"""Tạo ảnh ngay trên CPU: DreamShaper-8 + LCM-LoRA (4-6 bước). Miễn phí, không giới hạn, không phụ thuộc mạng."""
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "models" / "dreamshaper-8"
LORA = ROOT / "models" / "lcm-lora-sdv1-5"

_lock = threading.Lock()
_pipe = None

NEGATIVE = (
    "deformed face, distorted face, ugly, asymmetrical eyes, extra fingers, extra limbs, "
    "bad anatomy, blurry, lowres, text, watermark, logo, signature, cropped, duplicate"
)


def available() -> bool:
    return (MODEL / "model_index.json").exists() and (MODEL / "unet" / "diffusion_pytorch_model.fp16.safetensors").exists() \
        and any(LORA.glob("*.safetensors"))


def _load():
    global _pipe
    if _pipe is None:
        import os

        import torch
        from diffusers import LCMScheduler, StableDiffusionPipeline

        torch.set_num_threads(os.cpu_count() or 4)
        pipe = StableDiffusionPipeline.from_pretrained(
            MODEL, torch_dtype=torch.float32, variant="fp16", safety_checker=None, requires_safety_checker=False
        )
        pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
        pipe.load_lora_weights(LORA)
        pipe.fuse_lora()
        pipe.set_progress_bar_config(disable=True)
        _pipe = pipe
    return _pipe


def generate(prompt: str, out: Path, cfg: dict, seed: int = 7) -> Path:
    import torch

    with _lock:
        pipe = _load()
        gen = torch.Generator("cpu").manual_seed(seed)
        im = pipe(
            prompt, negative_prompt=NEGATIVE,
            width=cfg.get("local_width", 512), height=cfg.get("local_height", 768),
            num_inference_steps=cfg.get("local_steps", 5), guidance_scale=cfg.get("local_guidance", 1.5),
            generator=gen,
        ).images[0]
    im.save(out, quality=95)
    return out
