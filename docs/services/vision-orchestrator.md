# 视觉接收与编排组件

`services/vision-orchestrator/` 在三服务架构中有两个受限角色：`video-streamer` 中的 `pusher` 从 USB、RTSP 或视频文件读取 JPEG 帧；`gpu-inference-api` 中的 `receiver` 接收受令牌保护的 JPEG 帧，并调用私有 Florence、Grounding、SAM 和 Embedding。

GPU 接收器只执行真实模型流水线，不提供独立或 mock 观测模式。它只保存待处理的最新帧，慢推理或失败不会形成视频队列。`POST /v1/frames` 需要 `X-Vision-Push-Token`；`/health/ready` 和 `/internal/camera/status` 供受控运维诊断。

摄像头侧可使用 `mock-video` 作为视频输入夹具，但它仍是实际 JPEG 采集和推送，不会生成模拟推理结果。