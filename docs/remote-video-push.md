# Remote video-frame push

The transport uses independent JPEG frames over HTTP, not public RTSP. The receiver keeps only the latest pending frame, so a slow GPU never accumulates recorded video or causes unbounded memory use.

## GPU inference receiver

Deploy the vision orchestrator next to the GPU with the model services and API endpoint it should publish observations to. Configure:

```env
VISION_ROLE=receiver
VISION_MODE=real
VISION_PUSH_TOKEN=replace-with-a-long-random-secret
API_INTERNAL_URL=http://api-or-public-api-host:8000
```

Expose only `POST /v1/frames` to the edge pusher. It accepts `image/jpeg`, returns `202 Accepted`, and requires the `X-Vision-Push-Token` header when `VISION_PUSH_TOKEN` is set.

## Local mock-video pusher

Run a second vision-orchestrator process on the machine that has the bundled mock video:

```env
VISION_ROLE=pusher
CAMERA_SOURCE=mock-video
VISION_INGEST_URL=https://gpu.example.com/v1/frames
VISION_PUSH_TOKEN=replace-with-the-same-secret
DISCOVERY_INTERVAL_SECONDS=1
```

For a direct IP during private testing, use `http://GPU_IP:8001/v1/frames`. Use HTTPS and an authenticated reverse proxy or named tunnel in production. The pusher does not need the model services or API because it only reads and forwards frames.

## Observability

- `GET /health/ready` reports the role and pushed-frame buffer state.
- `GET /internal/camera/status` reports `push` as the active source on a receiver.
- `POST /v1/frames/process` forces one local push or one receiver processing attempt for smoke tests.

## Ubuntu 22.04 / CUDA 13.2 RTX 40 (24GB) deployment

Copy `.env.gpu.example` to `.env` on the GPU host, set a strong
`VISION_PUSH_TOKEN`, and set `API_INTERNAL_URL` to the API endpoint reachable
from that host. The template is a **receiver** configuration, so leave
`CAMERA_RTSP_URL` empty: the local pusher initiates the outbound connection.

```bash
cp .env.gpu.example .env
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu up -d --build
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu exec florence \
  python /app/services/model_runtime/verify_gpu_runtime.py
curl -fsS http://127.0.0.1:8001/health/ready
```

The preflight must return `ok: true`, CUDA `13.2`, compute capability `8.9`,
and roughly 24GB VRAM before accepting production traffic. The four visual
services are constrained to one request each and use FP16. They share the one
GPU, so do not raise `MODEL_MAX_CONCURRENCY` until measured under the intended
frame rate. Publish port 8001 behind HTTPS with an authenticated reverse proxy;
do not expose the model ports 8002-8005 to the Internet.
