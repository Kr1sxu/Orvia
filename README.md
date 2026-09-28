# 序航 Orvia

面向 Windows 的本地桌面多 Agent 工作助手。MVP 先完成需要用户审批的桌面文件整理。

当前 **M08 安装包与整体验收已完成本机验证**，尚不是完整文件整理产品。实际完成与测试、本地 commit 和用户手动推送状态以 [进度记录](docs/PROGRESS.md) 为准。

## 本轮能力

Electron + React + TypeScript 通过受限 IPC 与 Python 3.12 私有 JSON Lines 通信。界面可查看三个固定模型与凭据状态，创建任务草稿；SQLite 保存草稿、模型快照、文件操作账本、LangGraph checkpoint 和任务范围上下文，重启仍可读取。后端已具备需主进程授权的三角色合成编排、轻量检索与 Browser 私有只读接口，当前 UI 尚未开放目录选择和写操作按钮。
开发模式由主进程只读 `.env.local`；发布模式支持 safeStorage 加密保存与删除，无明文回退。三个模型已通过合成文本和结构化工具调用验证；界面不自动调用模型或执行任务。渲染端没有 Node、通用 IPC、密钥读取、路径或命令执行接口。

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
窗口出现后确认后端在线、查看三个角色配置，在“草稿名称”输入合成名称并保存。关闭窗口后重启，草稿仍在。保存草稿只写应用数据库，不整理任何用户文件。
开发数据默认放在被忽略的 `.orvia/`；更新开发密钥后需要重启应用。代码更新后先同步 uv/npm 依赖并重新构建。
Electron 固定启动 `backend/.venv/Scripts/python.exe`，不通过 PATH 搜索解释器。缺少环境时按上述步骤安装，不会自动换用其他 Python。
目前是源码开发启动，不是安装包；PyInstaller 与 electron-builder 留到 M08。

## 目录

| 位置 | 用途 |
|---|---|
| `apps/desktop/` | 主进程、preload、React 界面、桌面单元测试 |
| `backend/` | Python 协议服务、后端单元测试 |
| `contracts/` | Pydantic 导出的 JSON Schema 与跨语言约束 |
| `tests/integration/` | 跨进程集成验证 |
| `tests/e2e/` | Electron 真实窗口端到端验证 |
| `docs/` | 架构、开发清单、事实进度 |
| `artifacts/test-results/M07/` | 本轮本地测试证据，不提交 Git；历史证据原地保留 |

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

上述命令是测试入口，应按改动选择具体文件；M02 实际最小命令与证据见 PROGRESS。日常自动测试不调用真实模型；`backend/tests/live_model_preflight.py` 和 `live_model_capabilities.py` 只有显式 `--run-live` 才会使用真实 Key 发送合成内容并产生供应商费用，不属于默认 pytest。

## 目标架构与限制

Main Agent 负责规划、委派和证据判断，Computer Agent 负责受限本地任务，Browser Agent 负责搜索与只读网页访问。已实现固定模型配置、合成 LangGraph 流程、文件权限网关、审批账本、轻量 RAG 和受限网页读取；当前 UI 仍以配置与草稿为主。

开发 Key 仅放根目录被忽略的 `.env.local`，变量名见 `.env.example`。不得提交 Key 或把环境文件打包。三个角色固定模型配置见架构文档；Tavily 缺失时搜索明确不可用；开发主进程读取可选 TAVILY_API_KEY，发布通过 safeStorage。Browser 接口、合成试用与运行时限制见 [模块 README](backend/src/orvia_backend/browser/README.md)。创建草稿本身不代表开始执行任务。
首版不删除、覆盖、清理系统或执行任意脚本。PDF/OCR、PPT、标书、完整行业调研、代码生成、原型、桌面点击和浏览器写操作属于后续能力。

## 提交与远端同步

按最新开发约定，Agent 每轮完成一个模块后创建本地 commit 并停止，push 由用户手动执行。未推送不影响已实现、验证、记录和提交的模块完成；历史推送结果仅作为历史证据保留。

M07 配套 Chromium Headless Shell 已于 2026-09-28 重试安装成功，默认动态读取的 4 项合成测试通过，无需切换 Edge。未验证真实 Tavily/互联网网页兼容性，M08 本机验收已完成，独立无开发环境 Windows 机器仍待补验。
