# Embedding 向量模型服务

## 定位

Embedding 服务位于 `services/embedding/`，默认监听 8005，入口使用 `create_model_app("embedding")`。它为每个目标区域计算 DINOv2 图像向量，设计上用于未来的跨帧身份确认、相似物匹配或检索增强；当前产品闭环尚未持久化或消费其返回向量。

## HTTP 接口

该服务与其他视觉模型共享端点：`GET /health/live`、`GET /health/ready`、`POST /v1/infer`。请求必须遵循 `v1` `InferenceRequest` 并提供图像；`payload.detections` 可携带来自 SAM 的带框条目。公共协议与错误码见 [shared-runtime.md](shared-runtime.md)。

## 推理行为

真实 `EmbeddingAdapter` 默认模型为 `facebook/dinov2-small`，可通过 `EMBEDDING_MODEL` 覆盖。对每个 detection：

1. 将归一化 `[x, y, width, height]` 转为原图裁切区域；
2. 用 `AutoImageProcessor` 和 `AutoModel` 前向推理；
3. 取 `pooler_output[0]`，没有时回退 `last_hidden_state[0, 0]`；
4. L2 归一化后输出浮点向量、维数、标签和原边界框。

结果结构为 `{"embeddings": [{"label": "...", "box": [...], "values": [...], "dimensions": N}]}`。检测为空时会为整帧创建一个默认裁切项。mock 模式返回 `{"embeddings": [], "dimensions": 0}`。

视觉编排器会在 SAM 成功后调用本服务，但不会读取响应以构建入库观测。因此 Embedding 失败会依当前严格流水线策略阻止整帧发布；向量本身不会写 SQLite。

## 配置与运行

| 配置 | 说明 |
| --- | --- |
| `MODEL_MODE` | 默认 mock；真实时加载 DINOv2 |
| `MODEL_DEVICE` / `EMBEDDING_DEVICE` | 运行设备 |
| `EMBEDDING_MODEL` | 模型 ID |
| `MODEL_CACHE_DIR` | 模型缓存目录 |
| `MODEL_MAX_CONCURRENCY` | 推理槽上限，默认 1 |
| `EMBEDDING_READY` / `MODEL_READY` | readiness 控制 |

镜像与其他视觉模型相同，含 Pillow、Torch 和 Transformers；可用 `pnpm --filter @where-is-it/embedding dev` 或 Compose profile 启动。

## 演进注意

若未来将向量用于稳定身份，需先定义向量存储、版本、距离阈值、隐私/容量控制和误匹配回退策略。任何相似度判断仍应以 API 的观测规则决定是否成为事实，而不能让模型服务直接修改物品位置。

