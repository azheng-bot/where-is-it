# Grounding 内部运行时

Grounding 位于 `services/grounding/`，是 `gpu-inference-api` 内部的真实 GPU 模型运行时，默认内部端口 `8003`。它接收 Florence 候选标签和当前 JPEG 帧，执行目标定位与标签验证。

运行时只接受 CUDA 设备和真实模型权重；模型未加载、GPU 不可见或显存不足时返回未就绪，不会降级到 mock 或 CPU。其端口只供 GPU 包内视觉编排器访问。