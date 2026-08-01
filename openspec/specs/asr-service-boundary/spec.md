# asr-service-boundary Specification

## Purpose

将语音转写从 Web 或 API 进程中分离为可独立部署的 ASR 服务，使语音能力能够按模型和 GPU 资源独立升级，同时保持文字查询与语音查询的一致语义。

## Requirements

### Requirement: API 通过 ASR 服务处理语音查询
API MUST 将有效语音媒体发送给配置的 ASR 服务，并将成功转写出的文本送入与键盘输入相同的物品查询流程。浏览器 MUST 接收可展示的转写文本或结构化转写失败结果。

#### Scenario: 成功的语音物品查询
- **GIVEN** 用户提交了一段有效的语音媒体且 ASR 服务已就绪
- **WHEN** API 获取到 ASR 服务的转写文本
- **THEN** API 使用该文本查询物品，并返回与等价键盘输入一致的状态、回答和证据结构

### Requirement: ASR 失败不改变事实回答
ASR 服务不可用、超时或无法转写时，API MUST 返回可区分的语音处理失败状态，MUST NOT 猜测用户问题或创建、修改物品位置事实。

#### Scenario: ASR 服务超时
- **GIVEN** 用户已提交语音媒体
- **WHEN** ASR 服务未在请求时限内完成转写
- **THEN** API 返回语音转写超时结果，且不执行基于猜测文本的物品查询或观测写入

### Requirement: ASR 服务可独立配置和部署
ASR 服务 MUST 通过独立服务地址、模型版本和资源配置被发现和检查；API 在服务未配置时 MUST 保持文字查询可用。

#### Scenario: 未配置 ASR 的开发环境
- **GIVEN** 开发环境未提供 ASR 服务地址
- **WHEN** 用户通过键盘发起物品查询
- **THEN** 文字查询正常完成，且系统不会因 ASR 缺失而影响视觉观测或文字回答
