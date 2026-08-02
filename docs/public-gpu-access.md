# 受控 GPU 公网联调入口

公网联调只允许临时公开 `gpu-inference-api` 的 API 或受令牌保护的帧接收器。视觉模型和 CUDA ASR 为私有运行时，禁止建立隧道或发布端口。

```powershell
.\scripts\Start-PublicGpuTunnel.ps1 -Service api
# 仅在受控摄像头推流联调时：
.\scripts\Start-PublicGpuTunnel.ps1 -Service vision
```

API 隧道地址可配置为 Web 的 `PUBLIC_API_URL`。帧接收器隧道地址加 `/v1/frames` 后配置为推流端的 `FRAME_INGEST_URL`；请求必须携带正确的 `VISION_PUSH_TOKEN`。

Quick Tunnel 只适合短时排障。生产环境使用 HTTPS、认证网关和来源网络限制，并且绝不公开 `8002`–`8006`。