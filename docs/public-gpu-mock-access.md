# 让线上 GPU 服务访问本地 mock

本项目的 mock 服务默认只监听本机回环地址，不能被外网直接访问。使用 Cloudflare Quick Tunnel 可以在不开放路由器端口、也不修改 Windows 防火墙的情况下，为指定的 mock 服务创建一个临时 HTTPS 地址。

## 使用方法

先启动目标服务。例如，启动四个视觉模型 mock：

```powershell
pnpm dev:models
```

新开一个 PowerShell 窗口，在项目根目录运行：

```powershell
.\scripts\Start-PublicMockTunnel.ps1 -Service florence
```

脚本会在首次使用时下载 `cloudflared` 到 `.tools`，随后输出一个形如 `https://xxxxx.trycloudflare.com` 的临时地址。把该地址配置为线上 GPU 服务的基础地址；推理接口为：

```text
https://xxxxx.trycloudflare.com/v1/infer
```

可选服务和默认端口：

| 服务 | 参数 | 端口 |
| --- | --- | --- |
| Florence mock | `florence` | 8002 |
| Grounding mock | `grounding` | 8003 |
| SAM mock | `sam` | 8004 |
| Embedding mock | `embedding` | 8005 |
| Vision mock | `vision` | 8001 |
| ASR mock | `asr` | 8006 |
| 产品 API | `api` | 8000 |

例如：` .\scripts\Start-PublicMockTunnel.ps1 -Service grounding `。

## 注意事项

- 每次启动 Quick Tunnel 的公网地址都会变化；它适合联调，不适合稳定生产入口。
- 隧道只转发一个端口。四个模型服务需要分别建立四条隧道，或者由线上 GPU 服务只调用其中一个指定服务。
- 此公网地址没有业务层鉴权；只应在短时调试中发给可信的 GPU 任务。完成后按 `Ctrl+C` 关闭隧道。
- 线上服务调用 `/v1/infer` 时必须遵守项目的 `v1` 推理契约，并携带 `frame_ref` 或 `media_ref`。
