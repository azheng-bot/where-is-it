# 三服务架构与部署

本项目将运行时划分为三个可独立交付的服务包：`video-streamer`、`gpu-inference-api` 和 `web`。该划分按实际运行环境而非源码目录划分：摄像头设备负责推流，GPU 节点负责推理与业务 API，浏览器侧仅承载用户界面。

## 架构总览

```text
摄像头 / RTSP / mock 视频
          │ JPEG + X-Vision-Push-Token
          ▼
video-streamer ────── POST /v1/frames ──────► gpu-inference-api
                                                    │
                           ┌────────────────────────┼────────────────────────┐
                           │                        │                        │
                        API/SQLite            Vision runtime              ASR runtime
                      物品、证据事实       Florence/Grounding/SAM       faster-whisper
                           ▲                        │                        │
                           └──────────────内部观测与转写结果───────────────┘
                                                    ▲
                                                    │ HTTPS API
                                                   web
```

## 服务职责

| 服务包 | 运行位置 | 负责内容 | 不负责内容 |
| --- | --- | --- | --- |
| `video-streamer` | 摄像头可达的边缘设备 | 读取 USB、RTSP 或 mock 视频；压缩最新 JPEG 帧；使用令牌推送；报告采集与推送状态 | 模型推理、ASR、数据库、视频录像、浏览器查询 |
| `gpu-inference-api` | Ubuntu 22.04 GPU 节点 | 接收帧；视觉推理；语音转写；物品查询；证据与 SQLite 持久化；健康状态聚合 | 向公网单独暴露模型或 ASR 端口；保存完整视频流 |
| `web` | 静态站点或 Web 服务器 | 文字问答、麦克风录音、转写失败展示、证据查看、浏览器语音播报 | 访问摄像头、推流端、模型或 ASR 内部地址 |

## 网络与端口

| 使用方 | 目标 | 协议与端口 | 访问要求 |
| --- | --- | --- | --- |
| `video-streamer` | GPU 接收器 | `POST /v1/frames`，默认 `8001` | 必须携带 `X-Vision-Push-Token`；生产环境使用 HTTPS |
| 浏览器 `web` | GPU API | 默认 `8000` | 只配置 `PUBLIC_API_URL`；GPU 服务通过 `WEB_ALLOWED_ORIGINS` 限制来源 |
| GPU API | 接收器、模型、ASR | Compose 内部 DNS 与端口 `8001`–`8006` | 仅同一 `gpu-inference-api` Compose 网络可访问 |

模型服务 Florence、Grounding、SAM、Embedding 以及 ASR **不得**映射宿主机端口。GPU 包只发布 API `8000` 和经令牌保护的帧接收端口 `8001`。

## 配置文件

每个服务包都有独立配置模板：

| 服务 | 模板 | 必填配置 |
| --- | --- | --- |
| 视频推流 | `deploy/video-streamer/.env.example` | `CAMERA_SOURCE`、`FRAME_INGEST_URL`、`VISION_PUSH_TOKEN` |
| GPU 推理 API | `deploy/gpu-inference-api/.env.example` | `GPU_VISION_PUBLIC_URL`、`WEB_ALLOWED_ORIGINS`、`VISION_PUSH_TOKEN` |
| Web | `deploy/web/.env.example` | `PUBLIC_API_URL` |

`VISION_PUSH_TOKEN` 必须在推流服务和 GPU 服务中使用相同的高强度随机值。`PUBLIC_API_URL` 是 Web 构建时写入静态资源的唯一后端地址，不应设置模型、ASR 或摄像头地址。

## 启动顺序

1. 准备 GPU Linux 主机；详细步骤见 [GPU 服务部署说明](../deploy/gpu-inference-api/README.md)。
2. 在 GPU 主机复制 `deploy/gpu-inference-api/.env.example` 为 `.env`，配置公网地址、允许的 Web 域名和推送令牌。
3. 启动 GPU 服务并执行预检：

   ```bash
   bash deploy/gpu-inference-api/scripts/preflight-linux-gpu.sh
   docker compose --env-file deploy/gpu-inference-api/.env \
     -f deploy/gpu-inference-api/docker-compose.yml up -d --build
   bash deploy/gpu-inference-api/scripts/verify-deployment.sh
   ```

4. 在摄像头侧复制 `deploy/video-streamer/.env.example` 为 `.env`，配置视频源、GPU 接收地址和同一个令牌，然后启动：

   ```bash
   docker compose --env-file deploy/video-streamer/.env \
     -f deploy/video-streamer/docker-compose.yml up -d --build
   ```

5. 在 Web 主机复制 `deploy/web/.env.example` 为 `.env`，将 `PUBLIC_API_URL` 指向 GPU API，构建并启动：

   ```bash
   docker compose --env-file deploy/web/.env \
     -f deploy/web/docker-compose.yml up -d --build
   ```

## 健康检查与排障

- `video-streamer`：`GET /health/live`、`GET /health/ready`。推送失败时丢弃当前帧，不积压队列或写入视频文件。
- `gpu-inference-api`：`GET http://<gpu-host>:8000/health/ready` 汇总 API、视觉接收器与 ASR；接收器状态在 `8001/health/ready`。
- `web`：访问 `/` 确认静态页面可用；前端的 API 地址由 `VITE_API_BASE_URL` 构建参数提供。
- 配置静态校验：`pnpm topology:check`。
- 三个服务已启动后的本地冒烟检查：`pnpm smoke:services`。可通过 `VIDEO_STREAMER_URL`、`GPU_API_URL` 和 `WEB_URL` 覆盖默认检查地址。

当 GPU 推理或 ASR 不可用时，API 仍应返回既有物品事实与明确的降级状态；当推流中断时，系统不得将旧帧伪装为新的当前检测。

## 数据与回滚

`api-data` 卷保存 SQLite 数据库与证据图片，`model-cache` 卷保存模型下载。推流服务和 Web 服务均不持久化业务事实。回滚部署时，只需将 Web 的 API 地址和推流目标恢复到旧入口；不需要迁移或重写业务数据库。