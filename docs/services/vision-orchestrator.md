# 视觉编排器服务

## 定位

视觉编排器位于 `services/vision-orchestrator/`，监听 8001。它连接摄像头或模拟媒体，负责串联四个视觉模型服务、归一化最终观测并上报业务 API。它是视觉流水线的控制面，而不是数据库或模型权重的持有者。

开发命令：

```powershell
Set-Location services/vision-orchestrator
python -m uvicorn app.main:app --reload --port 8001
```

## 输入与输出

输入源由 `CAMERA_SOURCE` 决定：

| 值 | 行为 |
| --- | --- |
| `mock-video`（默认） | mock 模式生成固定观测；真实模式从内置 MP4 读取帧 |
| `file` / `video` | 从 `CAMERA_VIDEO_PATH` 读取并循环播放 |
| `usb` | 使用 `CAMERA_USB_INDEX` 打开 OpenCV 设备 |
| `rtsp` | 使用 `CAMERA_RTSP_URL` 打开网络流 |

输出包括：向 API 的 `POST /internal/observations/batch`、给浏览器的 `GET /api/camera/frame` 静态帧和 `GET /api/camera/stream` mock MP4。相机状态可由 `GET /internal/camera/status` 读取。

## 运行循环

服务启动时创建 daemon 线程，按 `DISCOVERY_INTERVAL_SECONDS`（也兼容 `MOCK_FRAME_INTERVAL_SECONDS`，默认 0.7 秒）执行一次发布：

1. `VISION_MODE=mock` 时，`MockFrameSource` 输出十个固定物品、fixture 图片和递增帧号；四个阶段状态记为 `mock`。
2. 真实模式使用 OpenCV 获取 JPEG、Base64 编码并创建唯一 `request_id`。
3. 依序请求 Florence、Grounding、SAM、Embedding，每个请求使用内部 `v1` 契约并附带帧 JPEG、8 秒默认阶段时限和来源信息。
4. Grounding 的有效检测进入 SAM；只有 `mask_area > 0` 的分割结果会形成标准化观测。`TrackStore` 以相同 label 加 IoU ≥ 0.35 分配/复用 `track_key`。
5. 若所有需要阶段成功且有有效观测，调用 API 入库；任一阶段超时、契约错误、服务不可用、降级或无结果时，本帧不发布。

Embedding 当前已被调用以保持流水线边界完整，但其向量不参与观测构建和身份匹配；跟踪仍是标签 + IoU 的轻量实现。

## 端点与健康状态

| 端点 | 说明 |
| --- | --- |
| `GET /health/live` | 编排器进程存活 |
| `GET /health/ready` | 返回当前模式、输入源状态与每一视觉阶段最后状态；真实模式必须相机已连接 |
| `POST /v1/frames/process` | 手动处理并发布一次帧，返回是否接受、模式和阶段状态 |
| `GET /internal/camera/status` | 当前源、帧计数、最近时间、错误与阶段状态 |
| `GET /api/camera/frame` | 返回 fixture PNG |
| `GET /api/camera/stream` | 仅在 `mock-video` 源时返回内置 MP4 |

`last_stages` 会记录 `ok`、`mock`、`deadline_exceeded`、`contract_mismatch` 等阶段结果，适合监控或排障。它不是持久化历史，服务重启会清空。

## 关键配置

| 配置 | 作用 |
| --- | --- |
| `API_INTERNAL_URL` | 观测上报目标，容器默认 `http://api:8000` |
| `VISION_MODE` | `mock` 或真实模式 |
| `FLORENCE_SERVICE_URL` 等 | 四个内部模型服务的基址 |
| `VISION_STAGE_TIMEOUT_MS` | 单个模型调用期限，默认 8000 ms |
| `VISION_PROMPTS` | Florence 无候选时的候选标签回退列表 |
| `CAMERA_*` | 输入类型、文件/RTSP/USB 参数、fixture 与视频路径 |
| `FRAME_JPEG_QUALITY` | OpenCV JPEG 质量，默认 85 |

容器安装 FastAPI、Pydantic、OpenCV Headless 和 multipart；本地真实视频模式同样需要 OpenCV 可用。

## 验证与故障边界

`tests/test_pipeline.py` 验证“只有已验证的分割结果会发布”，以及超时/契约不匹配时流水线返回空结果。运行：

```powershell
python -m unittest discover -s services/vision-orchestrator/tests -v
```

该服务不应绕过 API 直接写 SQLite；一旦模型阶段不可用，已有目录、观测和证据必须保持不变。

