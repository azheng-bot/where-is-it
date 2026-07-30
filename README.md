# 在哪里（Where Is It）

单卧室、单摄像头场景的室内物品查找助手。网页会将“当前检测到”“当前未检测到后的最后出现”和“推测位置”明确分层展示，避免将推测伪装为事实。

## 开发启动

```powershell
pnpm install
pnpm dev
```

分别打开：

- Web：<http://127.0.0.1:5173>
- API：<http://127.0.0.1:8000/docs>
- Vision：<http://127.0.0.1:8001/health/ready>

Python 服务依赖见 `services/api/requirements.txt`，首次运行可执行：

```powershell
python -m pip install -r services/api/requirements.txt
```

## 验证

```powershell
pnpm build
pnpm contracts:check
Set-Location services/api; python -m unittest discover -s tests -v
```

当前为可演示的工程骨架：包含 SQLite/WAL 目录、十个演示物品、查询澄清、证据查看与目录改名。真实摄像头采集、模型适配、证据落盘与性能验收仍按 OpenSpec 任务继续实现。
## 服务拆分与运行

`pnpm dev` 会启动 Web、API、无 GPU 的 `vision-orchestrator`、四个默认 mock 的视觉模型服务，以及 ASR 服务。模型服务可以单独运行：`pnpm dev:models`；只启动产品闭环：`pnpm dev:core`。

| 服务 | 默认端口 | 默认模式 | GPU |
| --- | --- | --- | --- |
| vision-orchestrator | 8001 | mock | 否 |
| Florence / Grounding / SAM / Embedding | 8002–8005 | mock | 可选，独立配置 |
| ASR | 8006 | mock | 可选，独立配置 |

可使用 `docker compose --profile gpu up` 启动带独立 GPU 声明的模型服务；默认不假定全部模型能够同时装入一张显卡。