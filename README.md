# 序航 Orvia

面向 Windows 的本地桌面多 Agent 工作助手。MVP 先完成需要用户审批的桌面文件整理。

当前开发到 **M12 Browser 搜索、来源与证据工作流**。M08 安装包为历史版本，本轮源码尚未重新打包；实际完成与测试、本地 commit 和用户手动推送状态以 [进度记录](docs/PROGRESS.md) 为准。

## 本轮能力

Electron + React + TypeScript 通过受限 IPC 与 Python 3.12 私有 JSON Lines 通信。界面提供新建/历史对话、输入框、目录授权、只读结果、计划审批、核验和受限撤销；SQLite 保存会话消息、固定模型快照、动作账本和 LangGraph checkpoint。对话重开不恢复文件权限，必须重新选择目录。
主动发送目录任务时调用固定 Main 模型，最多三次请求；必要对话与已授权文件元数据发往 Main 云服务，不自动上传文件正文。Computer 通过程序工具执行，Browser 通过会话内搜索、公开 URL 读取和来源检索提供只读证据。开发主进程读取 `.env.local`，发布模式使用 safeStorage，无明文回退。渲染端没有 Node、通用 IPC、密钥读取、任意路径或命令执行能力。

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
窗口出现后在“设置”检查固定模型凭据。点击“选择目录”，选择自己创建的合成测试目录，可查看列表、属性、搜索和空间统计；发送“将 a.txt 重命名为 b.txt”后核对计划，再点击“批准此版本并执行”。聊天中回复“同意”不会执行。完成后可撤销该会话最近一次变更；重启后需重新授权原目录。未授权时发送需求会请求选择目录，选择后请再次发送目标。
开发数据默认放在被忽略的 `.orvia/`；更新开发密钥后需要重启应用。代码更新后先同步 uv/npm 依赖并重新构建。
Electron 固定启动 `backend/.venv/Scripts/python.exe`，不通过 PATH 搜索解释器。缺少环境时按上述步骤安装，不会自动换用其他 Python。
上述方式运行最新源码；M08 已有历史安装包，未包含本轮对话界面。M12 不重新发布安装器。

M11 可在模型等待期间“取消规划”，取消不回滚文件，也不能打断审批执行。连接失败后点击“重新连接”，核对任务状态并重新授权目录；不会自动重发模型或文件动作。模型失败后可明确点击“重新尝试规划”，这会发起新的模型请求；不确定的文件变更请先查看账本与核验结果。长消息、长列表可展开，阅读历史时使用“查看最新消息”返回底部。

## 网页来源试用（M12）

在同一个对话输入框选择需求类型，再输入并发送：

- **搜索网页**：发送最多500字搜索词；需要 Tavily 凭据，缺失会明确显示不可用，不返回假结果。
- **读取网页**：发送一个公开 HTTP(S) URL，无需目录授权、模型或搜索凭据。搜索摘要卡片的“读取此网页”也会发起一次显式读取。
- **询问已有来源**：输入最多200字关键词，例如“许可”。复用 M06 的本地全文检索，返回当前会话原文片段及引用，不调用模型生成答案；自然语言长问句可能无匹配。
- 展开来源卡片点“查看证据”，查看 URL、标题、访问时间、正文、SHA256、截断与错误。重启后来源可读，但目录权限不恢复。

来源来自外部，不代表事实已经核实。搜索摘要与网页正文分别保存，内容变化产生独立证据版本；重复版本保留首次访问时间，新请求记录本次尝试时间。网页内容不进入文件规划模型，不会触发文件审批。来源目录最多20项且受12 KiB限制，快照仍为46 KiB；正文最多8000个 Unicode 字符，长文按需展开。搜索/读取无自动重试或取消入口，网络故障请先核对已保存证据再明确重试。全部 M12 验证使用合成网络与临时数据库，未验证真实 Tavily/互联网兼容性。

## 目录

| 位置 | 用途 |
|---|---|
| `apps/desktop/` | 主进程、preload、React 界面、桌面单元测试 |
| `backend/` | Python 协议服务、后端单元测试 |
| `contracts/` | Pydantic 导出的 JSON Schema 与跨语言约束 |
| `tests/integration/` | 跨进程集成验证 |
| `tests/e2e/` | Electron 真实窗口端到端验证 |
| `docs/` | 架构、开发清单、事实进度 |
| `artifacts/test-results/M12/` | 本轮本地测试证据，不提交 Git；历史证据原地保留 |

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

Main Agent 负责规划、委派和证据判断，Computer Agent 负责受限本地任务，Browser Agent 负责搜索与只读网页访问。M10 对话只接入 Main 文件任务规划与 Computer 工具，复用 LangGraph 和审批账本。没有自动任务、技能广场、团队管理或推荐信息流。

文件提问、网页搜索、读取和来源追问共用每会话最多100次请求，单次最多2000字；历史窗口最多显示最近30条并受46 KiB通信预算限制，完整记录保留在本地，暂不提供历史分页。任务历史显示最近10项，旧审批不能从历史重放；只有最近完成且当前授权的任务可申请受限撤销。当前仍为阶段状态，没有逐 token 输出或自动重连。只读结果会明确标记截断。旧 M04 无身份快照的计划需重建，无法安全证明的中断动作拒绝重放。程序不是操作系统级文件沙箱，不能消除外部进程并发更改路径的所有竞态。

开发 Key 仅放根目录被忽略的 `.env.local`，变量名见 `.env.example`。不得提交 Key 或把环境文件打包。三个角色固定模型配置见架构文档；Tavily 缺失时搜索明确不可用；开发主进程读取可选 TAVILY_API_KEY，发布通过 safeStorage。Browser 接口、合成试用与运行时限制见 [模块 README](backend/src/orvia_backend/browser/README.md)。创建草稿本身不代表开始执行任务。
首版不删除、覆盖、清理系统或执行任意脚本。PDF/OCR、PPT、标书、完整行业调研、代码生成、原型、桌面点击和浏览器写操作属于后续能力。

## 提交与远端同步

按最新开发约定，Agent 每轮完成一个模块后创建本地 commit 并停止，push 由用户手动执行。未推送不影响已实现、验证、记录和提交的模块完成；历史推送结果仅作为历史证据保留。

M07 配套 Chromium Headless Shell 已于 2026-09-28 重试安装成功，默认动态读取的 4 项合成测试通过，无需切换 Edge。未验证真实 Tavily/互联网网页兼容性，M08 本机验收已完成，独立无开发环境 Windows 机器仍待补验。
