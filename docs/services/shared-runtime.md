# GPU 内部推理运行时与契约

`services/shared/` 与 `services/model_runtime/` 为 `gpu-inference-api` 提供内部视觉推理契约、HTTP 客户端和真实模型运行时。它们不是独立对外服务。

每个内部请求携带 `request_id`、契约版本、时限和 JPEG/媒体引用；响应包含同一关联标识、模型版本与成功或失败状态。模型运行时固定使用 CUDA 和真实权重：CUDA 不可见、显存不足、模型加载失败或超时都会显式失败，不会执行 mock 或 CPU 推理。

四个视觉容器只暴露 `/health/live`、`/health/ready` 和 `/v1/infer` 到 GPU 包内部网络。API 仍是业务事实、SQLite 和证据的唯一写入者。