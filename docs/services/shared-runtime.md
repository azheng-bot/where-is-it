# 共享模型运行时与内部契约

## 作用范围

这不是一个独立 HTTP 服务，而是视觉编排器、四个视觉模型服务和业务 API 共用的基础层：

- `services/shared/contracts.py`：Python 内部推理请求/响应模型与错误码；
- `services/shared/client.py`：同步 HTTP 调用、超时和异常映射；
- `services/model_runtime/app.py`：视觉模型服务通用 FastAPI 工厂；
- `services/model_runtime/adapters.py`：Florence、Grounding、SAM、Embedding 的惰性真实适配器。

TypeScript 前端公共 API 类型独立位于 `packages/contracts/src/api.ts`，与该内部推理契约不混用。

## `v1` 推理契约

所有视觉模型服务使用 `POST /v1/infer`。请求 `InferenceRequest` 的关键字段是：

| 字段 | 含义 |
| --- | --- |
| `request_id` | 调用链关联 ID，由编排器生成并在响应中回传 |
| `contract_version` | 当前固定为 `v1` |
| `deadline_ms` | 0–30000 ms 的请求期限 |
| `source` | 输入来源，例如 `camera:mock-video` |
| `frame_ref` 或 `media_ref` | 至少一个媒体引用，保证模型有输入来源 |
| `query` | 可选文本查询 |
| `payload` | 服务特定数据，例如 Base64 JPEG、候选标签或检测框 |

`InferenceResponse` 返回相同的 `request_id`、契约版本、`model_name`、`model_version`、状态、结果与可选错误。状态为 `ok`、`degraded` 或 `failed`；错误码包括 `service_unavailable`、`deadline_exceeded`、`contract_mismatch`、`invalid_request`、`model_not_ready`。

契约验证保证请求没有媒体引用时直接失败。模型服务不支持的版本返回 HTTP 422；调用方通过统一客户端将其视为 `contract_mismatch`。

## 通用模型服务工厂

`create_model_app(service_name)` 为四个服务统一提供：

- 存活与就绪端点；
- 模型版本与设备信息；
- 基于 `BoundedSemaphore` 的每服务并发限制；
- mock 与真实模式切换；
- 统一的 HTTP 503/504/422/500 与结构化推理响应；
- 每次推理的结构化日志，含服务、请求 ID、模型版本、状态和延迟。

`MODEL_MODE=mock` 时不会加载真实适配器，服务可立即 ready。非 mock 模式下，启动阶段惰性加载适配器；加载失败会被记录，并让 readiness 返回未就绪。所有实际模型权重缓存可通过 `MODEL_CACHE_DIR` 统一指定，单服务可使用 `*_READY`、`*_MODEL_VERSION` 与 `*_DEVICE` 覆盖通用变量。

## 调用方的降级处理

`InternalServiceClient` 将请求时限转换为 urllib 超时，并转化常见错误：HTTP 422 → `contract_mismatch`，408/504 或 Python Timeout → `deadline_exceeded`，其余 HTTP/网络错误 → `service_unavailable`。未配置地址也返回不可重试的 `service_unavailable`。

视觉编排器捕获这些错误后将阶段状态写入内存，并拒绝发布该帧。它可以创建一个 `degraded_response` 供其他调用方使用，但当前主流水线选择更严格的“失败即不写事实”行为。此设计确保模型演进、故障和资源变化不改变已存储的查询事实。

## 检查

内部契约测试位于 `services/api/tests/test_internal_contracts.py`，覆盖无媒体引用、未配置服务与超时错误映射。运行：

```powershell
python -m unittest services.api.tests.test_internal_contracts -v
pnpm contracts:check
```

