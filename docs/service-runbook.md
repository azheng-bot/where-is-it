# 三服务运行手册

本手册的生产交付单位只有 `video-streamer`、`gpu-inference-api` 和 `web`。GPU 包内的视觉模型和 ASR 只通过 Compose 内部网络通信，不单独开放端口或单独部署。

## 1. 部署前准备

| 服务 | 主机要求 | 准备的配置 |
| --- | --- | --- |
| `gpu-inference-api` | Ubuntu 22.04、NVIDIA GPU、Docker Engine、NVIDIA Container Toolkit | `deploy/gpu-inference-api/.env` |
| `video-streamer` | 能访问 USB 摄像头、RTSP 源或 mock 视频；可向 GPU 节点发起 HTTPS 请求 | `deploy/video-streamer/.env` |
| `web` | 能对浏览器提供静态 HTTP 内容 | `deploy/web/.env` |

GPU 主机的驱动、Docker 和运行时安装流程见 [GPU 服务部署说明](../deploy/gpu-inference-api/README.md)。不要在摄像头侧安装模型，也不要在 Web 主机安装 Python 推理环境。

## 2. 启动顺序

### GPU 推理与 API 服务

在 GPU 主机中复制模板并设置：`GPU_VISION_PUBLIC_URL`、`WEB_ALLOWED_ORIGINS`、`VISION_PUSH_TOKEN`。`VISION_PUSH_TOKEN` 应为高强度随机值。

```bash
cp deploy/gpu-inference-api/.env.example deploy/gpu-inference-api/.env
bash deploy/gpu-inference-api/scripts/preflight-linux-gpu.sh
docker compose --env-file deploy/gpu-inference-api/.env \
  -f deploy/gpu-inference-api/docker-compose.yml up -d --build
bash deploy/gpu-inference-api/scripts/verify-deployment.sh
```

只允许发布 API `8000` 与帧接收器 `8001`。Florence、Grounding、SAM、Embedding、ASR 的 `8002`–`8006` 不得配置宿主机端口或公网反向代理。

### 视频推流服务

在摄像头侧设置视频源，并将 `FRAME_INGEST_URL` 指向 GPU 接收器，例如 `https://gpu.example.com/v1/frames`。令牌须与 GPU 配置一致。

```bash
cp deploy/video-streamer/.env.example deploy/video-streamer/.env
docker compose --env-file deploy/video-streamer/.env \
  -f deploy/video-streamer/docker-compose.yml up -d --build
```

`CAMERA_SOURCE` 可为 `usb`、`rtsp` 或 `mock-video`；RTSP 还需填写 `CAMERA_RTSP_URL`。推流端只保留最新帧的工作数据，推送失败即丢弃该帧，不录像、不重放、不积压。

### Web 服务

将 `PUBLIC_API_URL` 设置为浏览器可访问的 GPU API 根地址（例如 `https://gpu.example.com`），随后构建和启动。该地址会写入静态资源，因此改动后必须重新构建 Web。

```bash
cp deploy/web/.env.example deploy/web/.env
docker compose --env-file deploy/web/.env \
  -f deploy/web/docker-compose.yml up -d --build
```

## 3. 健康检查

| 服务 | 检查方式 | 预期 |
| --- | --- | --- |
| `video-streamer` | `GET /health/live`、`GET /health/ready` | 采集进程可用；失败帧不会堆积 |
| `gpu-inference-api` | `GET http://<gpu-host>:8000/health/ready` | 汇总 API、接收器和 ASR 状态 |
| GPU 接收器 | `GET http://<gpu-host>:8001/health/ready` | 仅供运维；生产环境应受网络策略保护 |
| `web` | 请求 `/` | 静态文件可访问 |

部署前运行 `pnpm topology:check`。三个服务均可访问后，运行 `pnpm smoke:services`；可用 `VIDEO_STREAMER_URL`、`GPU_API_URL` 与 `WEB_URL` 指定检查目标。

## 4. GPU-only 验证

部署前运行 `pnpm topology:check`。真实 GPU 节点通过 `preflight-linux-gpu.sh` 和 `verify-deployment.sh` 验证 CUDA、模型、ASR、API 和帧接收器。没有 NVIDIA GPU、CUDA 运行时或真实模型时，GPU 包应保持未就绪；不提供 CPU/mock 联调配置。

`video-streamer` 可以使用 `CAMERA_SOURCE=mock-video` 发送测试 JPEG，但 GPU 端仍执行真实模型推理。