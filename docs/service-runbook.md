# Service installation and startup

This runbook describes the three deployable service boundaries: `video-streamer`,
`gpu-inference-api`, and `web`. The visual model and ASR processes remain private
runtime dependencies inside the GPU service package; never expose their ports to
the public Internet.

## Recommended three-service deployment

1. On the GPU node, copy `deploy/gpu-inference-api/.env.example` to `.env`, set
   `VISION_PUSH_TOKEN`, `GPU_VISION_PUBLIC_URL`, and `WEB_ALLOWED_ORIGINS`, then run
   `docker compose --env-file deploy/gpu-inference-api/.env -f deploy/gpu-inference-api/docker-compose.yml up -d --build`.
2. On the camera-side machine, copy `deploy/video-streamer/.env.example` to `.env`,
   set the source plus the same token, then run
   `docker compose --env-file deploy/video-streamer/.env -f deploy/video-streamer/docker-compose.yml up -d --build`.
3. Build the Web package with `PUBLIC_API_URL` pointing to the GPU API:
   `docker compose --env-file deploy/web/.env -f deploy/web/docker-compose.yml up -d --build`.

The GPU package publishes only API port 8000 and its token-protected frame receiver
on port 8001. Florence, Grounding, SAM, Embedding, and ASR do not have host ports.
Run `pnpm topology:check` before deployment and `pnpm smoke:services` after all
three services are healthy. For Ubuntu host setup and runtime preflight, follow
[the GPU package guide](../deploy/gpu-inference-api/README.md).

## Shared prerequisites

Local development requires Node.js 20+, pnpm 9, and Python 3.12+ with pip.
Install JavaScript workspace dependencies once from the repository root:

```powershell
pnpm install
```

`pnpm` does not load `.env` for local Python processes. Set the environment
variables in the same shell, or use Docker Compose, which reads `.env`.

The GPU receiver requires Ubuntu 22.04, an RTX 40-series GPU with 24GB VRAM, a
CUDA 13.2 compatible NVIDIA driver, Docker Engine, and NVIDIA Container Toolkit.

## Web (`web`, port 5173)

Dependencies: the root `pnpm install` command.

```powershell
pnpm --filter @where-is-it/web dev
```

The web frontend accesses the API only; it does not access cameras or model
services.

## API (`api`, port 8000)

Install and start:

```powershell
python -m pip install -r services/api/requirements.txt
$env:DATABASE_PATH = "services/api/data/mock-where-is-it.db"
$env:EVIDENCE_DIR = "services/api/data/evidence"
pnpm --filter @where-is-it/api dev
```

API owns the SQLite database and evidence images. In Docker they persist in the
`api-data` volume mounted at `/data`.

## Edge video pusher (`vision-orchestrator`, port 8001)

Install local dependencies:

```powershell
python -m pip install "fastapi>=0.115,<1.0" "uvicorn[standard]>=0.30,<1.0" "pydantic>=2,<3" "python-multipart>=0.0.18,<1.0" "opencv-python-headless>=4.10,<5"
```

Start as a pusher. Replace the receiver URL and secret with real values:

```powershell
$env:VISION_ROLE = "pusher"
$env:CAMERA_SOURCE = "mock-video" # or usb / rtsp
$env:VISION_INGEST_URL = "https://gpu.example.com/v1/frames"
$env:VISION_PUSH_TOKEN = "set-a-long-random-secret"
$env:DISCOVERY_INTERVAL_SECONDS = "1"
pnpm --filter @where-is-it/vision-orchestrator dev
```

For RTSP also set `CAMERA_RTSP_URL`; for USB set `CAMERA_USB_INDEX` when needed.
The pusher needs only outbound HTTPS and does not save a video archive.

## GPU receiver and private visual runtimes

The same `vision-orchestrator` service acts as a receiver when
`VISION_ROLE=receiver`. It accepts `POST /v1/frames`, keeps only the latest frame
in memory, then calls four internal GPU services:

| Service | Port | Dependencies / purpose |
| --- | --- | --- |
| `florence` | 8002 | Torch, Transformers; detection and captions |
| `grounding` | 8003 | Torch, Transformers; open-vocabulary verification |
| `sam` | 8004 | Torch, Transformers; segmentation |
| `embedding` | 8005 | Torch, Transformers; DINOv2 embeddings |

Recommended GPU deployment: Docker builds all dependencies. Copy the profile,
set `VISION_PUSH_TOKEN`, `API_INTERNAL_URL`, and `VISION_PUBLIC_URL`, then start:

```bash
cp .env.gpu.example .env
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu up -d --build
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu exec florence \
  python /app/services/model_runtime/verify_gpu_runtime.py
```

The preflight must report Python 3.12, PyTorch 2.12.1, CUDA 13.2, capability 8.9,
and at least 20GB VRAM. The GPU images install `torch==2.12.1` from the CUDA
13.2 wheel index, plus FastAPI, Uvicorn, Pillow, and Transformers. Model weights
persist in the `model-cache` Docker volume. Use `MODEL_MODE=real`,
`MODEL_DTYPE=float16`, and `MODEL_MAX_CONCURRENCY=1` on the GPU node.

For non-container model debugging:

```powershell
python -m pip install "fastapi>=0.115,<1.0" "uvicorn[standard]>=0.30,<1.0" "pydantic>=2,<3" "python-multipart>=0.0.18,<1.0" "pillow>=10,<12" "transformers>=4.57,<6"
python -m pip install --index-url https://download.pytorch.org/whl/cu132 --extra-index-url https://pypi.org/simple "torch==2.12.1"
pnpm dev:models
```

## Private ASR runtime (`asr`, internal port 8006)

Install and start:

```powershell
python -m pip install "fastapi>=0.115,<1.0" "uvicorn[standard]>=0.30,<1.0" "pydantic>=2,<3" "faster-whisper>=1.1,<2.0"
pnpm --filter @where-is-it/asr dev
```

Keep `ASR_MODE=mock` for local development. Set `ASR_MODE=faster-whisper` to load
a real ASR model.

## Full-stack startup and health checks

After installing local dependencies, start the mock stack:

```powershell
pnpm dev
```

For the CPU Docker profile:

```powershell
Copy-Item .env.cpu.example .env
docker compose -f docker-compose.yml -f docker-compose.cpu.yml --profile cpu up --build
```

Health endpoints:

```text
http://127.0.0.1:8000/health/ready   API
http://127.0.0.1:8001/health/ready   vision role
http://127.0.0.1:8002/health/ready   Florence
http://127.0.0.1:8003/health/ready   Grounding DINO
http://127.0.0.1:8004/health/ready   SAM2
http://127.0.0.1:8005/health/ready   Embedding
http://127.0.0.1:8006/health/ready   ASR
```

## Data and network boundaries

- Pusher: no persistent video; reads a source and sends JPEG frames.
- Receiver: one latest frame only in memory; restart discards it.
- API: database and evidence images; do not place them in model containers.
- Public surface: HTTPS receiver plus Web/API. Keep all model ports internal.
