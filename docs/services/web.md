# Web 前端服务

## 定位

Web 是用户唯一直接操作的界面，使用 React 19、TypeScript、Vite 和 Tabler Icons 构建。源代码位于 `apps/web/`，应用入口为 `src/main.tsx`，主要页面状态与组件集中在 `src/App.tsx`，HTTP 调用封装在 `src/api.ts`。

开发时 Vite 默认监听 5173；Docker 镜像在构建阶段运行 `pnpm --filter @where-is-it/web build`，由 Nginx 在 80 端口提供静态文件。

## 职责与边界

- 提交文本查询、展示结构化查找结果与证据图。
- 在浏览器端录制音频并调用 API 转写；不直接调用 ASR 服务。
- 展示物品/位置目录，支持物品改名。
- 通过视觉编排器提供的公开 URL 显示静态帧或 mock MP4 预览。
- 使用浏览器 Web Speech API 播报已返回的答案。
- 不保存业务事实、不访问 SQLite、不调用视觉模型，也不决定物品状态。

## 页面与交互

| 页面 | 已实现功能 | 依赖 API |
| --- | --- | --- |
| 查找 | 文本查询、约 1.8 秒麦克风录音、转写结果、歧义选择、证据弹窗、推测位置、播报 | `POST /api/query`、`POST /api/speech/transcribe`、`GET /api/room/state` |
| 物品目录 | 物品列表、状态、位置、置信度、物品名称编辑 | `GET/PATCH /api/objects` |
| 位置目录 | 位置列表、当前关联物品数、选择态、相机预览 | `GET /api/locations` |
| 历史记录 | 当前为占位页，未接入观测历史 | 无 |

查询页面完全依据 `QueryResult.status`、`predictions` 和 `evidence` 渲染：`currently_detected` 显示当前检测，`not_currently_detected` 显示最后确定位置及单独的“推测”卡片，`identity_uncertain` 不展示确定位置；多候选状态要求用户选择具体物品。

## API 集成与配置

当前 `src/api.ts` 将业务 API 基址写死为 `http://127.0.0.1:8000`。`GET /api/room/state` 返回的 `frame_url` 和 `stream_url` 用于加载视觉预览；视频加载失败时会自动回退到静态图片。

这适合本机开发，但不适合直接生产部署：容器中的浏览器仍会把 `127.0.0.1` 理解为访问者本机。生产环境应将 API 基址改为构建期环境变量或同源反向代理，并同步调整 API CORS 策略。

Web 会向 `/api/speech/transcribe` 上传 `FormData(audio)`，并会先检查 `navigator.mediaDevices.getUserMedia` 与 `MediaRecorder` 的浏览器能力。录音失败、权限被拒绝或服务失败时，界面保留文字输入路径。

## 启动、构建与检查

```powershell
pnpm --filter @where-is-it/web dev
pnpm --filter @where-is-it/web build
pnpm --filter @where-is-it/web lint
pnpm --filter @where-is-it/web test
```

前端依赖 `@where-is-it/contracts` 提供 `CatalogObject`、`QueryResult` 和状态枚举的 TypeScript 类型。该包的枚举一致性可通过根目录 `pnpm contracts:check` 检查。

## 关键限制

- 位置页面的“编辑区域”按钮尚未实现对应操作；后端位置改名接口已存在。
- 历史记录页尚未展示 `observations` 数据。
- 前端不刷新相机状态；启动时只读取一次 `/api/room/state`。
- Nginx 镜像没有内置 API 反向代理配置，部署时需要外层网关或额外配置。

