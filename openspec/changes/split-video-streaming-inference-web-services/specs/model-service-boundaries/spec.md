## MODIFIED Requirements

### Requirement: 视觉运行时作为 GPU 服务的私有组件
系统 MUST 将视觉编排、Florence、Grounding、SAM 和 Embedding 作为 GPU 推理 API 服务内部受管理的运行时组件。GPU 服务 MUST 不要求将任一组件作为用户需要单独部署的产品服务；各组件 MUST 不承担物品、证据或用户查询事实的持久化写入。

#### Scenario: 单个视觉组件不可用
- **GIVEN** GPU 推理 API 服务和其 API 进程处于可用状态
- **WHEN** 某个内部视觉组件未就绪或调用失败
- **THEN** GPU 服务返回可区分的服务状态或降级结果，且 API 中既有的物品与证据记录不被修改

### Requirement: GPU 服务聚合视觉运行时健康状态
GPU 推理 API 服务 MUST 分别报告自身及每个内部视觉组件的存活和就绪状态；服务整体就绪状态 MUST 反映处理新帧所需的最低组件集合是否可接受推理请求。内部组件的诊断信息 MAY 仅在私有网络或受控运维接口中提供。

#### Scenario: 模型尚未加载完成
- **GIVEN** GPU 服务进程已经启动但 Florence 运行时尚未可用
- **WHEN** 部署系统请求 GPU 服务的健康状态
- **THEN** 存活检查成功且就绪检查返回未就绪或降级状态，并指出 Florence 未准备完成
