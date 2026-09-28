# Orvia 开发约定

## 范围与依据

所有代码必须在 `D:\Users\18532\Desktop\LXH\Project\Orvia` 开发。远端为 `https://github.com/Kr1sxu/Orvia`。
设计依据为 `C:\Users\18532\Documents\Codex\2026-09-22\wo\outputs\序航Orvia-MVP技术栈设计.md`；当前用户要求优先于旧设计，尤其三个角色使用各自固定模型，不共用同一模型配置。
开始工作先检查目录、Git 状态、分支、远端默认分支与历史、已有文档和代码。禁止假设远端为空、覆盖用户改动、重置或删除已有内容。首次预检发现的 LICENSE 删除属于预存工作区状态，不纳入本模块提交。

## 每轮模块与停止点

默认按 M01 → M08 顺序，每轮只做一个模块。开始前用中文汇报模块、目标、涉及文件、验证方法和停止点；持续提供中文进度更新。
模块结束必须完成代码、必要中文注释、模块 README、相关分级测试、开发清单与进度记录、敏感信息检查、正常 commit 和 push，再汇报试用方法、风险、commit 与 push 结果并停止。用户明确要求后才开始下一模块。
重大范围变化、必要凭据缺失、模型不可用、不能安全解决的仓库冲突，停止并说明待决策原因。Push 失败保留本地 commit，记录未推送，不伪造成功，不 force push；仅继续当前模块必要收尾，不越过模块停止点。
未完成使用 `- [ ]`；只有实际实现、验证且记录后才使用 `- [x] √`。构建或 mock 测试通过不等于整个模块完成。提交与推送分别记录。

## 实现与文档

技术主线：Electron + React + TypeScript，Python 3.12，LangGraph Python，SQLite + aiosqlite，SQLite FTS5 + jieba，PyInstaller + electron-builder。
根目录维护 README、AGENTS；docs 维护 ARCHITECTURE、DEVELOPMENT_PLAN、PROGRESS。
每个逻辑模块 README 说明用途、结构、输入输出与公共接口、依赖配置、运行、测试、示例、权限边界、已知限制。
公共接口、状态转换、LangGraph 节点、审批与恢复、权限检查、跨语言通信、文件执行、浏览器限制和复杂边界必须有有意义的中文注释或 docstring；禁止逐行复述与泛化异常兜底。

## 产品权限边界

Main 规划依赖、委派、重规划、汇总证据并判断完成；Computer 执行限定本地任务；Browser 搜索与只读访问，静态网页优先 HTTP，动态页面使用 Playwright。程序负责授权检查和事实核验。
桌面整理 MVP 包含扫描、搜索、属性、空间统计、大文件、文本读取、分类重命名计划、审批、创建目录/移动/重命名、核验、恢复和最近一次文件变更任务的受限撤销。
后续能力：PDF/OCR、PPT、标书、完整行业调研、代码生成、原型、系统清理、任意脚本、桌面点击和浏览器写操作。不能提前实现或宣称可用。
M01 只验证窗口 → 受限 IPC → Python → stdio JSON Lines → 健康响应，不接入完整 Agent，不整理或操作用户真实文件，不调用模型完成真实任务。

## 凭据与模型

| 角色 | 固定模型 | 固定 Base URL | 环境变量 |
|---|---|---|---|
| Main | deepseek-flash | https://api.deepseek.com | DEEPSEEK_API_KEY |
| Computer | glm-5.3-flashx | https://open.bigmodel.cn/api/paas/v4 | ZHIPU_API_KEY |
| Browser | mimo-v2.6-flash | https://api.xiaomimimo.com/v1 | MIMO_API_KEY |

每个 Mission 固化三个角色配置，禁止静默更换模型、供应商或 Base URL。M01 不读取 `.env.local`。
开发密钥仅存被 Git 忽略的根 `.env.local`；`.env.example` 仅变量名、空值和说明。真实 Key 禁止进入源码、文档、测试、日志、Git、安装包和 subagent 提示词；检查时仅报告变量是否存在，不输出值。必要 Key 缺失不能猜测或填假值。
真实模型测试仅用合成数据，限制超时、重试与费用；必须区分 mock 与真实调用。未提供 Tavily Key 时，`web_search` 明确返回不可用，禁止伪造结果。

## 分级测试

先读 PROGRESS 复用已有结论。仅代码、配置、依赖、接口变化才重跑相关测试；文档-only 不跑代码测试；失败只重跑失败项或最小相关集合。

| 级别 | 适用范围 |
|---|---|
| L0 | 静态检查、文档、配置、类型、语法 |
| L1 | 修改模块目标单元测试 |
| L2 | 跨模块接口、数据库、协议、模型适配、权限集成 |
| L3 | 用户流程、Electron-Python 通信、审批对应 E2E |
| L4 | 重大跨模块改动、发布验收或用户明确要求的全量回归 |

测试代码只放 `backend/tests/`、`apps/desktop/tests/`、`tests/integration/`、`tests/e2e/`。
报告、截图、日志与临时构建产物放 `artifacts/test-results/<模块名>/`，必须 Git 忽略；不得把临时测试脚本散落源码。
每次记录级别、实际命令、通过/失败、是否 mock、是否真实模型、结果目录及未覆盖风险。

## 协作与 Git

允许将当前模块独立部分委派 subagent；先说明任务边界和文件所有权，禁止并发修改同一文件、提前开发下个模块、传递真实 Key。主 Agent 整合、验证、更新进度、提交和 push。
已授权每模块正常 commit 与 push。提交前检查 `git status`、`git diff`、`git diff --cached`，显式选择本模块文件，禁止 `git add .`。检查密钥、数据库、日志、用户文件、测试结果未暂存。
禁止 force push、重写公共历史、删除远端分支、覆盖他人修改、发布 GitHub Release。推送失败记录原因，不删除提交来解决。
