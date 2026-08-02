# ASR 内部运行时

ASR 位于 `services/asr/`，是 `gpu-inference-api` 服务包中的私有 CUDA 运行时，默认内部端口为 `8006`。浏览器始终只访问 API；API 将音频转交给 faster-whisper，并把转写文本走与键盘输入相同的查询流程。

ASR 只支持 `ASR_DEVICE=cuda` 和 `ASR_COMPUTE_TYPE=float16`。不提供 mock、CPU 或无模型后备路径；模型不可用时 `/health/ready` 和转写接口明确返回未就绪，而文字查询仍保持可用。

| 配置 | 用途 |
| --- | --- |
| `ASR_MODEL` / `ASR_MODEL_VERSION` | faster-whisper 模型和版本 |
| `ASR_DEVICE` | 必须为 `cuda` |
| `ASR_COMPUTE_TYPE` | CUDA 推理精度，默认 `float16` |
| `ASR_MODEL_CACHE_DIR` | 持久化模型缓存 |
| `ASR_MAX_AUDIO_BYTES` | 上传音频大小上限 |

支持 webm、wav、mpeg 和 mp4。临时音频文件在转写结束后删除；ASR 端口不得映射到宿主机或公网。