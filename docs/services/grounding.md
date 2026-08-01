# Grounding 模型服务

## 定位

Grounding 服务位于 `services/grounding/`，默认监听 8003，入口使用 `create_model_app("grounding")`。它在真实视觉流水线中接收 Florence 输出的候选标签，对当前帧做零样本目标定位与标签验证。它不持久化业务数据。

## HTTP 接口与公共运行时

服务端点为 `GET /health/live`、`GET /health/ready` 和 `POST /v1/infer`，字段、版本校验、并发上限和错误代码均由共享运行时实现，详见 [shared-runtime.md](shared-runtime.md)。编排器是它的唯一预期调用者，默认地址为 `http://grounding:8003`（容器）或 `http://127.0.0.1:8003`（本机）。

## 推理输入输出

真实 `GroundingAdapter` 默认使用 `IDEA-Research/grounding-dino-tiny`，可通过 `GROUNDING_MODEL` 覆盖。输入需要图像以及 `payload.candidates` 字符串数组：

1. 适配器将候选用句点串接成 zero-shot 文本提示。
2. Grounding DINO 产生边界框、文本标签和分数。
3. 适配器将像素框转化为 `[x, y, width, height]` 的 0–1 归一化坐标，返回 `result = { verified: true, detections: [...] }`。

可选阈值是 `payload.box_threshold`（默认环境变量 `GROUNDING_BOX_THRESHOLD`，默认 0.35）和 `payload.text_threshold`（默认 `GROUNDING_TEXT_THRESHOLD`，默认 0.25）。候选为空时返回空检测和 `verified: true`，不会制造结果。

mock 运行时直接回传 `payload.detections`；因此 mock 可用于连接/契约调试，但真实输入通常由前一 Florence 阶段提供。

## 配置与部署

| 配置 | 说明 |
| --- | --- |
| `MODEL_MODE` | 默认 `mock`；设置为非 mock 值时加载真实适配器 |
| `MODEL_DEVICE` / `GROUNDING_DEVICE` | CPU 或 CUDA 设备 |
| `GROUNDING_MODEL` | Hugging Face 模型 ID |
| `MODEL_CACHE_DIR` | 模型缓存目录/卷 |
| `MODEL_MAX_CONCURRENCY` | 同时推理请求数，默认 1 |
| `GROUNDING_READY` / `MODEL_READY` | 显式控制 readiness |

Docker 镜像带 FastAPI、Pillow、Torch 和 Transformers。Compose 的 GPU profile 为该服务单独声明 NVIDIA GPU 设备；CPU profile 则设置为 `cpu`。

## 失败影响

Grounding 是真实流水线的验证关口。若它不可用、超时、拒绝请求或没有通过到 SAM 的结果，编排器停止该帧，API 不会更新物品位置或证据。已有持久化事实不受影响。

