# ASR 语音转写服务

## 定位

ASR 服务位于 `services/asr/`，默认监听 8006。它把原始音频字节转成中文文本，并与业务 API 解耦，以便模型、设备和 GPU 资源可单独部署。浏览器只访问 API；API 再调用本服务的 `/v1/transcribe`。

## 接口

| 端点 | 说明 |
| --- | --- |
| `GET /health/live` | 返回进程存活 |
| `GET /health/ready` | 返回模式、模型版本、设备和 readiness；不可用时 HTTP 503 |
| `POST /v1/transcribe` | 请求体为原始音频字节，`Content-Type` 指定媒体格式 |

支持 `audio/webm`、`audio/wav`、`audio/mpeg` 和 `audio/mp4`，包括带 codec 参数的 Content-Type。响应统一含 `text`、`provider`、`model_version`、`status`，成功时可含 `language`、`confidence`；失败时返回 `error_code`。

## 模式与实现

### Mock 模式

`ASR_MODE=mock` 是默认配置。`MockAdapter` 忽略音频内容，返回 `ASR_MOCK_TEXT`（默认“我的钥匙在哪里？”）、`mock-asr` 和 1.0 置信度，用于不安装模型时走通浏览器录音到查询的全链路。

### faster-whisper 模式

`ASR_MODE=faster-whisper` 时，`FasterWhisperAdapter` 在第一次转写时才加载模型，避免拖慢服务启动。它会把请求音频写入临时文件，调用 faster-whisper，随后在 `finally` 中删除临时文件。固定使用 `language="zh"`、`task="transcribe"`、`beam_size=5`、`vad_filter=true` 和 `condition_on_previous_text=false`。

模型名由 `ASR_MODEL`（默认 `small`）决定；`ASR_MODEL_CACHE_DIR` 可指定下载缓存目录；`ASR_COMPUTE_TYPE` 默认随设备选择（CUDA 默认 `float16`，CPU 默认 `int8`）。若没有文字结果，服务返回 `empty_transcription` 而非伪造成功。

## 校验与失败语义

转写前，服务会校验媒体类型、非空内容和 `ASR_MAX_AUDIO_BYTES`（默认 10 MiB）。典型失败码如下：

| 错误码 | HTTP | 含义 |
| --- | ---: | --- |
| `unsupported_media_type` | 415 | 格式不受支持 |
| `empty_audio` | 422 | 请求体为空 |
| `audio_too_large` | 413 | 超过大小上限 |
| `model_not_ready` | 503 | `ASR_READY` 关闭或模型未就绪 |
| `invalid_asr_mode` | 503 | 未支持的运行模式 |
| `model_unavailable` / `model_load_failed` | 503 | faster-whisper 不可用或加载失败 |
| `transcription_failed` / `empty_transcription` | 422 | 转写不能产生有效文本 |

业务 API 会把 ASR 网络问题映射为 `service_unavailable` 或 `deadline_exceeded`。转写失败只影响该次语音输入，不会更新物品、位置或观测；用户仍可改用文字查询。

## 配置、部署与测试

| 配置 | 说明 |
| --- | --- |
| `ASR_MODE` | `mock` 或 `faster-whisper` |
| `ASR_MODEL`、`ASR_MODEL_VERSION` | 模型加载与响应版本 |
| `ASR_DEVICE` | 默认 `cpu`，可设置 CUDA |
| `ASR_COMPUTE_TYPE` | 默认根据设备推导 |
| `ASR_MODEL_CACHE_DIR` | 模型缓存目录 |
| `ASR_MAX_AUDIO_BYTES` | 音频最大字节数 |
| `ASR_READY` | 就绪状态覆盖，默认 true |

容器镜像安装 `faster-whisper`。可使用 `pnpm --filter @where-is-it/asr dev` 启动；单元测试位于 `services/asr/tests/test_main.py`，执行 `python -m unittest discover -s services/asr/tests -v`。

