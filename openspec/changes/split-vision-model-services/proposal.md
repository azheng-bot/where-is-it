## Why

当前视觉识别、目标定位、分割、向量检索和语音识别将会共享同一个本地服务与运行环境，难以按模型的显存需求独立部署、扩缩容和升级。随着 VLM 服务迁移到线上，需要先建立清晰的服务边界，保证首版室内物品查找的 API 和事实状态不受单个模型故障或版本变化影响。

首版范围是单摄像头、单卧室的物品查找助手；本变更只定义和落地可独立部署的模型服务边界、内部调用契约和本地演示编排，不改变面向用户的“当前检测 / 最后出现 / 推测”回答语义。模型准确率优化、多摄像头和生产级集群调度不在本次范围内。

## What Changes

- 将现有视觉入口调整为不依赖 GPU 的 `vision-orchestrator`，负责接收帧、并行/串行编排模型调用、归一化结果并向 API 上报观测。
- 新增独立的 Florence、Grounding、SAM、Embedding 和 ASR 服务；每个服务独立暴露存活/就绪检查与版本化内部推理接口。
- 定义携带请求关联 ID、时限、模型版本和帧/媒体引用的内部推理契约，避免在服务之间复制写入物品事实。
- 将摄像头 mock 图和固定识别结果保留为 orchestrator 可替换的本地演示适配器，使前端闭环在未配置真实模型时仍可运行。
- 让 API 通过 ASR 服务处理语音输入；API 继续作为物品观测、证据和查询事实的唯一持久化写入方。
- 提供每个模型服务的地址、资源配置、超时与降级配置，为后续容器化线上部署和按 GPU 服务独立扩缩容做准备。

## Capabilities

### New Capabilities

- `model-service-boundaries`: 为视觉模型服务和无 GPU 的视觉编排服务定义独立部署、健康检查、资源隔离和职责边界。
- `internal-inference-contract`: 定义 API、编排器与模型服务之间版本化、可追踪且可降级的内部推理请求和结果契约。
- `asr-service-boundary`: 将语音转写作为可独立配置和部署的 ASR 服务接入产品查询流程。

### Modified Capabilities

- 无。

## Impact

- 影响 `services/vision`、`services/api` 和新增的 Florence、Grounding、SAM、Embedding、ASR 服务目录及其配置。
- 新增内部 HTTP API、模型服务环境变量、健康检查与本地/线上编排配置；浏览器公开 API 保持兼容。
- 需要以共享 contracts、异步/HTTP 客户端、容器运行时和模型镜像依赖支撑后续上线；DeepSeek 仍为外部云端 LLM，不纳入 GPU 模型服务。
