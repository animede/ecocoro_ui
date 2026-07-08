"""Wraps Flux2KleinPipeline: lazy load, single-GPU exclusive access, thread offload.

Note on negative prompting: in diffusers 0.39.0 the pipeline's `negative_prompt_embeds`
kwarg only accepts a pre-computed torch.Tensor (it is forwarded straight into
`encode_prompt(prompt_embeds=...)`), not raw text. There is no text-based
`negative_prompt` argument on this pipeline. We therefore accept negative_prompt in our
API/DB for UX and record-keeping, but do not forward it to the pipeline call itself to
avoid a runtime crash. Classifier-free guidance still runs against an internal empty
string negative prompt whenever guidance_scale > 1 (this model is not distilled).
"""
import asyncio
import concurrent.futures
import logging
from typing import Optional

import torch
from PIL import Image

logger = logging.getLogger("ecocoro.pipeline")


class PipelineManager:
    def __init__(self, model_id: str, device: str):
        self.model_id = model_id
        self.device = device
        self._pipe = None
        self._load_lock = asyncio.Lock()
        self._gen_lock = asyncio.Lock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    async def ensure_loaded(self):
        if self._pipe is not None:
            return
        async with self._load_lock:
            if self._pipe is not None:
                return
            loop = asyncio.get_running_loop()
            self._pipe = await loop.run_in_executor(self._executor, self._load_pipeline)

    def _load_pipeline(self):
        from diffusers import Flux2KleinPipeline

        logger.info("Loading pipeline %s on %s ...", self.model_id, self.device)
        pipe = Flux2KleinPipeline.from_pretrained(self.model_id, torch_dtype=torch.bfloat16)
        pipe.to(self.device)
        logger.info("Pipeline loaded.")
        return pipe

    async def generate(
        self,
        prompt: str,
        image: Optional[Image.Image] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        num_inference_steps: int = 28,
        guidance_scale: float = 3.5,
        num_images_per_prompt: int = 1,
        seed: Optional[int] = None,
    ) -> list[Image.Image]:
        await self.ensure_loaded()
        async with self._gen_lock:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self._executor,
                self._run_pipe,
                prompt,
                image,
                width,
                height,
                num_inference_steps,
                guidance_scale,
                num_images_per_prompt,
                seed,
            )

    def _run_pipe(
        self,
        prompt,
        image,
        width,
        height,
        num_inference_steps,
        guidance_scale,
        num_images_per_prompt,
        seed,
    ) -> list[Image.Image]:
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)

        kwargs = dict(
            prompt=prompt,
            image=image,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            num_images_per_prompt=num_images_per_prompt,
            generator=generator,
            output_type="pil",
        )
        # width/height are only meaningful for pure T2I; the pipeline derives size
        # from the reference image itself for i2i/edit (image is not None).
        if image is None:
            kwargs["width"] = width
            kwargs["height"] = height

        result = self._pipe(**kwargs)
        return result.images


_manager: Optional[PipelineManager] = None


def get_pipeline_manager(model_id: str, device: str) -> PipelineManager:
    global _manager
    if _manager is None:
        _manager = PipelineManager(model_id, device)
    return _manager
