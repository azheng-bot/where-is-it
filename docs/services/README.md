# 服务文档索引

本目录按可运行服务拆分说明。系统默认以 mock 模式运行，服务间边界和 HTTP 契约在真实模型模式下保持不变。

| 服务 | 文档 | 默认端口 | 上游 | 下游 |
| --- | --- | ---: | --- | --- |
| Web | [web.md](web.md) | 5173 / 80 | 浏览器用户 | API、视觉编排器资源 |
| 业务 API | [api.md](api.md) | 8000 | Web、视觉编排器 | SQLite、ASR、可选 LLM |
| 视觉编排器 | [vision-orchestrator.md](vision-orchestrator.md) | 8001 | 相机/视频源 | API、四个视觉模型 |
| Florence | [florence.md](florence.md) | 8002 | 视觉编排器 | 无 |
| Grounding | [grounding.md](grounding.md) | 8003 | 视觉编排器 | 无 |
| SAM | [sam.md](sam.md) | 8004 | 视觉编排器 | 无 |
| Embedding | [embedding.md](embedding.md) | 8005 | 视觉编排器 | 无 |
| ASR | [asr.md](asr.md) | 8006 | 业务 API | 无 |
| 共享运行时与契约 | [shared-runtime.md](shared-runtime.md) | — | API、编排器、模型服务 | — |

所有视觉模型服务都实现同一组端点：`GET /health/live`、`GET /health/ready`、`POST /v1/infer`。请求和响应定义见 [shared-runtime.md](shared-runtime.md)。

