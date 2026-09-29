# M17 代码生成与网页原型

## 用途、结构与接口

`service.py` 的 `DevelopmentService` 只保存待审查草稿并逐文件应用；`chat.development.context/generate/draft/apply` 是会话接口。Desktop 的 `M17Cards.tsx` 提供资料选择、完整差异、源码与原型预览，主进程在云端发送及每个文件写入前分别弹原生确认框。`context` 仅读取用户明确选择的已授权项目内最多 3 个 UTF-8 文本文件（每个 8 KiB）；也可选择当前会话最多 2 个 M12/M13 不可变来源，经 M06 检索取有界引用片段，或一条已保存 M15 回答/M16 引用记录。M16 只追溯其 M15 原回答，不读取后续修改的导出文件。预览显示实际拟发送内容，需求、选择与内容共同绑定 revision。

`generate` 只调用 Mission 固定 Computer `glm-5.3-flashx` / `https://open.bigmodel.cn/api/paas/v4`，请求 JSON 草稿，不执行输出。首批代码为 TypeScript/React/Vite 或原生 HTML/CSS/JS；最多 12 个文本文件、总计 64 KiB、单文件 24 KiB。允许创建文件和修改已授权项目中的既有文件；每个文件显示完整源码与统一差异。`apply` 再核对授权根、草稿版本、目标身份和 SHA256，逐文件写入、读回，已变化的目标拒绝覆盖。草稿存于本地 SQLite，重启后目录授权失效，须重新授权同一根。生成成功只表示提案有效，不代表类型检查或运行成功。

`prototype` 首批为 1–4 页可交互网页：受限结构化页面、导航与表单反馈。模型只给文案和结构；服务生成可编辑 `index.html`、`style.css`、`app.js`。应用内预览由 React 固定组件转义呈现，不加载或执行生成的 HTML/JS；源码写入仍逐文件确认。所有页面标明演示数据，未连接真实业务；不安装依赖、启动服务、运行代码或部署。

## 依赖、运行与验证

沿用当前会话目录授权、Computer 路径策略、SQLite、M06/M12/M13 证据及固定模型内存凭据；开发密钥只由主进程读取被忽略的根 `.env.local`。没有 Computer Key 时明确失败，不切换供应商。开发版启动见根 README。示例：选择一个自建合成项目目录 → 填需求并选择少量上下文 → 预览实际正文 → 原生确认发送 → 审核每个差异和原型预览 → 分别确认写入。云端发送仅针对经预览的内容；目录选择本身不等于上传许可。

验证命令见 `docs/PROGRESS.md` M17 节。日常 pytest/Vitest/Playwright 使用合成项目和模型 mock；显式 `backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_m17_development.py --run-live` 才在测试进程读取 Computer Key 并发送两条短合成需求。模型代码可能含错误或不安全逻辑，用户需在独立环境自行审查、检查与运行；本模块没有执行授权。外部进程在身份复核与操作之间更改路径仍有极窄竞态，异常时应检查实际文件和草稿状态。
