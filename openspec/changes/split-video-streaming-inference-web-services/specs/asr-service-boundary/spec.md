## MODIFIED Requirements

### Requirement: API 通过 GPU 服务内部 ASR 运行时处理语音查询
GPU 推理 API 服务 MUST 将有效语音媒体交给其内部配置的 ASR 运行时，并将成功转写出的文本送入与键盘输入相同的物品查询流程。浏览器 MUST 接收可展示的转写文本或结构化转写失败结果。

#### Scenario: 成功的语音物品查询
- **GIVEN** 用户提交了一段有效的语音媒体且 GPU 服务的 ASR 运行时已就绪
- **WHEN** API 获取到 ASR 服务的转写文本
- **THEN** API 使用该文本查询物品，并返回与等价键盘输入一致的状态、回答和证据结构

### Requirement: ASR 运行时作为 GPU 服务的受管理依赖
ASR 运行时 MUST 通过 GPU 推理 API 服务的内部模型版本和资源配置被发现和检查，而不作为需要单独部署或向浏览器公开的产品服务。ASR 运行时未就绪时，GPU 服务 MUST 保持文字查询可用，并通过其健康状态报告语音能力不可用。

#### Scenario: ASR 尚未就绪的开发环境
- **GIVEN** GPU 推理 API 服务未提供可用的 ASR 运行时
- **WHEN** 用户通过键盘发起物品查询
- **THEN** 文字查询正常完成，且系统不会因 ASR 缺失而影响视觉观测或文字回答
