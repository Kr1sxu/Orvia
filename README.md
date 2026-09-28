# 序航 Orvia

面向 Windows 的本地桌面多 Agent 工作助手。MVP 先完成需要用户审批的桌面文件整理。

当前 **M01 工程骨架与 Electron-Python 通信已通过本机验收**，不是完整文件整理产品。实际完成与测试、commit、push 状态以 [进度记录](docs/PROGRESS.md) 为准。

## 本轮能力

Electron + React + TypeScript 窗口通过固定健康检查 IPC 调用 Python 3.12 子进程，使用私有 UTF-8 stdio JSON Lines 完成握手与健康响应。
渲染端不暴露 Node、通用 IPC、路径或命令执行接口。M01 不读取 `.env.local`，不调用模型，不操作用户真实文件。

## 开发启动

开发环境：Windows x64、Node.js >=22.12（已验证 24.19.0）、npm 11、Python 3.12。以下命令在项目根目录 PowerShell 执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install uv==0.12.19
.\.venv\Scripts\uv.exe sync --project backend --locked
npm ci
npm run setup:electron
npm run build
npm start
```

Electron 44 需要通过 `npm run setup:electron` 显式下载运行时，`npm ci` 不会自动完成此步骤。
窗口出现后点击健康检查按钮，预期返回后端在线状态。关闭窗口后应用退出并关闭自有后端。
Electron 固定启动 `backend/.venv/Scripts/python.exe`，不通过 PATH 搜索解释器。缺少环境时按上述步骤安装，不会自动换用其他 Python。
目前是源码开发启动，不是安装包；PyInstaller 与 electron-builder 留到 M08。

## 目录

| 位置 | 用途 |
|---|---|
| `apps/desktop/` | 主进程、preload、React 界面、桌面单元测试 |
| `backend/` | Python 协议服务、后端单元测试 |
| `tests/integration/` | 跨进程集成验证 |
| `tests/e2e/` | Electron 真实窗口端到端验证 |
| `docs/` | 架构、开发清单、事实进度 |
| `artifacts/test-results/M01/` | 本轮本地测试证据，不提交 Git |

参见 [开发约定](AGENTS.md)、[架构](docs/ARCHITECTURE.md)、[开发清单](docs/DEVELOPMENT_PLAN.md) 和各模块 README。

## 验证

按改动范围选择最低必要级别，不要求每次全部执行。E2E 前先完成构建。

```powershell
npm run check
npm run test:unit
.\.venv\Scripts\uv.exe run --project backend pytest backend/tests --junitxml=artifacts/test-results/M01/backend-junit.xml
npm run test:integration
npm run test:e2e
```

测试结果写入 `artifacts/test-results/M01/`，实际命令和结论见 PROGRESS。M01 测试不调用真实模型；真实进程、真实窗口测试与模拟场景须在记录中区分。

## 目标架构与限制

Main Agent 负责规划、委派和证据判断，Computer Agent 负责受限本地任务，Browser Agent 负责搜索与只读网页访问。LangGraph、SQLite、凭据配置、文件权限网关和 RAG 属于后续模块，并未因骨架存在而实现。

开发 Key 仅放根目录被忽略的 `.env.local`，变量名见 `.env.example`。不得提交 Key 或把环境文件打包。三个角色固定模型配置见架构文档；Tavily 未配置时搜索不可用。
首版不删除、覆盖、清理系统或执行任意脚本。PDF/OCR、PPT、标书、完整行业调研、代码生成、原型、桌面点击和浏览器写操作属于后续能力。
