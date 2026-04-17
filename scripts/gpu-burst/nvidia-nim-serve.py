#!/usr/bin/env python3
"""NVIDIA NIM on Modal — self-host Llama-3.1-8B-Instruct as OpenAI endpoint.

Serves an OpenAI-compatible /v1/chat/completions endpoint on Modal A10G GPU.
No rate limits. Free tier on Modal ($30/mo included). Fits A10G (24GB VRAM).

Why this model: build.nvidia.com free tier is 40 RPM / 1000 credits — we hit
that fast when a 22-agent TF fires 132 calls/day. This gives us an unlimited
self-hosted lane we can slot into the gateway as `modal-nim:llama-3.1-8b`.

Usage:
    modal secret create nvidia-nim NGC_API_KEY=nvapi-...    # first time
    modal serve scripts/gpu-burst/nvidia-nim-serve.py        # dev (warm)
    modal deploy scripts/gpu-burst/nvidia-nim-serve.py       # prod

After `modal deploy`, copy the URL shown and add to llm-gateway:

    "modal-nim:llama-3.1-8b": {
        "url": "https://<your-org>--nomos42-nim-server-serve.modal.run/v1/chat/completions",
        "model": "meta/llama-3.1-8b-instruct",
        "key_env": "MODAL_NIM_TOKEN",  # optional — set to empty for open access
        "provider": "nvidia_nim_modal",
        "max_tokens": 400, "rpm": 120, "tier": "fast",
    }

Larger models (Llama-3.3-70B, MiniMax M2.7) need H100 (80GB VRAM).
Swap `gpu="A10G"` → `gpu="H100"` and update MODEL_NAME/MODEL_IMAGE.
"""
from __future__ import annotations

import modal

app = modal.App("nomos42-nim-server")

# ── MODEL CHOICE ────────────────────────────────────────────────────────────
# A10G (24GB): llama-3.1-8b, mistral-7b, phi-3.5-mini, gemma-2-9b
# A100 (40GB): llama-3.3-70b-quantized, mistral-small-3.1
# H100 (80GB): llama-3.3-70b, minimax-m2.7 (MoE, 10B active)
MODEL_NAME = "meta/llama-3.1-8b-instruct"
MODEL_IMAGE = "nvcr.io/nim/meta/llama-3.1-8b-instruct:1.3.0"
GPU_TYPE = "A10G"  # change to "H100" for 70B+
SCALEDOWN_WINDOW = 300  # keep warm 5 min after last request

# NIM image: pull NVIDIA's prebuilt container — no custom build step required.
nim_image = (
    modal.Image.from_registry(MODEL_IMAGE, add_python=None)
    .env({
        "NIM_SERVED_MODEL_NAME": MODEL_NAME,
        "NIM_HTTP_API_PORT": "8000",
    })
)

secret = modal.Secret.from_name("nvidia-nim")  # must contain NGC_API_KEY=nvapi-...


@app.function(
    image=nim_image,
    gpu=GPU_TYPE,
    secrets=[secret],
    timeout=60 * 15,
    scaledown_window=SCALEDOWN_WINDOW,
    allow_concurrent_inputs=16,
)
@modal.web_server(port=8000, startup_timeout=120)
def serve():
    """NIM serves OpenAI-compatible /v1/chat/completions on :8000 automatically."""
    import subprocess
    subprocess.Popen(
        ["/opt/nim/start_server.sh"],
        env={
            **__import__("os").environ,
            "NGC_API_KEY": __import__("os").environ["NGC_API_KEY"],
        },
    )


@app.local_entrypoint()
def main():
    print(f"Model: {MODEL_NAME} on {GPU_TYPE}")
    print(f"Run `modal deploy {__file__}` to publish a stable URL.")
    print("Then curl the URL/v1/chat/completions with OpenAI payload.")
