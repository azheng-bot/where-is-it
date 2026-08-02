# 远程视频帧推送

`video-streamer` 与 `gpu-inference-api` 之间传输的是独立 JPEG 帧，不对外公开 RTSP，也不传输或保存完整视频流。GPU 接收器只保留待处理的最新帧；推流或推理变慢时，旧帧会被丢弃而不是形成队列。

## 服务边界

- `video-streamer` 部署在能访问摄像头的设备，只读取视频源并向 GPU 节点发起出站请求。
- `gpu-inference-api` 在 GPU 节点接收帧、执行视觉推理并写入业务事实。
- `web` 不参与视频传输；它只调用 GPU 包的业务 API。

视觉模型与 ASR 位于 GPU Compose 内部网络，不能用作推流目标，也不得暴露到公网。

## 配置

先启动 GPU 包，配置其 `GPU_VISION_PUBLIC_URL` 与 `VISION_PUSH_TOKEN`。然后在推流端使用同一令牌：

```env
CAMERA_SOURCE=rtsp
CAMERA_RTSP_URL=rtsp://camera.example/stream
FRAME_INGEST_URL=https://gpu.example.com/v1/frames
VISION_PUSH_TOKEN=use-the-same-long-random-secret
VISION_PUSH_TIMEOUT_SECONDS=5
```

USB 摄像头使用 `CAMERA_SOURCE=usb` 和 `CAMERA_USB_INDEX`；联调可使用 `CAMERA_SOURCE=mock-video`。完整环境变量见 [推流服务模板](../deploy/video-streamer/.env.example)。

## 传输协议

推流端调用：

```text
POST https://<gpu-host>/v1/frames
Content-Type: image/jpeg
X-Vision-Push-Token: <shared-secret>
```

启用 `VISION_PUSH_TOKEN` 后，缺少或错误的令牌必须被拒绝。成功接收返回 `202 Accepted`。生产入口应使用 HTTPS、反向代理或网关，并按来源 IP/VPN/零信任策略限制 `8001`；不要将摄像头暴露给公网。

## 启动与检查

```bash
# GPU 主机
bash deploy/gpu-inference-api/scripts/preflight-linux-gpu.sh
docker compose --env-file deploy/gpu-inference-api/.env \
  -f deploy/gpu-inference-api/docker-compose.yml up -d --build

# 摄像头边缘设备
docker compose --env-file deploy/video-streamer/.env \
  -f deploy/video-streamer/docker-compose.yml up -d --build
```

- 推流端：`GET /health/ready` 检查采集和推送状态。
- 接收器：`GET http://<gpu-host>:8001/health/ready` 仅用于受控运维网络。
- API：`GET http://<gpu-host>:8000/health/ready` 检查业务 API、接收器与 ASR 的聚合状态。

当网络中断、令牌无效或 GPU 不可用时，推流端记录失败并丢弃当前帧；它不会把历史帧当作实时帧重新提交。