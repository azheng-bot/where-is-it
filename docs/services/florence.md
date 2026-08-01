# Florence 模型服务

## 定位

Florence 服务位于 `services/florence/`，默认监听 8002。入口只调用共享工厂 `create_model_app("florence")`；通用 HTTP、健康检查、并发与错误处理在 `services/model_runtime/app.py`，真实实现位于 `services/model_runtime/adapters.py`。

它是视觉流水线的第一阶段：在真实模式下使用 Florence-2 从一帧图片中生成对象检测结果或文字描述。它不访问数据库、不保存图片、不调用其他模型。

## HTTP 接口

- `GET /health/live`：进程存活。
- `GET /health/ready`：在 mock 模式或真实适配器成功加载后返回 `ready`；否则为 HTTP 503 和 `not_ready`。
- `POST /v1/infer`：接收共享 `InferenceRequest`，返回 `InferenceResponse`。详细字段见 [shared-runtime.md](shared-runtime.md)。

请求必须携带 `frame_ref` 或 `media_ref`；真实推理可优先从 `payload.frame_jpeg_b64` 读取图片。`contract_version` 必须为 `v1`。

## 推理行为

真实 `FlorenceAdapter` 的默认权重为 `florence-community/Florence-2-base`，可通过 `FLORENCE_MODEL` 覆盖。请求的 `payload.task` 只接受 `<OD>`、`<CAPTION>` 或 `<DETAILED_CAPTION>`，其他值降级为 `<OD>`。

- `<OD>`：返回 `result.detections`，每项包含 `label`、归一化 `[x, y, width, height]` 边界框和当前实现固定的 0.5 置信度。
- 描述任务：返回同样的结果结构，并可附加 `caption`。

视觉编排器在真实流程中以 `<OD>` 调用本服务；它从 `detections` 取出 label 作为 Grounding 候选。mock 模式不会加载模型，并仅将 `payload.candidates` 转化为覆盖全图的假检测；当前编排器首个 Florence 请求不带 candidates，所以 mock 模式通常由编排器自身的 mock 流程完全绕过。

## 配置与运行

| 配置 | 说明 |
| --- | --- |
| `MODEL_MODE` | `mock`（默认）或真实模式 |
| `MODEL_DEVICE` / `FLORENCE_DEVICE` | 模型执行设备；Compose GPU 默认为 `cuda:0` |
| `FLORENCE_MODEL` | 模型标识 |
| `FLORENCE_MODEL_VERSION` / `MODEL_VERSION` | 健康/推理响应中的版本标识 |
| `MODEL_CACHE_DIR` | 设置为 Hugging Face 缓存根目录 |
| `MODEL_MAX_CONCURRENCY` | 进程内推理槽数，默认 1 |
| `FLORENCE_READY` / `MODEL_READY` | 就绪状态显式开关 |

Dockerfile 安装 Pillow、Torch 与 Transformers。可用 `pnpm --filter @where-is-it/florence dev` 本地启动，或通过 Compose CPU/GPU profile 启动。真实模式首次加载/下载模型会影响就绪状态，且不会阻塞其他独立服务。

## 故障语义

不支持的契约版本返回 422；模型未加载返回 503 和 `model_not_ready`；信号量等待超时返回 504 与 `deadline_exceeded`。视觉编排器将这些情况记为阶段失败并不发布该帧任何物品事实。

