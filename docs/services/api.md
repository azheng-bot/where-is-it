# 业务 API 服务

## 定位

业务 API 位于 `services/api/`，是系统事实层和唯一的业务数据写入者。它使用 FastAPI 提供公开 HTTP API，并在启动时初始化 SQLite schema 与证据目录。开发命令为 `python -m uvicorn app.main:app --app-dir . --reload --port 8000`；容器内以 `services.api.app.main:app` 在 8000 端口运行。

## 职责与边界

- 保存房间、位置、物品、别名、观测记录与证据图片。
- 接收视觉编排器的标准化观测批次，并按防抖规则把候选转化为可查询事实。
- 对文字查询做名称/别名匹配，按状态返回确定结果、歧义、未找到或推测。
- 将音频转发给独立 ASR 服务；文字查询不依赖 ASR 可用性。
- 可选调用 DeepSeek 仅润色回答，随后校验回答未改变事实。
- 不读取摄像头、不直接调用视觉模型，也不让 LLM 修改事实数据。

## 端点

| 端点 | 调用方 | 行为 |
| --- | --- | --- |
| `GET /health/live` | 部署平台 | 进程存活状态 |
| `GET /health/ready` | 部署平台 | 数据库/API 就绪信息 |
| `GET /api/room/state` | Web | 相机资源 URL、目录统计与演示视觉状态 |
| `POST /internal/observations/batch` | 视觉编排器 | 写入归一化观测和首张证据 |
| `GET /api/objects` | Web | 返回物品目录 |
| `PATCH /api/objects/{id}` | Web | 修改名称和可选别名；同房间重名返回 409 |
| `GET/PATCH /api/locations[/ {id}]` | Web | 列表或修改位置名称；同房间重名返回 409 |
| `POST /api/query` | Web | 返回 `QueryResult` |
| `GET /api/evidence/{id}` | Web | 返回已保存的证据文件 |
| `POST /api/speech/transcribe` | Web | 校验音频并代理 ASR 转写 |

应用只允许 `http://localhost:5173` 和 `http://127.0.0.1:5173` 跨域请求。`/internal/observations/batch` 没有应用层鉴权，部署时必须通过内网隔离、网关或服务认证限制访问。

## 观测写入规则

`Repository.ingest_observations` 是视觉事实入口。每个 `IncomingObservation` 包含稳定 `track_key`、名称、类别、位置、边界框与置信度。系统对新 `track_key` 先累计至 3 次命中，再创建物品，降低单帧误检直接进入目录的风险。已存在物品会更新为 `currently_detected`，写入当前/最后位置、观测与置信度。

服务只在物品尚无证据时保存一张图片：优先解码编排器携带的 `frame_image_b64`，否则复制 fixture 文件，并在 `evidence_images` 保存路径和边界框。默认 SQLite 使用 WAL 与外键约束；详细表结构见 [`../architecture.md`](../architecture.md) 的“持久化模型”。

## 查询与回答规则

查询文本会标准化并移除部分常见问法，然后匹配物品的展示名、系统名、分类和别名：

- 没有匹配：`not_found`，带少量目录建议；
- 多个匹配：`clarification`，返回候选；
- 当前检测到：返回 `current_location` 和最新证据；
- 身份待确认：返回警示，不当作确定位置；
- 当前未检测到：返回 `last_location`，并生成 `is_inference=true` 的预测位置，说明推测依据。

`AnswerComposer` 只有在 `DEEPSEEK_API_KEY` 已配置且找到唯一物品时才请求 DeepSeek。请求只带物品名、状态和当前/最后位置；返回答案必须包含正确物品名、必要的位置和正确状态措辞，否则回退本地模板。

## 配置与依赖

| 配置 | 默认值/作用 |
| --- | --- |
| `DATABASE_PATH` | 开发默认 `services/api/data/mock-where-is-it.db` |
| `EVIDENCE_DIR` | 开发默认 `services/api/data/evidence` |
| `VISION_PUBLIC_URL` | 为 Web 生成帧和视频 URL，默认 `http://127.0.0.1:8001` |
| `ASR_SERVICE_URL`、`ASR_TIMEOUT_SECONDS` | ASR 地址与代理超时 |
| `DEEPSEEK_*`、`LLM_TIMEOUT_SECONDS` | 可选回答润色服务 |
| `EVIDENCE_MAX_*`、`FRESHNESS_SECONDS`、`MISSING_GRACE_SECONDS` | 已暴露配置；当前尚未全部落实为清理/过期状态逻辑 |

Python 依赖定义在 `services/api/requirements.txt`：FastAPI、Uvicorn 与 `python-multipart`。

## 验证

```powershell
Set-Location services/api
python -m unittest discover -s tests -v
```

测试涵盖仓储行为、内部契约和 ASR 代理边界。业务 API 的主要源码入口依次是 `app/main.py`、`app/repository.py`、`app/models.py`、`app/asr.py` 和 `app/llm.py`。

