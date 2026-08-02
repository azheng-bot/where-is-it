# GPU inference API on Ubuntu 22.04

This is a GPU-only production package. It runs the API, frame receiver, visual models, and CUDA ASR on one NVIDIA GPU node. Only API port `8000` and the push-token-protected receiver port `8001` are published; model and ASR ports are private.

## Requirements

- Ubuntu 22.04 with a working NVIDIA driver and `nvidia-smi`.
- Docker Engine and NVIDIA Container Toolkit.
- RTX 40-series GPU with at least 20 GB VRAM.
- Python 3.12, PyTorch 2.12.1 CUDA 13.2 wheels, and CUDA ASR libraries are built into the images.

CPU inference, mock models, and mock ASR are not supported. If Docker cannot expose an NVIDIA GPU, the model/ASR readiness checks remain unavailable rather than falling back.

## Deploy

```bash
sudo bash deploy/gpu-inference-api/scripts/bootstrap-ubuntu-22.04.sh
cp deploy/gpu-inference-api/.env.example deploy/gpu-inference-api/.env
# Set GPU_VISION_PUBLIC_URL, WEB_ALLOWED_ORIGINS and VISION_PUSH_TOKEN.
bash deploy/gpu-inference-api/scripts/preflight-linux-gpu.sh
docker compose --env-file deploy/gpu-inference-api/.env \
  -f deploy/gpu-inference-api/docker-compose.yml up -d --build
bash deploy/gpu-inference-api/scripts/verify-deployment.sh
```

The preflight and verification scripts must report CUDA 13.2, an available GPU, and real model/ASR readiness before traffic is accepted.