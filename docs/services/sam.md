# SAM 分割模型服务

## 定位

SAM 服务位于 `services/sam/`，默认监听 8004，入口使用 `create_model_app("sam")`。它将 Grounding 的目标检测框转换为图像分割结果，并向编排器提供每个目标的有效掩码面积。服务本身没有业务数据库、状态写入或外部模型编排职责。

## 接口与契约

服务通过共享模型运行时提供：

- `GET /health/live`
- `GET /health/ready`
- `POST /v1/infer`

`/v1/infer` 使用 `v1` 内部契约。请求中必须有图像引用或 `frame_jpeg_b64`；业务参数 `payload.detections` 是包含 label、归一化 `box` 与可选 confidence 的数组。公共错误语义、请求时限与并发限制见 [shared-runtime.md](shared-runtime.md)。

## 推理行为

真实 `SamAdapter` 默认加载 `facebook/sam2.1-hiera-tiny`（可由 `SAM_MODEL` 覆盖）。它会：

1. 将每个 `[x, y, width, height]` 归一化框转换为图片像素坐标；
2. 用 `Sam2Processor` 与 `Sam2Model` 进行单掩码推理；
3. 为每个输入检测返回保留原 label、box、confidence 的 segment，并计算 `mask_area`（掩码像素平均占比）。

输出形如 `{"segments": [{"label": "keys", "box": [...], "confidence": 0.9, "mask_area": 0.05}]}`。没有有效检测时返回空 `segments`。mock 模式在每个传入检测上附加 `mask_area: 1`，用于验证服务调用边界。

视觉编排器只保留 `mask_area > 0` 的条目，才会继续生成观测。因此 SAM 作为几何有效性关口，但当前没有实现掩码文件保存或更高阈值的面积质量筛选。

## 配置与部署

| 配置 | 说明 |
| --- | --- |
| `MODEL_MODE` | 默认 mock；真实模式加载 SAM 2 |
| `MODEL_DEVICE` / `SAM_DEVICE` | 运行设备 |
| `SAM_MODEL` | 模型 ID |
| `MODEL_CACHE_DIR` | Hugging Face 缓存位置 |
| `MODEL_MAX_CONCURRENCY` | 推理并发上限，默认 1 |
| `SAM_READY` / `MODEL_READY` | 就绪开关 |

Docker 镜像安装 Pillow、Torch、Transformers；Compose GPU profile 可将其独立调度至 NVIDIA GPU。启动命令为 `pnpm --filter @where-is-it/sam dev`。

## 故障影响

如果 SAM 未就绪、模型失败或超时，编排器将该阶段标记为失败，整帧不发布到 API，而不是将 Grounding 的未分割框作为已确认位置保存。

