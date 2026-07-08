from typing import Literal, Optional

from pydantic import BaseModel, Field


class T2IRequest(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    width: int = 1024
    height: int = 1024
    steps: int = Field(28, ge=1, le=100)
    guidance_scale: float = 3.5
    seed: Optional[int] = None
    num_images: int = Field(1, ge=1, le=4)


class ImageMetadata(BaseModel):
    id: str
    type: str
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    steps: Optional[int] = None
    guidance_scale: Optional[float] = None
    seed: Optional[int] = None
    source_image_id: Optional[str] = None
    filename: str
    created_at: str


class GenerationResponse(BaseModel):
    ids: list[str]
    images: list[ImageMetadata]


class PromptExpandRequest(BaseModel):
    text: str
    mode: Literal["t2i", "i2i_edit"]


class PromptExpandResponse(BaseModel):
    result: str


class PromptTranslateRequest(BaseModel):
    text: str
    direction: Literal["ja2en", "en2ja"]


class PromptTranslateResponse(BaseModel):
    result: str
