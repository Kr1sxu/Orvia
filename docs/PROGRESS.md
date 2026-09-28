# 开发进度与验证证据

## 当前状态（2026-09-28）

M01–M06 已完成并由用户手动 push；本轮从 `db08c59` 开发 M07。M07 已实现并完成下述合成验证，本地提交以包含本节的 `feat(M07): add restricted browser search and page reading` 为准；用户手动 push 待执行，Agent 不 push。预存 LICENSE 删除仍未暂存；M08 未开始。历史推送失败记录原样保留。

## 启动预检

- 项目：`D:\Users\18532\Desktop\LXH\Project\Orvia`。
- 已阅读技术设计 v0.7（2026-09-28）。本轮三个独立固定模型映射覆盖旧文档的共用模型约定，详见 ARCHITECTURE。
- 远端：`https://github.com/Kr1sxu/Orvia`，默认分支与本地分支均为 `main`。
- `git ls-remote --symref origin HEAD` 与 `git fetch origin` 确认初始远端为 `8446647`（Initial commit），非空仓库，历史只有 MIT LICENSE。
- 预存工作区：`LICENSE` 已删除但未暂存，`.gitignore` 未跟踪；保留该删除，不纳入提交。无已有 README、AGENTS 或代码，无祖先 AGENTS 约定。
- `.env.local` 三个模型变量均存在且非空，仅检查状态，不输出密钥。未验证供应商可用性；M01 不读取凭据、不调用模型。Tavily 未配置，搜索留在 M07。
- 默认 Python 是 3.11.7；`py -0p` 找到已安装 Python 3.12.6，项目固定使用后者。Node 24.19.0、npm 11.17.0、uv 0.12.19、Windows x64。

## M01 已实现并验证

- [x] √ npm workspaces、Electron/React/TypeScript/Vite、Python 3.12/uv 工程及锁文件。
- [x] √ 真实窗口 → 单一 preload API → 校验来源的 IPC → 固定 Python 子进程 → UTF-8 JSON Lines → 健康响应。
- [x] √ hello 握手、版本校验、请求关联、64 KiB 行上限、中文分片、错误恢复、5 秒请求超时与无自动重放。
- [x] √ Node 隔离、sandbox、CSP、新窗口/导航/权限/网络拒绝，Python 环境变量白名单。
- [x] √ EOF 关闭及自有进程清理；修复退出早于首次请求的启动竞态。
- [x] √ 中文注释、根文档、桌面/后端/跨进程测试模块 README。
- [x] √ Git commit 成功（代码提交 `d9bab2a`）。
- [x] √ Git push 成功（`8446647..9b37ac0 main -> main`）。
- [x] √ M01 全部收尾完成并停止。

## 实际验证记录

结果目录统一为 `artifacts/test-results/M01/`，已 Git 忽略。测试未调用真实模型、无费用、不处理真实用户资料。开发运行输出 `apps/desktop/dist/` 为可重复启动的构建目录，亦不入 Git。

| 级别 | 实际命令 | 结果与证据 | mock / 真实模型 | 未覆盖风险 |
|---|---|---|---|---|
| L0 | `npm run build`（内含 `npm run check`、两套 tsc 与 Vite 构建） | 最终通过，`build.log` | 无 / 否 | 未构建安装包 |
| L0 | `npm audit --json`（重定向至结果目录） | 修复后 0 项已知漏洞，`npm-audit.json` | 无 / 否 | 审计数据库不能证明没有未知漏洞 |
| L1 | `.\backend\.venv\Scripts\python.exe -m pytest backend\tests --junitxml=artifacts/test-results/M01/backend-junit.xml` | 16/16 通过；协议状态、有界读取、无换行 EOF、非法 UTF-8/JSON | 内存流，无协议/模型 mock / 否 | 不替代操作系统管道测试 |
| L1 | `npm run test:unit -- --reporter=json --outputFile=artifacts/test-results/M01/desktop-unit.json` | 当时 9/9；协议/权限 4 项仍有效，生命周期后来增加 1 项，见下一行 | 生命周期模拟子进程，其余无 mock / 否 | 拒绝路径的真实恶意渲染页面未穷举 |
| L1 | `npx vitest run apps/desktop/tests/backend.test.ts --reporter=json --outputFile=artifacts/test-results/M01/lifecycle.json` | 最终 6/6；不兼容握手、超时、异常关闭、不重放、EOF/终止、先退出后请求不 spawn | 模拟进程/管道/时间 / 否 | kill 失败且没有 close 的极端 OS 状态未验证 |
| L2 | `npm run test:integration -- --reporter=json --outputFile=artifacts/test-results/M01/integration.json` | 最终 3/3；真实 Python、并发关联、中文分片/合并、错误恢复、缺失解释器、EOF 与 PID 退出核验 | 无 / 否 | Windows 当前开发环境，未覆盖其他系统 |
| L3 | `npm run test:e2e` | 最终 1/1；真实 Electron 窗口+真实 Python、两次健康检查、隔离属性、退出 PID 核验；`e2e.json`、`e2e.log`、`health-window.png`，截图已视觉检查 | 无 / 否 | 无干净机器安装验收；不包含后续 Agent/文件任务 |

最终有效目标用例共 30 项：Python 16、桌面协议/权限 4、桌面生命周期 6、跨进程 3、E2E 1。不是 L4 全量回归，未测试未实现模块。

### 失败、修复与重跑依据

1. 依赖安装尚未完成时，首次 `npm run build` 与 `npm run test:integration -- --reporter=json --outputFile=artifacts/test-results/M01/integration.json` 分别因 `tsc` / `vitest` 未就绪而 exit 1，无测试执行。安装完成后相关命令通过。
2. 初始 npm audit 返回 3 项已知问题（moderate/high/critical 各 1），报告 `npm-audit-initial.json`。将 Vite 6.4.1 → 6.4.3、Vitest 3.2.4 → 4.1.11，更新锁文件后审计 0。因依赖变化重跑受影响的 TS 构建和测试；未重跑无关 Python 单测。
3. 代码审查发现 stop 先于首次 health 时仍可 spawn；修复 start 前关闭状态检查，新增用例后仅重跑生命周期 L1、客户端 L2、构建及对应 L3，复用其他结论。
4. 第一次 `npm run test:e2e` 的真实健康响应已经通过，但退出核验取用了 Playwright 启动器 PID，查不到 Python 导致失败，保留 `e2e-initial.log`。改为从 Electron 主进程读取 PID 后，仅重跑该 E2E，1/1 通过。
5. Electron 44 npm 包不自动下载运行时，增加 `npm run setup:electron`，已实际执行成功。npm 对 esbuild 安装脚本的提示未阻塞构建；未调整全局 npm 策略。

## 限制与下一轮

仅提供 Windows 源码开发启动，无安装包、托盘、自动重连、持久化日志、Agent、数据库、凭据存储、模型适配、文件操作或浏览器工具。stderr 持续消费但不保存原文。安全策略不是 OS 沙箱。
健康检查仅证明本地通信正常；三模型真实可用性与能力需要在后续配置模块用合成数据验证。未承诺真实模型支持情况。
本轮完成提交/推送后停止；只有用户明确要求，才开始 M02。

## Git 收尾

提交前已检查 `git status`、`git diff`、`git diff --cached`、`git diff --cached --check`；清除 5 个文件末尾多余空行后静态检查通过，纯空白修订不重复代码测试。
通过内存比较本地 Key 与 38 个暂存文件及本地测试产物，密钥匹配为 0；禁止路径为 0；JSON 配置、Markdown 本地链接及 `.env.example` 空值均通过。报告 `staged-hygiene.json` 仅含计数，无密钥或摘要。
测试报告、运行数据、虚拟环境、node_modules 与真实 Key 均未暂存；`git check-ignore` 已确认保护生效。预存 LICENSE 删除未纳入本轮提交。
- 首次提交尝试：因 `Author identity unknown` / `unable to auto-detect email address` 失败，未产生 commit；随后用户确认身份。
- 提交成功：`git -c user.name='踪显' -c user.email='18532112451@163.com' commit -m "feat(M01): establish restricted Electron Python health bridge"`，生成 `d9bab2a`，38 个模块文件。作者身份已核对。
- 推送失败：连续两次 `git push origin main` 均 exit 1，错误为 `OpenSSL SSL_connect: SSL_ERROR_SYSCALL in connection to github.com:443`。未报告远端更新成功，保留本地提交，不 force push、不重写历史、不关闭 TLS 校验。
- 身份阻塞已解除：用户明确确认沿用“踪显 <18532112451@163.com>”。仅为本次 Git 命令指定该身份，不修改全局配置。
- 模块代码已提交，另将本次失败回执作为独立文档提交保留；这些本地提交尚未推送。工作区预存 LICENSE 删除仍未暂存。网络恢复后只需继续正常 push 和更新回执，不开始 M02。
- 本次仅 Git 与文档收尾，复用上述 L0–L3 结论，不重复运行代码测试。

### 2026-09-28 推送恢复

- 用户要求继续 push；`git ls-remote --symref origin HEAD` 确认远端默认分支为 main，远端仍为 `8446647`。
- `git push origin main` 成功，远端从 `8446647` 更新至 `9b37ac0`，包含代码提交与先前失败回执。未 force push，未修改 TLS 配置。
- 本次仅更新 PROGRESS 与 DEVELOPMENT_PLAN 的收尾状态；L0 使用 `git diff --check` 和暂存差异检查，无 mock、无真实模型调用，无新增测试产物。代码测试复用上述结果，未覆盖风险不变。
- 预存 LICENSE 删除继续保持未暂存；M02 未开始。

## M02 数据契约、SQLite、凭据与模型配置（2026-09-28）

### 实现与边界

- [x] √ Pydantic 冻结契约、生成 JSON Schema、Zod 校验及 Ajv2020 跨语言对照；固定映射、角色唯一性、额外字段拒绝。
- [x] √ aiosqlite + SQLite v1 迁移、WAL、事务、幂等草稿创建、重启读取、模型快照不可变、未知数据库版本拒绝。列表最多 20 条。
- [x] √ 开发主进程只读根 .env.local，发布 CredentialVault 使用 safeStorage 加密原子保存；无明文回退。私有 stdio 注入后端内存，不进入命令行或数据库。
- [x] √ 六个受限 renderer API，设置状态和草稿 UI。保存草稿只保存名称与模型配置，不触发 Agent、模型或用户文件操作。
- [x] √ 三个固定模型的真实合成文本与结构化工具调用通过；不静默替换模型/供应商/地址。
- [x] √ 初始化失败清理后端；凭据落盘后同步失败停止旧后端并提示重启；工具响应结构与深嵌套 JSON 错误脱敏。
- [x] √ 中文注释及 domain/storage/configuration/credentials/contracts 的独立 README，根和父模块文档同步。
- [x] √ M02 commit 成功（`6f2986a`）。
- [x] √ M02 push 成功（远端从 `f6b8c76` 更新至 `6b459c7`）。
- [x] √ M02 全部收尾完成并停止。

M02 不创建空壳审批/操作账本/checkpoint，不提前实现 M03–M08。草稿重启持久化不等于执行中任务恢复。完整安装包、发布设置页面全流程、LangGraph 与真实任务在相应后续模块验收。

### 测试记录与复用

统一结果目录：`artifacts/test-results/M02/`，所有报告、截图和测试数据库均 Git 忽略。除显式 live 脚本外，没有真实模型请求；L3 正常启动主进程会读开发 Key 并仅传后端内存，不发网络请求，safeStorage 验证只用合成 Key。

| 级别 | 实际命令 | 最终结果 / 证据 | mock / 真实模型 | 未覆盖风险 |
|---|---|---|---|---|
| L0 | `npm run build` | 两套 tsc 和 Vite 通过；build.log | 无 / 否 | 未打包安装 |
| L0 | `.\.venv\Scripts\uv.exe pip check --python backend\.venv\Scripts\python.exe` | 19 个包兼容 | 无 / 否 | 非漏洞扫描 |
| L0 | `.\backend\.venv\Scripts\python.exe -`（内存生成三模型 JSON Schema，与 contracts/m02.schema.json 比较） | 无漂移；schema-check.txt | 无 / 否 | 输入规范化由运行时完成 |
| L0 | `npm audit --json` | 升级 Ajv 后 0 项；npm-audit.json | 无 / 否 | 不保证未知漏洞不存在 |
| L1/L2 | `.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_domain.py backend/tests/test_storage.py --basetemp=artifacts/test-results/M02/data-temp --junitxml=artifacts/test-results/M02/data-junit.xml` | 20/20；契约、真实 SQLite 迁移/持久化/损坏/快照/列表上限 | 无 / 否 | 不含后续业务表、OS 断电 |
| L1/L2 | `.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_configuration.py backend/tests/test_application.py --basetemp=artifacts/test-results/M02/app-temp --junitxml=artifacts/test-results/M02/application-junit.xml` | 当时 18/18；其中 application 4 项结论继续有效，configuration 后续扩展见下行 | HTTP mock、应用层真实 SQLite / 否 | 不替代真实模型能力测试 |
| L1 | `.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_configuration.py --basetemp=artifacts/test-results/M02/configuration-final-temp --junitxml=artifacts/test-results/M02/configuration-final-junit.xml` | 27/27；脱敏、缺 Key、错误/重定向/超时/超大响应、工具结构、深层 JSON | httpx.MockTransport / 否 | 工具业务授权尚未实现 |
| L1 | `.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_server.py --basetemp=artifacts/test-results/M02/server-temp --junitxml=artifacts/test-results/M02/server-junit.xml` | 4/4；serve 接入 Application 后重验帧恢复和 EOF | 内存流 / 否 | 不代替真实进程 |
| L1 | `npx vitest run apps/desktop/tests/credentials.test.ts --reporter=json --outputFile=artifacts/test-results/M02/credentials.json` | 15/15；开发只读、发布模式、损坏、原子失败、串行保存 | fake safeStorage + 真实临时文件 / 否 | 系统加密另由 L3 验证 |
| L0 | `npx tsc --noEmit --strict --target ES2022 --module NodeNext --moduleResolution NodeNext --esModuleInterop --skipLibCheck apps/desktop/src/main/credentials/index.ts` | 独立凭据模块类型检查通过；整体 build 再次覆盖 | 无 / 否 | 不证明业务正确 |
| L2 | `npx vitest run tests/integration/m02.test.ts --reporter=json --outputFile=artifacts/test-results/M02/integration.json` | 初版 7/7；后续增加 Unicode/default revision，最终 8 项见下文 | 无，真实 Python/SQLite / 否 | 不是所有模型输出语义的证明 |
| L1/L2 | `npx vitest run tests/integration/m02.test.ts tests/integration/backend.test.ts apps/desktop/tests/backend.test.ts apps/desktop/tests/protocol.test.ts --reporter=json --outputFile=artifacts/test-results/M02/bridge-regression.json` | 当时 20/20；保留 M01 协议/权限4项与真实管道3项，其余采用更新结果 | 生命周期模拟，管道/DB真实 / 否 | 未重跑无关 M01 Python 协议单测 |
| L1/L2 | `npx vitest run apps/desktop/tests/backend.test.ts apps/desktop/tests/credential-sync.test.ts tests/integration/m02.test.ts --reporter=json --outputFile=artifacts/test-results/M02/final-targeted.json` | 当时 16/17；同步2项、跨语言8项通过，生命周期1项失败后单独修复重验 | 生命周期/同步模拟，其余真实 / 否 | 此失败报告保留，不伪装全通过 |
| L1 | `npx vitest run apps/desktop/tests/backend.test.ts --reporter=json --outputFile=artifacts/test-results/M02/lifecycle-final.json` | 最终 7/7；含初始化失败终止与先退出后请求 | fake 子进程/时间 / 否 | OS kill 失败且无 close 的极端退出未覆盖 |
| L3 | `npm run test:e2e` | 最终 2/2；真实窗口/IPC/Python/SQLite/重启及 Windows safeStorage，e2e.json、e2e.log、settings-and-draft.png（已视觉检查） | 无通信/加密 mock / 否 | safeStorage 调用生产模块，完整打包界面未验收 |

最终有效自动化用例 **96 项**：domain/storage20、configuration27、application4、server4、credentials15、生命周期7、凭据同步2、跨语言/存储8、M01相关真实管道3、协议/权限4、E2E2。只根据改动范围运行 L0–L3，未运行 L4，也没有重复无关已通过测试。

### 真实模型调用与费用边界（L2，非 mock）

1. `.\backend\.venv\Scripts\python.exe -X utf8 backend\tests\live_model_preflight.py --run-live`：Main 成功；Computer HTTP 200 但 64 输出 token 内无正文，脚本停止，Browser 未调用。退出码 1，保留 live-preflight-initial.json；不将 HTTP 200 单独记为完整文本能力通过。
2. `.\backend\.venv\Scripts\python.exe -X utf8 backend\tests\live_model_preflight.py --run-live --role computer --role browser --max-tokens 256`：只重测未通过/未执行角色，两个均成功；Computer 返回推理内容和正文，finish_reason=stop。live-preflight.json，exit 0。模型/URL 未改。
3. `.\backend\.venv\Scripts\python.exe -X utf8 backend\tests\live_model_capabilities.py --run-live`：使用实际 ModelClient，三个角色均返回合法 report_probe 工具提议和合成参数；未执行任何工具。每次最多 512 输出 token；live-capabilities.json，exit 0。

总计 **7 次真实请求**，供应商 usage 合计 **1194 token**（含首次不足额度请求）；每个请求零自动重试、20 秒网络超时、响应上限 64 KiB。只传固定合成提示词和虚构工具定义，未发送草稿、路径、用户文件或秘密。价格以供应商账单为准，本次不臆造人民币费用。已通过的真实调用不因后续纯校验加固再次调用。

### 失败、修复与最小重跑

- 新增 Ajv 8.17.1 时审计提示 1 项 moderate，升级固定为 8.20.0 后 0 项；依赖变化仅重验相关跨语言测试。初始审计保留 npm-audit-initial.json。
- 审查发现凭据已落盘但后端同步失败状态不明确，增加显式部分成功提示并关闭旧后端，测试模拟失败而不使用真实 Key。
- 初始化失败统一清理时，一项已有不兼容握手测试发现重复 kill；加上已失败状态判断后只重跑生命周期文件（7/7）。相关功能集成与 E2E 根据接口变化重跑；未再次跑无关数据库测试或付费调用。
- 模型适配对无效 tool_calls 与深层 JSON 的响应边界已收紧，增加参数化用例后只重跑 test_configuration.py。此前真实三模型返回均满足新契约，复用真实能力结论。
- UTF-16 与 Python Unicode 长度差异已修正，跨语言增加 200 个 emoji 边界和 revision 默认值用例。发布 Key 输入在发起 IPC 后清空，失败响应不带原始内容。

### M02 Git 收尾

预检 fetch 与 ls-remote 确认远端默认 main、HEAD f6b8c76，与本地一致。预存 LICENSE 删除保留且不纳入本轮。提交/推送在实际执行后分别记录，本节不会提前声称模块完成。

提交前检查：已显式暂存本模块 48 个文件，检查 git status、git diff、git diff --cached 及 diff --check；预存 LICENSE 删除不在索引。暂存文件与本地 221 个测试产物逐字节比较开发 Key，匹配 0；禁止路径 0；JSON 与 Markdown 本地链接通过。报告 staged-hygiene.json 只含安全计数。真实 Key、测试报告、数据库和日志未进入提交。

- 提交成功：`git -c user.name='踪显' -c user.email='18532112451@163.com' commit -m "feat(M02): persist mission profiles and protect model credentials"`，生成 `6f2986a`，48 个文件，作者身份已核对。
- 推送失败：`git push origin main` 返回 `OpenSSL SSL_connect: SSL_ERROR_SYSCALL in connection to github.com:443`，exit 1。
- 有限替代尝试：`git -c http.sslBackend=schannel push origin main` 使用 Git for Windows 系统 TLS 后端，仍返回 `schannel: failed to receive handshake, SSL/TLS connection failed`，exit 1。仅该命令指定后端，没有更改全局配置、关闭证书校验或 force push。
- 保留实现提交，本次失败记录另作文档提交；当前不能勾选 push 或整个 M02 完成。后续网络恢复可正常推送这些本地提交，不重写历史。未开始 M03，未发布 Release。
- 本次收尾只有文档变化，L0 暂存差异/空白检查通过，复用上述测试结论，不再运行代码测试或付费模型调用。

### M02 推送恢复（2026-09-28）

- 用户要求继续推送；git ls-remote 确认远端 main 为 f6b8c76。git push origin main 首次重试即成功，远端更新至 6b459c7，包含实现与此前失败回执。
- 本次仅更新 PROGRESS 与 DEVELOPMENT_PLAN；L0 执行 git diff --check、git diff --cached --check 并审查暂存差异及文件范围，无密钥、数据库、日志或测试产物；无 mock、无真实模型调用、无新增结果文件。复用已有测试，未覆盖风险不变。
- 预存 LICENSE 删除保持未暂存，未开始 M03；此前失败记录作为历史证据保留。

## 2026-09-28 开发规则调整

用户明确要求：只创建本地提交，由用户自行手动 push。已同步 AGENTS、README、DEVELOPMENT_PLAN；Agent 不再执行 push，不尝试为 push 更改 TLS/网络配置。模块完成条件为实现、分级验证、文档与本地提交，未推送不再导致模块未完成。历史推送记录保留，不改写事实。
本次规则变更为文档-only，L0 使用 `git diff --check` 和暂存差异检查，无 mock、无真实模型，不运行代码测试。随后仅开发 M03，完成本地提交后停止。

## M03 Computer 只读工具与权限网关（2026-09-28）

- [x] √ 本地目录授权、路径穿越、UNC、符号链接和 Windows reparse point 拒绝；每次调用复核授权根身份。
- [x] √ 目录枚举、文件名搜索、文件属性、UTF-8 文本读取、逻辑空间统计和大文件清单；扫描预算与 `complete/truncated/errors` 证据。
- [x] √ PowerShell、Git Bash、WSL 固定路径探测；受限进程概况；仅允许 `runtime_version` 模板，拒绝任意命令和 WSL 发行版执行。
- [x] √ Computer 角色、Mission、grant ID、撤销和 200 次调用预算网关；接入 `Application` 的 `computer.grant/revoke/status/execute`。
- [x] √ 中文模块 README、M03 JSON Schema 与目标测试；未开放 renderer 目录选择，未执行写操作。

### M03 验证

| 级别 | 实际命令 | 结果 | mock / 真实模型 | 结果目录 | 未覆盖风险 |
|---|---|---|---|---|---|
| L0 | `python backend/src/orvia_backend/computer/contracts.py`、`git diff --check` | Schema 生成、空白检查通过 | 无 / 否 | `artifacts/test-results/M03/` | 未做安装包构建 |
| L1 | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_computer_files.py backend/tests/test_computer_gateway.py backend/tests/test_computer_system.py -q` | 10 passed, 1 skipped（Windows 无符号链接权限时跳过） | mock 进程、临时合成目录 / 否 | `artifacts/test-results/M03/` | 未覆盖真实 reparse point、权限拒绝组合 |
| L2 | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_application.py backend/tests/test_protocol.py backend/tests/test_server.py -q` | 20 passed；应用协议回归通过 | 内存流与临时 SQLite / 否 | `artifacts/test-results/M03/` | 未接入 Electron renderer 目录选择流程 |

M03 未读取 `.env.local`、未调用模型、未访问真实用户文件。空间统计为逻辑大小，不代表磁盘可释放空间。系统探测仍受 Windows 安装路径和权限影响；完整审批、写入、账本和撤销属于 M04。提交成功后由用户手动 push。

## M04 文件动作、审批、操作账本与撤销（2026-09-28）

- [x] √ 动作计划契约支持 `mkdir`、`move`、`rename`；计划固定授权根、任务 ID 和顺序，拒绝删除、覆盖、绝对路径、越界和跨卷动作。
- [x] √ 计划必须经过显式 `computer.approve` 才能执行；执行前后复核源/目标，逐步记录账本并返回核验结果。
- [x] √ SQLite 新增 `operation_tasks` / `operation_entries` 账本表；连接重启把 running/approved 标成 `interrupted`，恢复不会自动重放。
- [x] √ `computer.resume` 只恢复 interrupted 计划，`computer.undo_latest` 只撤销指定 Mission 最近完成任务，并检查目标身份、原位置冲突和新建目录是否为空。
- [x] √ 应用协议、存储 README、Computer README、开发清单和目标测试已更新；未开放 renderer 写操作 UI。

### M04 验证

| 级别 | 实际命令 | 结果 | mock / 真实模型 | 结果目录 | 未覆盖风险 |
|---|---|---|---|---|---|
| L1 | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_computer_actions.py backend/tests/test_application_actions.py -q` | 4 passed | 临时合成目录、真实临时 SQLite / 否 | `artifacts/test-results/M04/` | 未做 Electron renderer 完整审批界面 |
| L2 | `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` | 81 passed, 1 skipped | 临时合成目录与进程 mock / 否 | `artifacts/test-results/M04/` | 未覆盖断电时 OS 文件动作与真实 reparse point |

M04 未读取 `.env.local`、未调用模型、未访问真实用户文件。恢复状态需要用户再次明确调用，撤销只处理本程序账本中且身份未变化的最近任务；没有通用回滚或删除能力。提交成功后由用户手动 push。

## M05 LangGraph 三 Agent 与桌面整理闭环（2026-09-28）

- [x] √ 加入 LangGraph 0.6 与 SQLite checkpoint 依赖；兼容当前 aiosqlite 的连接状态接口。
- [x] √ Main / Computer / Browser 固定逻辑角色和能力表；Main 负责计划/证据/完成判断，Computer 只能进入 M04 审批动作，Browser 未配置 Tavily 时明确不可用。
- [x] √ LangGraph 节点完成计划、动作计划、审批暂停、执行、核验和完成判断；Application 暴露 `mission.run` / `mission.approve`。
- [x] √ SQLite checkpoint 支持按 thread_id 中断后恢复；文件事实仍以 M04 操作账本和核验结果为准。
- [x] √ 合成目录闭环、空计划拒绝、角色边界和 Browser 不可用测试；未调用真实模型、未联网搜索。

### M05 验证

| 级别 | 实际命令 | 结果 | mock / 真实模型 | 结果目录 | 未覆盖风险 |
|---|---|---|---|---|---|
| L0 | `.venv/Scripts/uv.exe lock --project backend`、`uv sync --project backend --locked`、Python compileall | 依赖锁定、安装和编译通过 | 无 / 否 | `artifacts/test-results/M05/` | 未构建安装包 |
| L1 | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_agents_graph.py backend/tests/test_agent_roles.py backend/tests/test_application_actions.py -q` | 5 passed | 合成目录、临时 checkpoint / 否 | `artifacts/test-results/M05/` | 未覆盖真实供应商模型 |
| L2 | `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` | 85 passed, 1 skipped（LangGraph 依赖发出 1 条弃用提示） | 临时 SQLite、进程 mock / 否 | `artifacts/test-results/M05/` | 未覆盖 Electron renderer 流程和断电恢复 |

M05 的 Main 规划使用程序传入的合成动作列表，未让真实模型决定文件动作；Browser 只注册角色边界，搜索与网页读取属于 M07。提交成功后由用户手动 push。

## M06 上下文、用户偏好与轻量 RAG（2026-09-28）

- [x] √ 加入 `jieba` 依赖并锁定；SQLite FTS5 可用性在临时数据库中验证。
- [x] √ 文本按有界字符数分块，jieba 分词后写入 FTS5；原文块、来源、Mission、内容哈希和更新时间单独保存。
- [x] √ 检索严格按 Mission 隔离，返回来源、块序号、原文和分数；拒绝 FTS 控制字符和超长查询。
- [x] √ 显式偏好、版本化滚动摘要、按来源替换和按 Mission 清理；不扫描目录、不删除用户原文件。
- [x] √ Application 接入 context 索引、检索、清理、偏好和摘要接口；模块 README、存储 README、架构、开发清单已更新。

### M06 验证

| 级别 | 实际命令 | 结果 | mock / 真实模型 | 结果目录 | 未覆盖风险 |
|---|---|---|---|---|---|
| L0 | `.venv/Scripts/uv.exe lock --project backend`、`uv sync --project backend --locked`、Python compileall | jieba/锁文件/编译通过 | 无 / 否 | `artifacts/test-results/M06/` | 未做安装包构建 |
| L1 | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_context.py backend/tests/test_application_context.py -q` | 3 passed | 临时 SQLite、合成文本 / 否 | `artifacts/test-results/M06/` | 未覆盖超大生产索引 |
| L2 | `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` | 88 passed, 1 skipped | 临时 SQLite、进程 mock / 否 | `artifacts/test-results/M06/` | 未覆盖 Electron renderer 上下文 UI和断电时 FTS 事务 |

M06 未读取 `.env.local`、未调用模型、未联网。摘要由调用方提供，检索证据来自任务范围内显式提交文本；真实模型摘要、全盘索引和向量检索不属于本模块。提交成功后由用户手动 push。

## M07 Browser 搜索、HTTP 与 Playwright 只读读取（2026-09-28）

### 预检与范围

已读取 AGENTS、README、ARCHITECTURE、DEVELOPMENT_PLAN、PROGRESS 及指定技术设计。工作目录正确，本地分支 main、HEAD db08c59；`git ls-remote --symref origin HEAD` 确认远端默认 main 且 HEAD 同为 db08c59c76ec1639db2d9ee8758ddd6ec0d0935e。初始仅 LICENSE 预存删除，无其它用户改动。未 fetch/push，未修改 TLS 或网络配置。

- [x] √ 新增 browser/network.py 与 service.py：公开目标校验、全部 DNS 地址检查、固定 IP 与 TLS SNI、同源逐跳重定向、无 Cookie 的流式 HTTP 出口。
- [x] √ HTTP 优先与 trafilatura 正文提取；空壳 HTML 可转 Playwright，权限/HTTP 错误不绕过。浏览器单页资源经相同出口 fulfill，CSP sandbox、资源/字节/超时限制与错误证据。
- [x] √ Tavily 缺 Key 明确 SEARCH_UNAVAILABLE；配置后仅固定搜索 API、基本搜索、有限合成/mock 验证，无伪造结果。
- [x] √ 主进程开发凭据与发布 safeStorage 增加 tavily，Python 仅持有 SecretStr；configuration.search_available 返回配置存在性。三个模型映射与 Mission 快照不变。
- [x] √ Application 接入 browser.read/search，要求已有任务且拒绝额外字段；BrowserAgent 委派窄接口。renderer 未开放搜索、读取或任意网络入口。
- [x] √ 中文注释、模块 README、根/相关模块文档、开发清单与本节记录更新；未提前开发 M08。

### 分级验证

所有本轮报告位于 Git 忽略的 `artifacts/test-results/M07/`。Python 使用项目 `backend/.venv/Scripts/python.exe`；以下命令在仓库根目录执行。未调用任何真实模型或 Tavily，网页 HTTP/DNS 均为 mock，真实浏览器加载的也是合成响应。依赖/运行时下载不涉及用户资料。

| 级别 | 实际命令 | 结果 / 证据 | mock / 真实模型 | 未覆盖风险 |
|---|---|---|---|---|
| L0 | `.venv/Scripts/uv.exe lock --project backend`、`.venv/Scripts/uv.exe sync --project backend --locked` | Playwright 1.63.0、trafilatura 2.2.0 及锁文件安装通过 | 无 / 否 | 不等于 Chromium 安装成功 |
| L0 | `npm run check`、`npm run build`；UI 凭据标签调整后再次 `npm run build` | 类型与构建通过，build.log / build-final.log | 无 / 否 | 未打包 |
| L0 | `backend/.venv/Scripts/python.exe -m compileall -q backend/src/orvia_backend/browser backend/src/orvia_backend/application.py backend/src/orvia_backend/agents/roles.py` | 编译通过 | 无 / 否 | 非行为验证 |
| L1/L2 | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_browser.py backend/tests/test_agent_roles.py backend/tests/test_configuration.py --basetemp=artifacts/test-results/M07/unit-temp --junitxml=artifacts/test-results/M07/unit.xml -q` | 65 passed；URL、DNS、重定向、Cookie、超限、错误脱敏、Tavily 和协议 | HTTP/DNS mock、临时 SQLite / 否 | 未验证真实 TLS/公网可达性 |
| L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_browser.py backend/tests/test_application.py backend/tests/test_application_actions.py backend/tests/test_application_context.py backend/tests/test_protocol.py backend/tests/test_server.py backend/tests/test_agents_graph.py --basetemp=artifacts/test-results/M07/integration-temp --junitxml=artifacts/test-results/M07/backend-integration.xml -q` | 62 passed；最终 HTTP/应用接口与关联模块回归 | mock 网络、真实临时 DB/合成目录 / 否 | 不重复无关全量测试，非 L4 |
| L1/L2 | `npx vitest run apps/desktop/tests/credentials.test.ts apps/desktop/tests/credential-sync.test.ts tests/integration/m02.test.ts --reporter=json --outputFile=artifacts/test-results/M07/credentials-integration.json` | 25 passed | fake safeStorage、真实 Python stdio/SQLite / 否 | 首轮复用 M02 测试的临时 DB 仍按旧路径在 M02；后已允许结果目录变量 |
| L2 | `$env:ORVIA_TEST_RESULTS='artifacts/test-results/M07'` 后 `npx vitest run tests/integration/m07-credentials.test.ts tests/integration/m02.test.ts --reporter=json --outputFile=artifacts/test-results/M07/stdio-final.json` | 10 passed；新增 Tavily 加密重载/删除、配置与三个角色隔离、真实 stdio 替换且不落 DB | fake safeStorage、真实 stdio/SQLite / 否 | 不验证供应商搜索可用性 |
| L2 | 设置 `ORVIA_BROWSER_TEST=1`、`ORVIA_BROWSER_TEST_CHANNEL=msedge` 后 `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_browser_engine.py --junitxml=artifacts/test-results/M07/engine-unicode-final.xml -q` | 最终 4 passed；真实 Edge Chromium 154.0.4258.37 渲染 JS、相对资源、阻止写/越界/二次导航及预算 | 真实引擎，合成 HTTP/DNS mock / 否 | 不是配套 Chromium 或真实站点验收；默认 pytest 跳过此显式测试 |
| L3 | `$env:ORVIA_TEST_MODULE='M07'` 后 `npx playwright test tests/e2e/m07.spec.ts` | 1 passed；真实 Electron、Windows safeStorage、私有 Python 同步；e2e.json / settings.png（已视觉检查） | 无加密/通信 mock，仅合成 Key / 否 | 未验完整安装包或发布 UI 的凭据操作流程 |

已有 LangGraph 依赖的序列化弃用提示保留，没有因 M07 改动静默替换依赖行为。没有调用真实模型，不增加模型费用。

### 失败与修复

- 最初用于批量修改的 Python 命令默认 GBK 解码失败，尚未写入文件；改用 `-X utf8` 后完成。后续统一 UTF-8，不影响用户改动。
- `python -m playwright install chromium` 因官方 CDN 超时失败；随后 `python -m playwright install chromium --only-shell` 也失败，记录 chromium-install.log。未关闭证书验证或改网络配置。显式选择本机 Edge 仅用于测试，产品默认仍为配套 Chromium，缺失会报告 PLAYWRIGHT_FAILED。
- 初始真实引擎测试 1 通过、2 失败（engine.xml）：合成页面缺 UTF-8 声明导致乱码；被拒绝的表单导航使定位器等待导航。修正合成页面编码，固定只读提取不再依赖定位器导航等待，并增加 CSP sandbox。失败项最小重跑保留 engine-retry.xml；策略变化后重跑 3 项，engine-final.xml 全通过；最终审查补上 UTF-16/UTF-8 emoji 截断与孤立代理项处理，4 项目标用例全部通过（engine-unicode-final.xml）。
- HTTP 到浏览器的文档重定向在启动页面前由网关解析，浏览器以最终 URL 建立文档，避免相对脚本路径与来源不一致。每一资源重定向都扣减共享请求/字节预算。

### 完成边界与本地提交

本轮只读工具流程、程序边界、文档与对应验证完成，不声称真实 Tavily/公网兼容性、配套 Chromium 安装或 M08 发布验收完成。默认动态读取需要安装匹配 Chromium；当前本机配套下载未成功。跨源 CDN、登录、验证码、互动内容、非 UTF-8 HTTP 文本、持续轮询页面可能受限或失败；公开 GET 不保证网站侧零副作用。Browser 不自动启动模型、不自动把网页写入索引。

本地提交使用 `git -c user.name='踪显' -c user.email='18532112451@163.com' commit -m "feat(M07): add restricted browser search and page reading"`，具体哈希由最终交付回执和 git log 确认。提交前显式选择 M07 文件，检查 status / diff / diff --cached 与空白、敏感信息及忽略路径；LICENSE 预存删除不在索引。用户手动 push 待执行，Agent 本轮无任何 push。M07 完成后停止等待，不开始 M08。

提交前卫生检查：31 个显式暂存文件，无禁止路径；扫描暂存内容与当时 101 个 M07 产物，真实开发 Key 匹配均为 0（仅检查存在性、不输出值）。三个模型变量存在，Tavily 未配置。staged-hygiene.json 保存计数；代码/报告/截图均无真实 Key，数据库、日志和截图未暂存。最终仅 Browser Unicode 边界与相关测试、记录追加，复核暂存差异后创建本地提交。


### M07 配套 Chromium 安装恢复（2026-09-28）

用户要求重新尝试安装。首次以默认 30 秒连接上限重试仍失败（chromium-install-retry.log）；随后只对当前安装进程设置 `PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=60000`，运行 `backend/.venv/Scripts/python.exe -m playwright install chromium --only-shell`，退出码 0。配套 Chromium Headless Shell 153.0.8010.12（revision 1243）与所需辅助组件安装完成，日志 chromium-install-retry-60s.log。未修改系统网络/TLS 配置，未关闭证书验证，未更换 Playwright 版本。

L2：设置 `ORVIA_BROWSER_TEST=1` 并清除 `ORVIA_BROWSER_TEST_CHANNEL` 后，运行 `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_browser_engine.py --junitxml=artifacts/test-results/M07/engine-bundled-chromium.xml -q`，**4 passed**。使用真实配套 Chromium，HTTP/DNS 为合成 mock，无真实模型或 Tavily 调用。覆盖动态正文、相对脚本路径、写/越界请求、导航/数量预算和 Unicode 截断。默认动态读取的运行时缺失限制解除；公网兼容性与 M08 安装包验收仍未覆盖。

本次源码、依赖锁均无变化，仅更新根 README、Browser README、开发清单及本记录。L0 检查 Git status、diff、暂存差异与空白；安装日志/测试报告在忽略的 M07 目录，未暂存密钥、数据库、用户文件或测试产物。使用指定作者创建本地文档提交，用户手动 push 待执行；LICENSE 预存删除继续未暂存，M08 未开始。


## M08 安装包与整体验收（2026-09-28）

### 构建与资源

- PyInstaller 6.22.3 onedir + console：`artifacts/test-results/M08/build/python/orvia-backend/`，运行时清除 `PATH/PYTHONPATH/PYTHONHOME` 后可握手。依赖包含 SQLite FTS5、jieba、trafilatura、Playwright。
- Playwright 1.63.0 配套 Chromium Headless Shell 153.0.8010.12/revision 1243、ffmpeg 1011、winldd 1007 复制至 `resources/chromium`；`runtime-manifest.json` 记录版本。
- electron-builder 26.15.3 / Electron 44.4.5 生成 `Orvia-0.1.0-win-x64-setup.exe`（约 274 MB）和 `win-unpacked` 目录包。资源白名单仅含 dist、后端、Chromium、manifest 和许可证；不执行 publish。

### 验证

| 级别 | 命令 | 结果 | 边界 |
|---|---|---|---|
| L0 | `npm run check`；`uv lock/sync --group packaging`；PyInstaller；electron-builder | 通过；依赖锁定、构建日志和包产物在 M08 目录 | 未签名，默认图标；不是发布渠道验收 |
| L1/L2 | `vitest run apps/desktop/tests/runtime.test.ts apps/desktop/tests/backend.test.ts apps/desktop/tests/credentials.test.ts` | 通过；发布资源定位、进程生命周期、safeStorage | 模拟生命周期与合成密钥 |
| L2 | `pytest backend/tests/test_frozen.py backend/tests/test_browser.py backend/tests/test_context.py backend/tests/test_agents_graph.py` | 42 passed；冻结 EXE、SQLite/FTS5、Browser、LangGraph 审批恢复 | 临时合成资料；无真实用户文件/模型 |
| L3 | `ORVIA_PACKAGED_EXE=.../install-smoke/Orvia.exe ORVIA_TEST_MODULE=M08 npx playwright test tests/e2e/m08.spec.ts` | 1 passed；隔离安装版窗口、safeStorage、草稿重启、随包 Chromium data 页面 | 无真实网络/模型；非独立机器 |
| L3 | `m08-install.ps1 -Stage Install` / `-Stage Uninstall` | 安装与静默卸载均 exit 0；installation.json、uninstallation.json | 只操作本轮隔离目录，未覆盖已有安装 |
| L0 | 包内容审查 `package-hygiene.json` | 扫描 5625 个包/冻结资源文件；真实合成 Key 0，禁止用户文件路径 0 | 环境变量名/依赖许可证文本可能出现，非密钥值 |

### 重要限制

当前无法获得无开发环境的独立 Windows 机器；本机采用清空开发 PATH、显式隔离 userData、实际安装/卸载和冻结后端进程验收。安装器未签名，完整证书、杀毒软件、升级/回滚和多用户安装行为未验收。未调用真实模型、Tavily 或真实互联网网页，不产生供应商费用。

M08 使用固定发布后端资源路径和 `PLAYWRIGHT_BROWSERS_PATH`，不读取系统 Python、用户浏览器配置、`.env.local` 或普通环境 Key。安装版用户数据只写 userData，卸载保留用户数据策略由 electron-builder 配置决定。未发布 GitHub Release。

## M09 桌面整理用户界面闭环（2026-09-28）

### 实现范围

- [x] √ 主进程新增系统目录选择与授权流程；绝对路径仅在主进程和 Python Computer gateway 间流转，renderer 只得到任务/授权 ID、目录名摘要和剩余预算。
- [x] √ BackendClient/preload/contextBridge 接入固定 `computer.grant`、`computer.status`、`computer.execute` 适配；renderer 只允许四个 Computer 只读工具，未开放通用 IPC、Node、命令或写操作。
- [x] √ UI 完成授权目录、扫描进度/部分结果、文件列表、文件名搜索、文件属性、空间统计、大文件清单，以及空结果、截断、不可访问、权限/越界/失败提示。
- [x] √ 新增 M09 合成目录集成测试和真实 Electron E2E；开发测试目录通过 `ORVIA_TEST_DIRECTORY` 注入，发布模式仍强制系统目录选择器。
- [x] √ 更新桌面 README 与开发计划；未开始 M10。

### 分级验证

测试结果放在 Git 忽略的 `artifacts/test-results/M09/`，未读取真实用户文件、未调用真实模型、Tavily 或互联网。

| 级别 | 实际命令 | 结果 | mock / 真实模型 | 未覆盖风险 |
|---|---|---|---|---|
| L0 | `npm run check`；`npm run build`；`git diff --check` | 通过 | 无 / 否 | 未重新构建安装包 |
| L1 | `npx vitest run apps/desktop/tests --reporter=dot` | 5 files, 30 passed | 进程与 IPC mock / 否 | 未覆盖系统原生选择器自动化 |
| L2 | `npx vitest run tests/integration/m09-computer-ui.test.ts --reporter=dot` | 2 passed | 临时合成目录、真实 Python/SQLite / 否 | 未覆盖真实用户权限变化组合 |
| L2 | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_computer_files.py backend/tests/test_computer_gateway.py backend/tests/test_application.py -q` | 8 passed, 1 skipped | 临时目录与既有测试 mock / 否 | 符号链接跳过项受 Windows 权限影响 |
| L3 | `$env:ORVIA_TEST_MODULE='M09'; $env:ORVIA_TEST_RESULTS='artifacts/test-results/M09'; npx playwright test tests/e2e/m09.spec.ts` | 1 passed；真实 Electron/Python 窗口闭环，已检查截图 | 合成目录 / 否 | 未验安装包版本的目录选择器 |

### 安全与边界

没有把 `.env.local`、真实 Key、数据库、日志、用户文件或测试产物加入 Git；M09 只读，不执行移动、重命名、创建目录、删除、审批、撤销或真实模型任务。空间统计为逻辑文件大小。错误消息不回显绝对路径或异常输入。`ORVIA_TEST_DIRECTORY` 仅在未打包开发进程生效，不能改变发布模式的系统选择器和 Computer 路径校验。

本地提交使用固定作者，用户手动 push 待执行；Agent 未执行 push。M09 完成后停止，不开始 M10。

## 对话式产品方向与计划修订（2026-09-28）

用户确认最终产品以对话框交互，并明确不做自动任务、技能广场等额外能力。本轮仅修订 DEVELOPMENT_PLAN 和本记录，未修改代码、依赖、接口或数据库，未开始 M10。

- [x] √ 明确侧栏新建/历史会话、欢迎页与输入框、消息流、任务卡片、详情面板和设置的分工。参考截图只作为布局参考，其文字与其他入口不构成开发授权。
- [x] √ M10 增加会话/消息持久化、任务关联与隔离、M09 只读卡片迁移，再接入真实任务编排和版本绑定审批；M10 全部实现项仍为未完成。
- [x] √ M11–M14 分别补充对话体验、会话内来源证据、附件与导出、对话流程发布验收；保留原安全边界、固定角色模型和逐模块停止规则。
- [x] √ 排除自动/定时/后台主动任务、技能与插件市场、管家团队管理、促销与推荐内容信息流，不设置虚假占位入口。

L0 文档检查：核对范围、模块依赖、未完成标记和历史记录，运行 `git diff --check`、`git diff`、`git status` 及暂存差异检查。按 AGENTS 文档-only 规则不运行代码测试；无 mock 或真实模型/网络业务调用，无测试产物。只暂存两份 Markdown，不包含密钥、数据库、日志、用户文件、LICENSE 或构建产物。使用固定作者创建本地文档提交；不 push，等待用户手动同步。此次计划修订不代表对话界面已实现，原 M09 验证不等于新对话流程验收。
