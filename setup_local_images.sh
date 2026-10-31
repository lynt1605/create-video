#!/usr/bin/env bash
# Cài tạo ảnh cục bộ (miễn phí, không giới hạn): torch CPU + diffusers + DreamShaper-8 (fp16) + LCM-LoRA. ~2.5GB, chỉ làm 1 lần.
set -e
cd "$(dirname "$0")"
.venv/bin/pip install -q torch --index-url https://download.pytorch.org/whl/cpu
.venv/bin/pip install -q diffusers transformers accelerate peft safetensors huggingface_hub
.venv/bin/python - <<'PY'
from huggingface_hub import snapshot_download
p = snapshot_download("Lykon/dreamshaper-8", local_dir="models/dreamshaper-8",
    allow_patterns=["model_index.json","scheduler/*","tokenizer/*","text_encoder/config.json","text_encoder/model.fp16.safetensors",
    "unet/config.json","unet/diffusion_pytorch_model.fp16.safetensors","vae/config.json","vae/diffusion_pytorch_model.fp16.safetensors"])
snapshot_download("latent-consistency/lcm-lora-sdv1-5", local_dir="models/lcm-lora-sdv1-5")
print("MODELS READY", p)
PY
