import io
import logging
import os
import uuid
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

from backend import db
from backend.config import settings
from backend.llm_client import (
    LLMClient,
    SYSTEM_MESSAGE_TRANSLATE_EN2JA,
    SYSTEM_MESSAGE_TRANSLATE_JA2EN,
    SYSTEM_MESSAGE_UPSAMPLING_I2I,
    SYSTEM_MESSAGE_UPSAMPLING_T2I,
)
from backend.pipeline_manager import get_pipeline_manager
from backend.schemas import (
    GenerationResponse,
    ImageMetadata,
    PromptExpandRequest,
    PromptExpandResponse,
    PromptTranslateRequest,
    PromptTranslateResponse,
    T2IRequest,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ecocoro")

app = FastAPI(title="ecocoro image generator")

db.init_db(settings.outputs_dir)
pipeline_manager = get_pipeline_manager(settings.model_id, settings.device)
llm_client = LLMClient(settings.llm_endpoint, settings.llm_model, settings.llm_api_key)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


def _save_images(
    images: list[Image.Image],
    gen_type: str,
    prompt: str,
    negative_prompt: Optional[str],
    width: Optional[int],
    height: Optional[int],
    steps: int,
    guidance_scale: float,
    seed: Optional[int],
    source_image_id: Optional[str],
) -> list[dict]:
    records = []
    created_at = db.now_iso()
    for img in images:
        image_id = uuid.uuid4().hex
        filename = f"{image_id}.png"
        path = os.path.join(settings.outputs_dir, filename)
        img.save(path, format="PNG")
        record = {
            "id": image_id,
            "type": gen_type,
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width if width is not None else img.width,
            "height": height if height is not None else img.height,
            "steps": steps,
            "guidance_scale": guidance_scale,
            "seed": seed,
            "source_image_id": source_image_id,
            "filename": filename,
            "created_at": created_at,
        }
        db.insert_image(record)
        records.append(record)
    return records


def _to_response(records: list[dict]) -> GenerationResponse:
    return GenerationResponse(
        ids=[r["id"] for r in records],
        images=[ImageMetadata(**r) for r in records],
    )


@app.post("/api/t2i", response_model=GenerationResponse)
async def t2i(req: T2IRequest):
    try:
        images = await pipeline_manager.generate(
            prompt=req.prompt,
            image=None,
            width=req.width,
            height=req.height,
            num_inference_steps=req.steps,
            guidance_scale=req.guidance_scale,
            num_images_per_prompt=req.num_images,
            seed=req.seed,
        )
    except Exception as exc:
        logger.exception("t2i generation failed")
        raise HTTPException(status_code=500, detail=f"画像生成に失敗しました: {exc}") from exc

    records = _save_images(
        images, "t2i", req.prompt, req.negative_prompt, req.width, req.height,
        req.steps, req.guidance_scale, req.seed, None,
    )
    return _to_response(records)


async def _read_upload_image(image: UploadFile) -> Image.Image:
    data = await image.read()
    try:
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"画像ファイルの読み込みに失敗しました: {exc}") from exc


@app.post("/api/i2i", response_model=GenerationResponse)
async def i2i(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    negative_prompt: Optional[str] = Form(None),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    steps: int = Form(28),
    guidance_scale: float = Form(3.5),
    seed: Optional[int] = Form(None),
    num_images: int = Form(1),
):
    src_img = await _read_upload_image(image)
    source_record = _save_images([src_img], "source", "", None, None, None, 0, 0.0, None, None)[0]

    try:
        images = await pipeline_manager.generate(
            prompt=prompt,
            image=src_img,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            num_images_per_prompt=num_images,
            seed=seed,
        )
    except Exception as exc:
        logger.exception("i2i generation failed")
        raise HTTPException(status_code=500, detail=f"画像生成に失敗しました: {exc}") from exc

    records = _save_images(
        images, "i2i", prompt, negative_prompt, width, height,
        steps, guidance_scale, seed, source_record["id"],
    )
    return _to_response(records)


@app.post("/api/edit", response_model=GenerationResponse)
async def edit(
    image: UploadFile = File(...),
    instruction: str = Form(...),
    negative_prompt: Optional[str] = Form(None),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    steps: int = Form(28),
    guidance_scale: float = Form(3.5),
    seed: Optional[int] = Form(None),
    num_images: int = Form(1),
):
    src_img = await _read_upload_image(image)
    source_record = _save_images([src_img], "source", "", None, None, None, 0, 0.0, None, None)[0]

    try:
        images = await pipeline_manager.generate(
            prompt=instruction,
            image=src_img,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            num_images_per_prompt=num_images,
            seed=seed,
        )
    except Exception as exc:
        logger.exception("edit generation failed")
        raise HTTPException(status_code=500, detail=f"画像生成に失敗しました: {exc}") from exc

    records = _save_images(
        images, "edit", instruction, negative_prompt, width, height,
        steps, guidance_scale, seed, source_record["id"],
    )
    return _to_response(records)


@app.get("/api/images", response_model=list[ImageMetadata])
async def list_images():
    rows = db.list_images()
    return [ImageMetadata(**r) for r in rows if r["type"] != "source"]


@app.delete("/api/images/{image_id}")
async def delete_image(image_id: str):
    record = db.get_image(image_id)
    if record is None:
        raise HTTPException(status_code=404, detail="画像が見つかりません")
    path = os.path.join(settings.outputs_dir, record["filename"])
    if os.path.exists(path):
        os.remove(path)
    db.delete_image(image_id)
    return {"deleted": image_id}


@app.get("/api/images/{image_id}/download")
async def download_image(image_id: str):
    record = db.get_image(image_id)
    if record is None:
        raise HTTPException(status_code=404, detail="画像が見つかりません")
    path = os.path.join(settings.outputs_dir, record["filename"])
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="画像ファイルが見つかりません")
    return FileResponse(
        path,
        media_type="image/png",
        filename=f"ecocoro_{image_id}.png",
        headers={"Content-Disposition": f'attachment; filename="ecocoro_{image_id}.png"'},
    )


@app.get("/api/images/{image_id}")
async def get_image_file(image_id: str):
    record = db.get_image(image_id)
    if record is None:
        raise HTTPException(status_code=404, detail="画像が見つかりません")
    path = os.path.join(settings.outputs_dir, record["filename"])
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="画像ファイルが見つかりません")
    with open(path, "rb") as f:
        data = f.read()
    return Response(content=data, media_type="image/png")


@app.post("/api/prompt/expand", response_model=PromptExpandResponse)
async def prompt_expand(req: PromptExpandRequest):
    system_message = (
        SYSTEM_MESSAGE_UPSAMPLING_T2I if req.mode == "t2i" else SYSTEM_MESSAGE_UPSAMPLING_I2I
    )
    result = await llm_client.chat(system_message, req.text)
    return PromptExpandResponse(result=result)


@app.post("/api/prompt/translate", response_model=PromptTranslateResponse)
async def prompt_translate(req: PromptTranslateRequest):
    system_message = (
        SYSTEM_MESSAGE_TRANSLATE_JA2EN if req.direction == "ja2en" else SYSTEM_MESSAGE_TRANSLATE_EN2JA
    )
    result = await llm_client.chat(system_message, req.text)
    return PromptTranslateResponse(result=result)


@app.get("/")
async def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")
