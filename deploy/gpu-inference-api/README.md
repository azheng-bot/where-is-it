# GPU inference API on Ubuntu 22.04

This package runs API, receiver, visual models and ASR on one NVIDIA GPU node.
Only API port `8000` and the push-token-protected receiver port `8001` are
published. Do not publish model or ASR ports.

## Host preparation

1. Install an NVIDIA driver appropriate for the installed RTX 40-series GPU and
   verify `nvidia-smi` works on the host.
2. Run `sudo bash deploy/gpu-inference-api/scripts/bootstrap-ubuntu-22.04.sh`.
3. Copy `.env.example` to `.env`; set `GPU_VISION_PUBLIC_URL`,
   `WEB_ALLOWED_ORIGINS`, and a long unique `VISION_PUSH_TOKEN`.
4. Run `bash deploy/gpu-inference-api/scripts/preflight-linux-gpu.sh`.

The supported runtime is Python 3.12, PyTorch 2.12.1 with the CUDA 13.2 wheel,
and a CUDA-capable RTX 40-series GPU with at least 20 GB VRAM. ASR includes the
CUDA 12 cuBLAS and cuDNN 9 user-space libraries required by faster-whisper.

## Deploy and verify

```bash
docker compose --env-file deploy/gpu-inference-api/.env \
  -f deploy/gpu-inference-api/docker-compose.yml up -d --build
bash deploy/gpu-inference-api/scripts/verify-deployment.sh
```

For CPU/mock development, merge `docker-compose.cpu.yml` and use `MODEL_MODE=mock`.
The production GPU command is intentionally separate so a missing GPU cannot be
silently replaced with CPU inference.