# Florence 内部运行时

Florence 位于 `services/florence/`，是 `gpu-inference-api` 内部的真实 GPU 模型运行时，默认内部端口 `8002`。它读取 JPEG 帧并产生检测或描述，供视觉编排器继续调用 Grounding、SAM 和 Embedding。

启动时会加载实际模型并检查 CUDA 设备、显存下限和模型缓存。`/health/ready` 只有模型加载完成且 CUDA 可用时返回 ready；不存在 mock 或 CPU 推理模式。常用配置为 `MODEL_DEVICE=cuda:0`、`MODEL_DTYPE=float16`、`MODEL_MIN_GPU_MEMORY_GB=20` 与 `MODEL_CACHE_DIR=/models`。