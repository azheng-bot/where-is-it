# 三服务部署拓扑

本文是 [三服务架构与部署](three-service-architecture.md) 的速查页。正式交付只有三个服务包。

| 服务包 | 宿主环境 | 对外配置 | 私有依赖 | 持久化数据 |
| --- | --- | --- | --- | --- |
| `video-streamer` | 摄像头边缘设备 | `FRAME_INGEST_URL`、`VISION_PUSH_TOKEN` | 摄像头适配器 | 无；失败帧直接丢弃 |
| `gpu-inference-api` | GPU 节点 | `GPU_API_PORT`、`GPU_VISION_PORT`、`WEB_ALLOWED_ORIGINS`、`VISION_PUSH_TOKEN` | 接收器、视觉模型、ASR（Compose 内部） | `api-data`、`model-cache` 卷 |
| `web` | 静态站点 / Web 服务器 | `PUBLIC_API_URL` | 无 | 无 |

浏览器只访问 `PUBLIC_API_URL`；摄像头侧只访问 `FRAME_INGEST_URL`。GPU 包内的 API、接收器、模型和 ASR 通过 Compose DNS 通信。模型和 ASR 端口绝不可发布到宿主机。

## 最小连通性检查

- 推流服务：`/health/live`、`/health/ready`。
- GPU API：`8000/health/ready`；接收器 `8001/health/ready` 只应在受控运维网络中访问。
- Web：请求 `/`；部署后浏览器只能看到配置好的 API 根地址。

GPU 推理包只支持真实 NVIDIA GPU、真实模型和 CUDA ASR。生产部署与回滚均以 `deploy/video-streamer`、`deploy/gpu-inference-api`、`deploy/web` 为准。