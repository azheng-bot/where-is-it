# Embedding 内部运行时

Embedding 位于 `services/embedding/`，是 `gpu-inference-api` 内部的真实 GPU 模型运行时，默认内部端口 `8005`。它为检测区域生成 DINOv2 图像特征，以便后续身份确认和相似性能力演进。

服务仅支持真实 CUDA 推理。模型加载、显存检查或推理失败会以就绪状态和内部契约错误报告，不产生模拟向量，也不会退回 CPU。该端口仅在 GPU Compose 网络内可见。