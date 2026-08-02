# GPU 包内部组件索引

本目录记录源码级组件的职责和接口，便于开发与故障定位；它们不是正式的独立交付服务。生产环境只部署 [三服务架构](../three-service-architecture.md) 中的 `video-streamer`、`gpu-inference-api` 与 `web`。

| 内部组件 | 文档 | 所属正式服务包 | 默认内部端口 | 说明 |
| --- | --- | --- | ---: | --- |
| 业务 API | [api.md](api.md) | `gpu-inference-api` | 8000 | 唯一业务事实写入者，对浏览器开放 |
| 视觉接收与编排 | [vision-orchestrator.md](vision-orchestrator.md) | `video-streamer` 或 `gpu-inference-api` | 8001 | 边缘侧为 pusher，GPU 侧为 receiver；由角色配置决定 |
| Florence | [florence.md](florence.md) | `gpu-inference-api` | 8002 | 私有视觉运行时 |
| Grounding | [grounding.md](grounding.md) | `gpu-inference-api` | 8003 | 私有视觉运行时 |
| SAM | [sam.md](sam.md) | `gpu-inference-api` | 8004 | 私有视觉运行时 |
| Embedding | [embedding.md](embedding.md) | `gpu-inference-api` | 8005 | 私有视觉运行时 |
| ASR | [asr.md](asr.md) | `gpu-inference-api` | 8006 | 私有语音运行时 |
| 共用运行时与契约 | [shared-runtime.md](shared-runtime.md) | `gpu-inference-api` | — | 内部 HTTP 契约与模型运行时 |

除 API `8000` 和受令牌保护的接收器 `8001` 外，不为表内内部端口设置宿主机映射。`web.md` 描述 `web` 正式服务；部署说明以 [服务运行手册](../service-runbook.md) 为准。