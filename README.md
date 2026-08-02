# 在哪里（Where Is It）

单卧室、单摄像头场景的室内物品查找助手。网页会将“当前检测到”“当前未检测到后的最后出现”和“推测位置”明确分层展示，避免将推测伪装为事实。

## 开发启动

```powershell
pnpm install
pnpm dev
```

For per-service dependency installation, local commands, GPU receiver startup,
and health checks, see [the service runbook](docs/service-runbook.md).

分别打开：

- Web：<http://127.0.0.1:5173>
- API：<http://127.0.0.1:8000/docs>
- Vision：<http://127.0.0.1:8001/health/ready>

Python 服务依赖见 `services/api/requirements.txt`，首次运行可执行：

```powershell
python -m pip install -r services/api/requirements.txt
```

## 验证

```powershell
pnpm build
pnpm contracts:check
Set-Location services/api; python -m unittest discover -s tests -v
```

当前为可演示的工程骨架：包含 SQLite/WAL 目录、十个演示物品、查询澄清、证据查看与目录改名。真实摄像头采集、模型适配、证据落盘与性能验收仍按 OpenSpec 任务继续实现。
## 三服务部署（推荐）

生产和演示环境按三个独立服务包交付：

| 服务包 | 部署位置 | 职责 | 对外端口 |
| --- | --- | --- | --- |
| `video-streamer` | 可访问摄像头的边缘设备 | USB/RTSP/mock 采集、最新 JPEG 帧鉴权推送 | 可选健康检查 `8001` |
| `gpu-inference-api` | GPU 节点 | 帧接收、视觉推理、ASR、物品 API、事实与证据存储 | API `8000`、受保护帧接收 `8001` |
| `web` | 静态站点或 Web 服务器 | 浏览器查询、录音、回答与证据展示 | `5173` |

复制各服务包中的 `.env.example` 为 `.env` 并分别启动：

```bash
docker compose --env-file deploy/gpu-inference-api/.env -f deploy/gpu-inference-api/docker-compose.yml up -d --build
docker compose --env-file deploy/video-streamer/.env -f deploy/video-streamer/docker-compose.yml up -d --build
docker compose --env-file deploy/web/.env -f deploy/web/docker-compose.yml up -d --build
```

GPU 包中的 Florence、Grounding、SAM、Embedding 与 ASR 仅在内部网络可见；不要发布其端口。CPU/mock 验证使用 `pnpm up:gpu:cpu`。运行 `pnpm topology:check` 检查服务边界；三套服务已启动后运行 `pnpm smoke:services`。
## 兼容的本地多进程开发

`pnpm dev` 会启动 Web、API、无 GPU 的 `vision-orchestrator`、四个默认 mock 的视觉模型服务，以及 ASR 服务。模型服务可以单独运行：`pnpm dev:models`；只启动产品闭环：`pnpm dev:core`。

| 服务 | 默认端口 | 默认模式 | GPU |
| --- | --- | --- | --- |
| vision-orchestrator | 8001 | mock | 否 |
| Florence / Grounding / SAM / Embedding | 8002–8005 | mock | 可选，独立配置 |
| ASR | 8006 | mock | 可选，独立配置 |

可使用 `docker compose --profile gpu up` 启动带独立 GPU 声明的模型服务；默认不假定全部模型能够同时装入一张显卡。
## CPU development and Linux GPU deployment

Local development uses CPU + mock by default. Run `pnpm dev`, or copy `.env.cpu.example` to `.env` and use the Compose CPU profile:

```powershell
docker compose -f docker-compose.yml -f docker-compose.cpu.yml --profile cpu up --build
```

The production GPU node baseline is Ubuntu 22.04, CUDA 13.2, Python 3.12, PyTorch 2.12.1, and a 24GB RTX 40-series GPU. Copy `.env.gpu.example` to `.env`, set `VISION_PUSH_TOKEN` and an `API_INTERNAL_URL` reachable from the GPU host, then run:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu up -d --build
docker compose -f docker-compose.yml -f docker-compose.gpu.yml --profile gpu exec florence \
  python /app/services/model_runtime/verify_gpu_runtime.py
```

This node is a video-frame receiver (`VISION_ROLE=receiver`), so no camera RTSP/IP is configured on it. The local capture process pushes JPEG frames to `/v1/frames` over HTTPS. Once started, `/health/ready` on each model service reports the PyTorch version, GPU name, compute capability, and available VRAM. See [remote video push](docs/remote-video-push.md) for the network configuration.

The `api-data` and `model-cache` volumes preserve database/evidence and model downloads across container recreation.
