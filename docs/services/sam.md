# SAM 内部运行时

SAM 位于 `services/sam/`，是 `gpu-inference-api` 内部的真实 GPU 模型运行时，默认内部端口 `8004`。它将 Grounding 的检测框转化为分割结果和 `mask_area`，由视觉编排器筛选可验证观测。

模型启动和推理均要求 CUDA；没有 mock 或 CPU 后备模式。`MODEL_DEVICE` 应指向 GPU，`MODEL_DTYPE` 默认 `float16`，模型缓存使用 GPU 包共享的 `model-cache` 卷。端口不得公开。