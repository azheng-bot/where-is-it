# 在哪里（Where Is It）

面向单房间、单摄像头场景的室内物品查找助手。页面将“当前检测到”“最后一次确定位置”和“推测位置”分层展示，不把推测当作事实。

## 正式部署架构

系统按运行环境交付为三个服务包，而不是按源码中的每个进程分别部署：

| 服务包 | 部署位置 | 职责 | 对外入口 |
| --- | --- | --- | --- |
| `video-streamer` | 摄像头可达的边缘设备 | USB、RTSP 或 mock 视频取帧；以 JPEG 帧推送到 GPU 节点 | 可选健康检查：`8001` |
| `gpu-inference-api` | Linux GPU 节点 | 帧接收、视觉推理、ASR、业务 API、SQLite 与证据存储 | API：`8000`；受令牌保护的接收器：`8001` |
| `web` | 静态站点或 Web 服务器 | 查询、录音、结果与证据展示 | HTTP：`5173`（默认） |

Florence、Grounding、SAM、Embedding 与 ASR 是 `gpu-inference-api` Compose 包内的私有运行时；浏览器和边缘设备都不能直接访问它们。

完整架构、网络边界和配置说明见 [三服务架构与部署](docs/three-service-architecture.md)，生产操作见 [服务运行手册](docs/service-runbook.md)。

## 三服务启动

先在 GPU 主机完成 Linux 与 NVIDIA 环境准备，再依次启动 GPU、推流和 Web：

```bash
# GPU 节点
cp deploy/gpu-inference-api/.env.example deploy/gpu-inference-api/.env
docker compose --env-file deploy/gpu-inference-api/.env \
  -f deploy/gpu-inference-api/docker-compose.yml up -d --build

# 摄像头边缘设备
cp deploy/video-streamer/.env.example deploy/video-streamer/.env
docker compose --env-file deploy/video-streamer/.env \
  -f deploy/video-streamer/docker-compose.yml up -d --build

# Web 主机
cp deploy/web/.env.example deploy/web/.env
docker compose --env-file deploy/web/.env \
  -f deploy/web/docker-compose.yml up -d --build
```

三个 `.env` 的关键关联：

- `video-streamer.FRAME_INGEST_URL` 指向 `https://<gpu-host>/v1/frames`。
- `video-streamer.VISION_PUSH_TOKEN` 与 `gpu-inference-api.VISION_PUSH_TOKEN` 必须完全一致。
- `web.PUBLIC_API_URL` 指向 `https://<gpu-host>`，不能填模型、ASR 或摄像头地址。

GPU 节点安装、预检与 CUDA/PyTorch 要求见 [GPU 服务部署说明](deploy/gpu-inference-api/README.md)；帧推送协议见 [远程视频推流](docs/remote-video-push.md)。

## 开发与验证

GPU 推理包仅支持真实 NVIDIA GPU、真实视觉模型和 CUDA ASR。请使用 `deploy/gpu-inference-api` 的环境模板、预检和 Compose 入口；未配置 GPU 时，模型与 ASR 会明确未就绪，不会回退到 mock 或 CPU。

摄像头边缘服务可使用 `CAMERA_SOURCE=mock-video` 作为测试帧源，但帧到达 GPU 后仍会走真实推理链路。

## 验证

```powershell
pnpm build
pnpm contracts:check
pnpm topology:check
Set-Location services/api; python -m unittest discover -s tests -v
```

三个服务均已启动时，可执行 `pnpm smoke:services`；用 `VIDEO_STREAMER_URL`、`GPU_API_URL`、`WEB_URL` 覆盖默认检查地址。