# 开发进度与验证证据

## 当前状态（2026-09-29，M15）

M15 有界文档摘要与多来源回答、M16 带引用简报、M17 代码生成/网页原型/旧临时文件隔离首批源码均已实现和验证，详见本文后续分节。最新安装包仍是 M14 未签名 0.2.0-rc.1，不包含 M15–M17；M14 生产签名和独立 Windows 验收仍暂缓。M18–M20 未开始。本地提交与用户手动 push 状态独立记录；Agent 不 push。

## 历史状态（2026-09-29，M13）

M01–M13已完成当前模块范围的实现与对应验证；M13本地提交见本轮交付回执，等待用户手动push，Agent不push。预检main、origin/main与远端默认main均为M12提交 `0cffa15f3840a92cd9fd3668b2b9bc63d10f322c`，确认用户已同步M12。未跟踪 `.zcodeignore` 保留，不提交；LICENSE未触碰。M14未开始，M08安装包仍为历史版本。M13详细证据见本文末节。

## 历史状态（2026-09-28）

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

## M10 对话式主界面、任务编排与审批闭环（2026-09-28）

### 实现与范围

起点为 main 分支 `4d269c9`，远端默认分支 main；本轮开始工作区干净，LICENSE 无待提交改动，全程未触碰 LICENSE。按用户修订后的计划只开发 M10，M11–M14 未开始。

- [x] √ 新建/历史会话、欢迎页、消息流、底部输入框和设置；M09 授权、扫描、搜索、属性、空间及大文件结果迁入对话卡片。没有自动任务、技能广场等额外入口。
- [x] √ SQLite 持久化会话、消息、Mission 关联和幂等请求；重启标记中断，不自动重放。会话与授权隔离，历史不会恢复文件访问权限。
- [x] √ 固定 Main 模型生成受限只读或整理提案，经 Application、Computer gateway 与 LangGraph 校验；计划、审批、执行核验、恢复和最近任务受限撤销形成闭环。聊天中输入“同意”不能执行操作。
- [x] √ 审批绑定最新操作及 SHA256 版本；核对授权根和源文件身份，拒绝重复来源/目标、错误目录创建顺序、旧审批和跨会话审批；不确定恢复拒绝继续。检查原始路径链，阻止链接、联接及越界。撤销记录部分完成状态。
- [x] √ renderer 仅使用固定类型 IPC；原生目录选择和授权在主进程完成。移除产品代码中的旧测试目录绕过，测试专用启动器独立模拟选择器；中文错误不回显内部路径。
- [x] √ 更新根、桌面、chat、Computer、agents README 及架构、清单；完成中文接口/边界注释和分级验证。

### 验证记录

所有报告位于 Git 忽略的 `artifacts/test-results/M10/`。自动化使用合成目录和临时数据库，不读取真实用户文件。下列重复目标验证与回归存在用例重叠，不能累加为独立测试总数。

| 级别 | 实际命令 | 最终结果与边界 |
|---|---|---|
| L0 | `npm run check`；`npm run build` | 通过，最终构建记录 build-final.log；未重新打包 |
| L1 | `npx vitest run apps/desktop/tests/chat.test.ts apps/desktop/tests/backend.test.ts apps/desktop/tests/protocol.test.ts --reporter=json --outputFile=artifacts/test-results/M10/desktop-unit.json` | 16 passed；进程/协议 mock，无真实模型 |
| L1 | `npx vitest run apps/desktop/tests/chat.test.ts --reporter=json --outputFile=artifacts/test-results/M10/chat-contract-final.json` | 最终错误映射调整后 5 passed |
| L2 | `npx vitest run tests/integration/m10.test.ts tests/integration/m09-computer-ui.test.ts --reporter=json --outputFile=artifacts/test-results/M10/stdio.json` | 3 passed；真实 Python stdio/SQLite，无真实模型 |
| L1/L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_application.py backend/tests/test_application_actions.py backend/tests/test_agents_graph.py backend/tests/test_computer_gateway.py backend/tests/test_computer_files.py backend/tests/test_computer_actions.py backend/tests/test_m10_action_safety.py backend/tests/test_chat.py backend/tests/test_protocol.py backend/tests/test_server.py -q --basetemp=artifacts/test-results/M10/integration-temp --junitxml=artifacts/test-results/M10/backend-final.xml` | 52 passed、1 skipped；Windows 符号链接权限相关既有跳过；模型 mock、合成文件 |
| L1/L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m10_action_safety.py backend/tests/test_computer_actions.py backend/tests/test_agents_graph.py -q --basetemp=artifacts/test-results/M10/conflict-temp --junitxml=artifacts/test-results/M10/conflicts-final.xml` | 最终冲突校验修改后 16 passed，含新增 3 项冲突用例 |
| L3 | 设置 `ORVIA_TEST_MODULE=M10`、`ORVIA_TEST_RESULTS=artifacts/test-results/M10` 后运行 `npx playwright test tests/e2e/m10.spec.ts tests/e2e/health.spec.ts tests/e2e/m02.spec.ts tests/e2e/m07.spec.ts tests/e2e/m09.spec.ts` | 最终 6 passed，0 flaky；真实 Electron/Python/SQLite/Windows safeStorage，模型与原生选择器 mock；截图已检查 |
| L2 真实模型 | `backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_m10_preflight.py --run-live` | 通过；仅固定 Main 的合成请求，三角色密钥只报告存在性 |
| L2 真实模型 | `backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_m10_plan.py --run-live` | 通过；固定 Main 对合成 sample.txt 生成重命名计划，最多 3 次请求、每次 1024 输出 token、零重试；未审批执行，源未变、目标不存在 |

E2E 覆盖独立审批、版本/会话拒绝、自然语言不能审批、重启重新授权、撤销、空目录、部分结果、模型失败、键盘输入及 800×650 窗口布局。旧 M01/M02/M07/M09 用户流程测试适配当前入口；M08 安装包测试保留历史语义。未调用真实 Computer/Browser 模型或 Tavily；mock 执行闭环与真实 Main 规划验收分别记录，不等价于三角色真实端到端验收。

开发中发现并修复 React 19 useRef 初始化类型错误、M03 错误码测试断言大小写和嵌套结果裁切问题；相关目标重跑通过，无未解决测试失败。已有 LangGraph 弃用提示保留。

### 试用与已知限制

在项目根运行 `npm run build`，然后 `npm start`。配置固定 Main 凭据，新建对话，选择专用测试目录，发送扫描或重命名需求；检查计划后用独立按钮审批，再查看核验与撤销结果。首次未授权的提问会请求选择目录，选择后需要再次发送需求。

- 只有 Main 在本轮使用模型；Computer 执行受限程序工具，Browser 不参与本轮会话任务。
- 历史快照最多 30 条消息且受 46 KiB 限制，无分页；每会话最多 100 次发送，结果截断会提示。
- 当前为阶段状态展示，没有逐 token 流式输出、取消或自动重连，这些留待 M11。
- 旧版缺少身份/版本的动作计划返回 STALE_PLAN，必须重新生成；外部进程并发替换路径仍存在操作系统层竞态限制。
- 原生目录选择器通过 mock 自动化，未读取真实用户目录；未重新生成安装包，旧 M08 安装器不包含本轮 UI。

本轮使用固定作者创建本地提交 `feat(M10): add conversational file tasks and versioned approvals`，哈希以最终回执与 git log 为准。提交前显式暂存本模块文件并检查 status、diff、cached diff、空白及敏感信息；最终卫生检查见本节后续记录。Agent 不执行 push，等待用户手动推送；M10 完成后停止。

提交前卫生检查通过：41 个显式暂存文件，禁止路径 0，暂存内容中的真实开发密钥匹配 0；扫描 1280 个本轮产物，真实密钥匹配 0。仅输出三角色凭据存在性，未输出值。结果保存于忽略的 hygiene.json；密钥、数据库、日志、用户文件、测试产物及 LICENSE 均未暂存。最终文档补记不触发代码测试重跑。

## M11 稳定性与对话体验（2026-09-28）

### 起点与实现

用户要求继续开发，并明确手动 push 失败以后再处理。预检为 main 分支、HEAD `6a52336`，工作区干净；本地远端 HEAD 记录为 origin/main。未联网处理 push、未修改 TLS/网络配置；LICENSE 无改动。仅实施 M11，不开始 M12。后端稳定性和 renderer 体验分别委派独立子 Agent，主 Agent 完成主进程整合、验收及本地提交。

- [x] √ 固定 chat.cancel 仅取消匹配会话/请求的模型等待，持久化取消终态；相同请求不重复调用。计划入库、审批执行及撤销不可取消，模型超时不再包围数据库事务。
- [x] √ 私有 stdio 普通请求保序串行，上限32；健康与取消可旁路。增加固定数据库忙、磁盘满、权限、连接超时/退出错误提示，异常原文不泄漏；初始化失败不发布半就绪后端。
- [x] √ 手动重新连接：确认旧进程退出后启动同一数据目录的新实例，不重放任务，不恢复授权。忙碌时拒绝重连；窗口关闭有界清理自有后端；保留单实例及重复启动聚焦。
- [x] √ renderer 重载显示活动规划、支持有效阶段取消；主进程保存活动请求标识，页面不自动再次发送。规划错误后通过明确按钮发起新请求，不自动重试审批/恢复/撤销。
- [x] √ 对话状态和最近10项操作历史，区分草稿/处理中/待审批/完成/失败/中断/取消/撤销；当前最新操作才可能受限撤销。快速审批返回时同步侧栏状态。
- [x] √ 历史阅读保持滚动位置、最新消息按钮、长消息/列表折叠、焦点恢复、中文输入法保护、设置焦点循环/Escape、760×560窄窗口布局。
- [x] √ 根/桌面/chat README、架构和开发清单更新；不增加 Browser 搜索、附件、自动任务或技能广场。

### 分级验证

报告统一为 Git 忽略的 `artifacts/test-results/M11/`。全部业务验证使用合成文件、隔离数据库与模型 mock；没有真实模型、Tavily 或真实用户文件调用。M10 真实 Main 合成验收作为既有结论保留，本轮未重复调用。

| 级别 | 实际命令 | 结果与边界 |
|---|---|---|
| L0 | `npm run check`；`npm run build` | 最终通过；build-final.log，包含构建前类型检查；未重新打包 |
| L1/L2 | 设置 `ORVIA_TEST_RESULTS=artifacts/test-results/M11` 后 `npx vitest run apps/desktop/tests/backend.test.ts apps/desktop/tests/chat.test.ts apps/desktop/tests/m11-contracts.test.ts apps/desktop/tests/m11-ui.test.ts apps/desktop/tests/protocol.test.ts apps/desktop/tests/credential-sync.test.ts tests/integration/m10.test.ts tests/integration/m09-computer-ui.test.ts --reporter=json --outputFile=artifacts/test-results/M11/desktop-final.json` | 29 passed；进程生命周期/凭据同步 mock、真实 Python stdio/SQLite/M03 网关 |
| L1/L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m11_stability.py backend/tests/test_server.py backend/tests/test_chat.py backend/tests/test_application.py backend/tests/test_application_actions.py backend/tests/test_agents_graph.py backend/tests/test_m10_action_safety.py backend/tests/test_protocol.py -q --basetemp=artifacts/test-results/M11/backend-final-temp --junitxml=artifacts/test-results/M11/backend-final.xml` | 62 passed；取消去重、历史上限、数据库/磁盘/权限故障注入、网络不可用与模型超时、初始化失败、旧审批及恢复相关回归 |
| L3 | 设置 `ORVIA_TEST_MODULE=M11`、`ORVIA_TEST_RESULTS=artifacts/test-results/M11` 后 `npx playwright test tests/e2e/m11.spec.ts tests/e2e/m11-ui.spec.ts tests/e2e/m10.spec.ts tests/e2e/m09.spec.ts` | 最终 6 passed、0 flaky（45.7秒）；真实 Electron/Python/SQLite，模型与原生目录选择 mock，合成文件真实读写 |

L3 覆盖：取消匹配/错标识拒绝/取消后幂等；运行中重载不重发；后端进程真实故障终止后手动重连且授权丢弃；窗口关闭确认自有子进程消失，再次启动中断不重放；实际第二实例退出；原 M09/M10 扫描、审批、核验、撤销；滚动保持、折叠、IME、焦点循环及显式规划重试。已检查 reconnected.png、narrow-completed.png、ui-narrow.png。没有执行独立机器/安装包 L4，匹配范围回归已覆盖本次改动。

早期并行开发时类型检查遇到 renderer 尚未完成的 JSX 语法错误，整合后通过。首轮6项 E2E通过，但截图检查发现快速审批后侧栏状态可能滞后；修复为快照同步，并添加状态断言及第二实例验证，最终同范围6项再验通过。已有 LangGraph 弃用提示与 Node NO_COLOR/FORCE_COLOR 提示保留，无未解决测试失败。单元/定向预跑与最终结果重叠，不累加测试数。

### 试用、风险与停止点

项目根 `npm run build` 后 `npm start`。在专用测试目录中观察与规划，模型等待时可“取消规划”；失败后可明确“重新尝试规划”。连接异常时“重新连接”，核对中断事实、重新选择目录，再决定重新提问或对已审批的中断任务进行受限恢复。历史记录不授予访问或重放权限。

取消仅支持模型等待，不是文件动作回滚；收到不可取消说明时等待并查看最终状态。重新尝试规划是新的模型请求，可能产生费用。无 token 流式输出、自动重连、历史分页或托盘；最近消息30条/46 KiB、任务摘要10条的限制保持。真实供应商取消计费、物理磁盘满、真实 ACL 组合与独立 Windows 机器未验收，相关故障通过受控注入验证。M08 历史安装包未重建；外部并发路径替换及不确定文件系统/数据库事务仍按原安全边界保守拒绝恢复。

本轮使用固定作者创建本地提交 `feat(M11): improve conversation stability and recovery`，具体哈希以最终回执和 git log 为准。提交前检查 status、diff、cached diff、空白和敏感信息，显式选择模块文件，卫生检查结果后附。用户手动 push 失败状态保留待处理；Agent 未执行 push。M11 完成后停止，M12 未开始。


## M12 Browser 搜索、来源与证据工作流（2026-09-29）

### 预检与范围

用户确认已手动 push 并授权继续。预检 main/HEAD/origin/main 同为 `b7f9980`，远端为 https://github.com/Kr1sxu/Orvia，默认分支 main；M11 已同步，历史失败记录保留为历史事实。开始时工作区干净，LICENSE 无本轮改动。完成中文模块/目标/文件/验证/停止点说明后只实施 M12，M13/M14 未开始。

开发中出现用户/外部工具生成的未跟踪 `.zcodeignore`。曾错误尝试清理，现已按读取内容恢复并保留，不纳入本模块提交。Agent 不处理 push，不修改网络或 TLS 配置。

### 实现与边界

- [x] √ 同一对话输入框提供文件任务、搜索网页、读取网页、询问已有来源；直接创建网页会话不要求目录授权。Tavily 状态、缺凭据、空结果、拒绝、失败和截断明确显示。
- [x] √ 固定 `chat.browser.search/read/ask/source` 与 preload 窄接口。主进程校验来源/frame/参数数目/strict 契约和串行锁；renderer 仍无 Node、通用 IPC、直接联网、路径、脚本或 Cookie 能力。
- [x] √ 复用 M07 SafeHTTP/BrowserService，URL、DNS 固定 IP、重定向、资源类型、限时和字节预算保持；HTTP 优先、动态 Playwright 只读。标题与正文在动态页面内先限长，React 仅渲染文本。
- [x] √ 新增 EvidenceStore，app.sqlite 内保存任务隔离的不可变来源版本、URL、访问时间、标题、模式、正文、错误和 SHA256。相同版本去重；搜索摘要和正文分别保存，新内容保留旧引用。去重版本保留首次访问时间，新请求事件记录本次时间。
- [x] √ M06 FTS 索引使用 browser:<evidence_id>，来源追问返回当前会话最多5条匹配原文和引用，支持证据详情反查；无匹配明确返回空结果。它是关键词检索，不是生成式总结/任意语义问答，也不调用 Browser 模型。
- [x] √ 搜索/读取/追问复用100次会话请求预算、请求占位、去重和中断状态；相同 request_id 不重放网络，重启不恢复目录权限。source/source_request 不进入 Main 文件规划上下文；没有网页驱动的文件操作或审批。
- [x] √ 消息最近30条/46 KiB，来源目录最多20项且先限制为12 KiB，卡片预览180字符，详情最多8000码点，长文折叠；修正 TS/Python 对 emoji 计数差异。
- [x] √ 更新根、桌面、chat、Browser README、架构、开发计划和进度。没有自动任务、技能广场、登录、附件、导出、页面写操作或安装包发布。

### 分级测试与证据

全部产物在 Git 忽略的 `artifacts/test-results/M12/`。测试使用合成网络响应、假凭据和临时数据库；真实组件为 Electron 窗口、Python 私有 stdio、SQLite/FTS、M07 网关及配套 Chromium。无真实模型、Tavily、互联网网页或用户文件读取。M10 文件回归仅修改专用合成目录。

| 级别 | 实际命令 | 结果 |
|---|---|---|
| L0 | `npm run check`；`backend/.venv/Scripts/python.exe -m compileall -q backend/src`；`npm run build` | 通过；最终构建含类型检查，build-final.log |
| L1/L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m12_browser_chat.py backend/tests/test_browser.py backend/tests/test_chat.py backend/tests/test_m11_stability.py -q --basetemp=artifacts/test-results/M12/pytest --junitxml=artifacts/test-results/M12/backend.xml` | 首轮72 passed；mock DNS/HTTP、真实 SQLite/FTS，会话/文件边界回归 |
| L1/L2 增补 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m12_browser_chat.py -q --basetemp=artifacts/test-results/M12/pytest-final2 --junitxml=artifacts/test-results/M12/backend-m12-final.xml` | 最终9 passed，与首轮8项重叠；增加磁盘故障后证据保留/重启/拒绝重放 |
| L1/L2 | 设置 `ORVIA_TEST_RESULTS=artifacts/test-results/M12`，`npx vitest run apps/desktop/tests/m12-contracts.test.ts apps/desktop/tests/chat.test.ts apps/desktop/tests/m11-contracts.test.ts tests/integration/m12.test.ts tests/integration/m10.test.ts --reporter=json --outputFile=artifacts/test-results/M12/desktop.json` | 13 passed；真实 Python/stdio 契约、无 Key 拒绝、持久化和跨会话隔离 |
| L1 Unicode 修复 | `npx vitest run apps/desktop/tests/m12-contracts.test.ts --reporter=json --outputFile=artifacts/test-results/M12/unicode-contracts.json` | 3 passed，与上述集合重叠；8000个 emoji 合法，8001个拒绝 |
| L3 | 设置 `ORVIA_TEST_MODULE=M12`、`ORVIA_TEST_RESULTS=artifacts/test-results/M12`，`npx playwright test tests/e2e/m12.spec.ts tests/e2e/m10.spec.ts` | 初轮3通过/1失败：M10两项与 M12正常流程通过；M12长正文详情失败，原因见下 |
| L3 定向修复 | 同样环境，`npx playwright test tests/e2e/m12.spec.ts -g '缺搜索凭据'` | 1 passed；Unicode 边界修复后验证，6.9秒 |
| L3 最终 UI | 同样环境，`npx playwright test tests/e2e/m12.spec.ts` | 2 passed，13.0秒；长文折叠/来源目录预算调整后，正常和错误流程均通过 |
| L2/L3 动态读取 | 设置 `ORVIA_BROWSER_TEST=1`，`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_browser_engine.py -q --basetemp=artifacts/test-results/M12/chromium-final-temp --junitxml=artifacts/test-results/M12/chromium.xml` | 4 passed（5.59秒）；动态标题页面内限长后定向通过，真实引擎、mock DNS/HTTP |

以上重跑不重复累加：Python业务去重73项，配套Chromium4项，Vitest13项，Electron4个不同流程。最初搭建的2项来源测试暴露摘要索引被同URL正文覆盖，已改为不可变版本独立索引并用9项测试替换。初轮 TypeScript 发现 unknown 条件渲染，已转显式 Boolean；长正文详情失败来自 TS UTF-16 与 Python 码点计数不一致，修复并加入 emoji 断言。最终无待修复测试失败，既有 LangGraph 弃用提示和 Node 颜色环境提示不影响结果。E2E JSON 随定向运行覆盖，原始批次结果和差异记录在 verification.md，不能把最后定向报告当成四项全跑。已查看 sources-narrow.png、isolated-empty.png、truncated-evidence.png；无横向溢出，长文按需展开。未做独立机器/安装包 L4。

### 试用与限制

项目根 `npm run build` 后 `npm start`。对话输入框选择“读取网页”，输入公开 URL 并发送；或配置 Tavily 后选择“搜索网页”，展开摘要，点击“读取此网页”后“查看证据”。选择“询问已有来源”输入简短关键词，查看原文引用与访问时间；重启后从历史会话继续查阅。网络访问由这次用户动作发起，不需要本地目录授权。

本轮不是模型网页总结，问句长或词形不匹配时可能无结果；来源没有自动事实核验，历史版本与搜索摘要均按类型和时间标记。来源目录/消息有界无分页，旧证据可经关键词检索返回；无搜索/读取取消、自动重试或后台任务。来源与 FTS 分别提交，存储中断可留下来源但索引未完成，读取现有证据不丢失，显式重读相同版本重建索引；不会自动联网修复。未验证真实 Tavily 服务和互联网兼容性，未重建 M08 安装器，固定角色模型配置不变。

本轮固定作者本地提交主题为 `feat(M12): add conversation browser sources and evidence`，哈希以 git log 和交付回执为准。提交前显式选择 M12 文件、检查 status/diff/cached diff 与敏感信息，产物不入 Git。Agent 未 push；本轮完成后等待用户手动 push，M13 未开始。


提交前差异检查还修正两处对话边界：来源请求中断不显示更早文件需求的“重试规划”，点击来源卡片读取网页不清空未发送草稿。加入保留草稿 E2E 断言后，重新构建通过；同样 M12 环境下 `npx playwright test tests/e2e/m12.spec.ts -g '搜索、引用'` 定向1 passed（9.0秒）。报告 e2e.json 为该最后定向结果，不累加流程数。M12两项流程、M10两项流程均已有通过证据。无待运行后台测试。

提交前卫生检查通过：30 个模块文件显式暂存，禁止路径 0，暂存真实密钥匹配 0，706 个本轮产物中真实密钥匹配 0。仅报告凭据存在性，Tavily 当前未配置；未输出凭据值。LICENSE、.zcodeignore、数据库、日志、用户文件和测试产物均未纳入索引。git diff --cached --check 通过；报告 hygiene.json 被 Git 忽略。

## M13 文档内容处理、引用与导出（2026-09-29）

### 预检与实现

`git status --short`仅有未跟踪`.zcodeignore`；main与origin/main同为`0cffa15`。`git ls-remote --symref origin HEAD refs/heads/main`确认远端默认main也为同一M12提交，用户手动push已生效。全程不触碰LICENSE，不暂存`.zcodeignore`，不push、不修改TLS/网络配置、不重写历史。读取AGENTS、根/架构/计划/进度与相关模块README后按M13范围实施，M14未开始。

- [x] √ 对话显式单附件选择、解析状态、原文引用、详情、导出预览与核验卡片。renderer隔离不变，主进程严格参数/来源检查及原生选择器授权，不开放任意路径/IPC。
- [x] √ PDF文本、无文本层扫描PDF与PNG/JPEG离线OCR、DOCX段落、PPTX实际幻灯片顺序；10 MiB/50单元/8000码点、44 KiB序列化预算，45秒固定解析子进程。无原文副本/解压临时目录，异常子进程回收；Office宏/加密/外部关系与ZIP/XML不安全输入拒绝。
- [x] √ 复用Computer gateway/PathPolicy的路径与句柄校验，单文件读取不建立父目录grant；Application/ChatService继续负责会话锁、100次预算和幂等。请求日志只存摘要，不存绝对附件/导出路径。
- [x] √ 复用M12不可变版本、归属与首次时间，独立document表与文件/内容SHA256；M06按文档版本/单元索引。OCR分数、普通文本无分数、缺失与截断分开记录，Word用段落不虚构页码。附件/网页不进入Main文件规划历史，不改变三个固定模型配置。
- [x] √ 单文档Markdown/JSON引用原文导出，覆盖指已提取非空单元都有引用，不是事实正确率或全文覆盖率；主进程最近预览一次性校验，原生保存框明确确认，后端再验证revision/路径，以独占新建、fsync与读回核验拒绝覆盖。导出不属于M04整理撤销，不生成Office/PDF成品。
- [x] √ 新增文档模块中文README、更新根/桌面/后端/Computer/Chat/Browser/Context/测试说明、架构和清单；仅在允许测试目录放测试，合成文档/报告归档M13。

本轮将解析器及桌面边界委派给独立子Agent，文件所有权分开；主Agent实现安全网关/存储/应用、整合验证与提交。子Agent未收到或读取真实Key。主Agent存在性预检结果为三模型Key存在，Tavily不存在，仅记录布尔值；M13不需要这些凭据，不构成阻塞。

### 分级验证与证据

以下均为合成文档/临时数据库。云端模型、Tavily、真实互联网调用为0；RapidOCR实际本地ONNX推理不是三角色供应商调用。系统原生选择器在E2E启动器中mock，产品无测试授权后门。精确命令均在项目根运行，报告均Git忽略。

| 级别 | 实际命令 | 结果与证据 |
|---|---|---|
| L0 | `.venv/Scripts/uv.exe lock --project backend --check`；`npm run check`；`npm run build`；`git diff --check` | 通过；新增依赖已锁定安装；构建包含最终导出卡片与255字符文件名契约。无安装器构建 |
| L1 | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_m13_parser.py -q --junitxml=artifacts/test-results/M13/parser.xml` | 18 passed；真实PDF文本、PNG/JPG/扫描PDF离线OCR、Office顺序/段落、截断/缺失、ZIP/XML、真实子进程/超时；逃逸字节预算和spawn异常使用mock。合成内容主要在内存中 |
| L1/L2 | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_m13_documents.py backend/tests/test_m12_browser_chat.py -q --basetemp artifacts/test-results/M13/backend-temp --junitxml artifacts/test-results/M13/backend.xml` | 首轮15 passed/1 failed；唯一失败为测试自身app.gateway属性误用，不是产品失败 |
| L1/L2 定向 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m13_documents.py::test_mock_parser_failure_partial_metadata_and_main_history_boundary -q --basetemp artifacts/test-results/M13/backend-retry-temp --junitxml artifacts/test-results/M13/backend-retry.xml` | 修正为app.chat.gateway后1 passed；OCR元数据与Main隔离mock |
| L2 新增边界 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m13_documents.py::test_attachment_idempotency_shared_budget_and_interrupted_claim -q --basetemp artifacts/test-results/M13/backend-budget-temp --junitxml artifacts/test-results/M13/backend-budget.xml` | 1 passed；附件同请求幂等、参数冲突、共享预算、持久化中断不重放。上述去重M13 9项、M12 8项全部有通过证据 |
| L1 Computer回归 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_computer_gateway.py backend/tests/test_computer_files.py -q --basetemp=artifacts/test-results/M13/computer-temp --junitxml=artifacts/test-results/M13/computer.xml` | 4 passed/1 skipped，符号链接真实创建受Windows权限限制；M13父重解析拒绝另外用mock覆盖 |
| L1 | `npx vitest run apps/desktop/tests/m13-contracts.test.ts apps/desktop/tests/m12-contracts.test.ts apps/desktop/tests/chat.test.ts` | 12 passed；文档路径/字段白名单、Unicode/方法/引用、纯文本渲染与既有契约回归 |
| L1/L2 | `npx vitest run tests/integration/m13.test.ts apps/desktop/tests/m13-contracts.test.ts tests/integration/m12.test.ts --reporter=json --outputFile=artifacts/test-results/M13/desktop-integration.json` | 6 passed；真实Python/stdio、SQLite/FTS、导出字节/拒覆盖/隔离/重启，与M12无Key及拒绝URL回归 |
| L3 | 设置`ORVIA_TEST_MODULE=M13`、`ORVIA_TEST_RESULTS=artifacts/test-results/M13`后，`npx playwright test tests/e2e/m13.spec.ts tests/e2e/m12.spec.ts tests/e2e/m10.spec.ts` | 首轮5 passed/1 failed；M10两项、M12两项、M13真实OCR均通过；失败为测试将无附件新对话的提示误写成空结果卡片。首轮报告保留e2e-initial.json |
| L3 定向 | 同环境，`npx playwright test tests/e2e/m13.spec.ts -g '选择附件'` | 修正测试预期后1 passed；新增导出卡片与主进程未预览拒绝断言后再定向1 passed（10.4秒）。验证选择/引用/预览/新建/拒覆盖/重启/隔离/760px窗口，报告e2e.json为最后定向结果 |
| L1/L2 导出卡片 | `npx vitest run apps/desktop/tests/m13-contracts.test.ts tests/integration/m13.test.ts --reporter=json --outputFile=artifacts/test-results/M13/export-final.json` | 5 passed；新增导出消息契约后真实stdio验证 |
| L1 最终边界 | `npx vitest run apps/desktop/tests/m13-contracts.test.ts --reporter=json --outputFile=artifacts/test-results/M13/export-contract-final.json` | 5 passed；额外覆盖合法255字符文件名不会在新建后被TS响应拒绝、无引用假成功消息拒绝及导出卡片渲染 |

重复执行不累加：Python去重39项通过/1项跳过；Vitest去重15项通过；Electron去重6项通过。初期PDF文本测试暴露pdfium对象不支持所用context-manager形式，已使用closing修正后18项验证通过；无待修复失败。未做L4全量/独立Windows/发布包验证，因为本轮不涉及发布验收。已查看document-export-narrow.png与ocr-evidence.png，窄窗口无横向溢出、输入区可用，OCR与置信度可见；导出卡片另有DOM/契约断言。

旧M12测试脚本有固定输出路径，首轮回归曾写入M12目录并刷新同名三张回归截图；已修正为读取ORVIA_TEST_RESULTS，本轮新生成profile/stdio目录及截图副本归档 `artifacts/test-results/M13/m12-regression/`，历史其他证据保留。该调整只影响测试产物路径，无用户文件访问。

### 试用、风险与提交状态

先 `.venv/Scripts/uv.exe sync --project backend --locked`，再 `npm run build`、`npm start`。选择“＋ 添加附件”提供人工合成PDF/DOCX/PPTX/图像，展开“查看文档证据”；“询问文档”输入简短关键词；预览Markdown/JSON、核对缺失/截断/覆盖后选择新路径确认。历史会话可重新查看已保存内容，原文件/目录权限不会恢复。导出卡片显示当时文件名、内容哈希及引用，不监测外部修改；取消或再次保存需重新预览。

限制：本轮只有原文提取和关键词检索，没有模型总结、多附件/网页合并报告、Office/PDF成品、完整标书；旧DOC/PPT、宏/加密/含外部关系的Office拒绝。OCR可能误识，混合PDF页内图片不额外OCR，复杂表格/公式/布局不保真；Word按段落而非物理页。数据保留本地DB/FTS，无自动历史删除；子进程只在内存处理原始字节。路径校验不是OS沙箱，不能消除所有外部进程竞态。中断导出可能留下部分新文件，程序不会覆盖重试；需人工核对。M08安装包未更新，新增依赖冻结/独立机器验收留M14。

提交前敏感信息检查确认源码与M13产物无真实Key匹配，仅输出计数；`.env.local`、数据库、日志、用户文件和测试产物均不纳入Git。固定作者“踪显 <18532112451@163.com>”，本地提交主题 `feat(M13): add local document citations and safe exports`，哈希以交付回执/git log为准。显式暂存本轮文件并检查status/diff/cached diff；Agent未push，本轮完成后立即停止，等待用户手动push与后续指令。

最终暂存43个模块文件，禁止路径0、暂存真实密钥匹配0，扫描571个本轮产物密钥匹配0；`git diff --cached --check`通过，未暂存差异为空，工作区保留未跟踪`.zcodeignore`。敏感检查报告为忽略的 `artifacts/test-results/M13/hygiene.json`。本地提交与手动push状态分开记录，不把未推送写为已同步。

## M14 本机未签名候选版（2026-09-29）

### 授权、预检和停止范围

用户在了解生产签名和独立 Windows 环境后明确要求“先不做这两项工作，继续开发”。本轮交付本机未签名候选版，M14完整发布验收仍未完成；不发布Release，不push，不开始新模块。预检工作区仅`.zcodeignore`，main与origin/main均为`18749cc`；实时`git ls-remote --symref origin HEAD refs/heads/main`因SSL_ERROR_SYSCALL失败，未改TLS或网络配置，不能宣称实时远端同步。LICENSE和`.zcodeignore`均保留且不纳入提交。

### 实现与产物

- [x] √ Electron/后端版本更新为0.2.0-rc.1 / Python规范版本0.2.0rc1；锁文件保持依赖一致。新增CHANGELOG，未签名状态与安装、升级、卸载数据策略有中文说明。
- [x] √ 构建输出切换M14，补齐PyInstaller PDF原生库、RapidOCR权重/字典、ONNX Runtime资源及manifest版本。复用M13已有固定冻结worker入口，无重复实现，不改变权限或三个固定模型。
- [x] √ 本地NSIS安装器与目录包包含最新对话及文档流程；实际Authenticode状态NotSigned，未签名安装包不冒充正式发行。M08历史包保留。
- [x] √ 新增冻结解析/升级数据/发布包E2E/受限安装脚本；安装脚本验证隔离目标、重解析点、注册表、EXE与安装器哈希，不递归删除，不接管个人已有安装。
- [x] √ M08旧包真实安装到M14隔离目录，生成旧合成草稿；升级0.2.0-rc.1后读取旧数据、确认固定配置，并执行新会话附件/FTS；升级后的安装版4条流程通过。
- [x] √ 静默卸载成功，安装EXE和注册项移除；隔离合成app.sqlite卸载前后SHA256相同。没有读取/删除默认个人userData；保留数据不代表已清除隐私。

独立任务仅拥有m14.spec.ts和m14-install.ps1两个互不重叠文件；主Agent负责打包、整合、实际测试与提交。无凭据传递给子Agent。产物均在Git忽略的`artifacts/test-results/M14/`。

### 分级验证（命令在项目根执行）

| 级别 | 实际命令/设置 | 结果 |
|---|---|---|
| L0 | `.venv/Scripts/uv.exe lock --project backend`；`sync --project backend --locked --group packaging`；`lock --project backend --check`；`npm run check`；`python -X utf8 -m compileall -q backend/src packaging backend/tests/test_m14_frozen.py backend/tests/m14_package_audit.py`；`git diff --check` | 通过，版本与锁一致，Python使用backend/.venv/Scripts/python.exe |
| L0/L4 构建 | `npm run package:win` | 通过，含类型/前端构建、PyInstaller及NSIS；package.log；约329.4MiB未签名测试包 |
| L1/L2/L4 | `ORVIA_BROWSER_TEST=1`，`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests -q --basetemp=artifacts/test-results/M14/pytest --junitxml=artifacts/test-results/M14/backend.xml` | 202 passed/6 skipped；4条真实配套Chromium合成响应测试已启用，5项冻结测试随后单独运行，另1项符号链接权限跳过 |
| L2/L4 冻结 | `ORVIA_FROZEN_BACKEND=<M14/build/python/orvia-backend/orvia-backend.exe绝对路径>`，`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_frozen.py backend/tests/test_m14_frozen.py -q --basetemp=artifacts/test-results/M14/frozen-temp --junitxml=artifacts/test-results/M14/frozen.xml` | 5 passed；真实冻结PDF/DOCX/PPTX/OCR、FTS/审批/撤销/重启；PATH仅System32 |
| L1/L2/L4 | `ORVIA_TEST_RESULTS=artifacts/test-results/M14`，`npx vitest run apps/desktop/tests tests/integration --reporter=json --outputFile=artifacts/test-results/M14/vitest.json` | 首轮68 passed/1 failed；历史协议测试将已知LangGraph弃用提示当失败。仅允许该具体提示，其余stderr仍拒绝 |
| L2定向 | 同环境，`npx vitest run tests/integration/backend.test.ts --reporter=json --outputFile=artifacts/test-results/M14/vitest-retry.json` | 3 passed，含上述唯一失败项，其余重复不累加 |
| L3/L4源码 | 设置`ORVIA_TEST_MODULE=M14`和`ORVIA_TEST_RESULTS=artifacts/test-results/M14`，`npx playwright test --ignore-snapshots` | 初轮11 passed/2 failed/4 skipped；旧M08发布测试及尚未指定包的M14三项跳过。13个源码流程中失败为M07旧提示文案和M13 OCR场景启动超过默认5秒 |
| L3定向 | 同环境，`npx playwright test tests/e2e/m07.spec.ts tests/e2e/m13.spec.ts -g 'M07\|本地真实 OCR'` | 2 passed；修正文案后重跑，OCR无需产品修改即通过。初轮及重跑JSON分别保存e2e-development-initial.json / e2e-development-retry.json |
| L4 安装升级 | `powershell -NoProfile -File tests/integration/m14-install.ps1 -Stage InstallLegacy`；`-Stage VerifyPending`；`-Stage Upgrade` | 旧包安装成功但首轮注册表断言失败，保留pending；按下述修正并核对哈希后恢复记录；真实Upgrade成功，installation.json保留两代记录 |
| L2升级数据 | 升级前`ORVIA_UPGRADE_STAGE=seed`，升级后`verify`，各运行`npx vitest run tests/integration/m14-upgrade.test.ts --reporter=json --outputFile=artifacts/test-results/M14/upgrade-<阶段>-test.json` | 两阶段各1 passed/1按阶段跳过。加强固定模型models字段断言后仅重跑verify通过；不会将两端不存在的profiles字段相等作为证据 |
| L3/L4安装版 | 指定`ORVIA_PACKAGED_EXE=<M14/install-smoke/Orvia.exe绝对路径>`和上述M14报告环境，`npx playwright test tests/e2e/m14.spec.ts` | 4 passed，42.4秒；真实包safeStorage、导出拒覆盖/历史隔离、OCR、Chromium data页、扫描/权限重启失效、无Key/私有URL拒绝。e2e-installed.json |
| L4卸载及拒绝 | 已安装时`-Stage Install`返回拒绝覆盖（预期失败）；`-Stage Uninstall` | 卸载exit0，EXE及注册表已移除；独立合成profile哈希未变，uninstallation.json / uninstall-data.json |
| L0卫生 | `backend/.venv/Scripts/python.exe -X utf8 backend/tests/m14_package_audit.py`；`Get-AuthenticodeSignature <安装器>` | 只报告计数与SHA256；最终结果见后附。签名NotSigned，无真实云端调用 |

最终去重：Python207项通过/1项跳过；既有Vitest69项通过，加升级两个阶段为71项；源码Electron13条、安装版4条共17条通过。旧M08面板发布用例由M14实际安装版用例替代，未伪称旧用例通过。全量期间测试产物目录已统一M14，更新health旧IPC白名单断言至当前固定接口。没有为文档改动重复全量执行。

安装验收脚本初次在Windows PowerShell5因无UTF8 BOM解析中文失败，未运行安装；加BOM后成功执行旧包安装。其后发现NSIS实际DisplayName带版本、未提供InstallLocation，改为严格比对固定卸载器路径、参数、版本和注册表身份；再次发现无值注册项不带PSChildName，改用枚举项身份。VerifyPending仅核验已有现场，不重新安装或伪造已丢失的旧退出码。首次卫生扫描与仍在关闭的Electron测试并行，DIPS-wal消失导致扫描失败；最终在全部测试/卸载结束后重跑，不忽略扫描错误。

已查看安装版文档导出截图；真实UI无新增排除入口。原生选择器在测试主进程mock，模型/HTTP/DNS在既有源码测试mock；真实组件为Electron、Windows safeStorage、冻结Python、SQLite/FTS、Chromium及本地OCR。真实云模型、Tavily和公网业务调用0；包构建并不代表生产签名或独立Windows验收。合成夹具由开发工具预生成，但发布进程使用隔离cwd、系统PATH和自带资源。

### 试用与限制

最新测试安装器：`artifacts/test-results/M14/release/Orvia-0.2.0-rc.1-win-x64-setup.exe`，旁边SHA256SUMS.txt核对校验和；也可运行`win-unpacked/Orvia.exe`。进入对话选择合成目录或“添加附件”，查看来源、询问文档关键词、预览后确认新文件导出。未签名包Windows可能提示未知发布者；本轮不指导关闭防护。卸载默认保留用户数据。

本轮没有真实云服务端到端测试，安装版完整Main模型规划审批未真实调用；已验证源码mock规划UI和冻结后端实际审批执行。多用户真实账户、ACL/磁盘满/断网组合、杀毒误报认证未全部实测，相关故障由既有单元注入及文档处理说明覆盖；不承诺全Windows兼容。M13关键词检索/OCR误差、输出预算、导出不覆盖、历史权限失效等限制不变。生产证书签名、独立无开发环境Windows验收由用户明确暂缓，M14完整清单保持未完成；不发布Release或自动更新。

本轮固定作者创建正常本地提交，主题`build(M14): package unsigned conversation release candidate`，哈希以最终回执为准。提交前显式暂存模块文件，检查status/diff/cached diff与敏感信息，不包含LICENSE、.zcodeignore、安装包、日志、数据库或测试产物。完成本轮授权部分后停止，等待用户手动push。

最终卫生检查：显式暂存31个模块文件，禁止暂存路径0、暂存真实密钥匹配0；目录包3096个文件中禁止文件0/密钥匹配0，另外4415个本轮产物密钥匹配0。报告hygiene.json及SHA256SUMS.txt均被Git忽略。安装器SHA256为`e5e5667239170aab2246a3e2ba4dc55fa276055b4690c7fe50996e4f0cc858cc`。已查看安装版导出及OCR截图，OCR原文/98%置信度显示正常；导出拒覆盖提示保留。`git diff --cached --check`通过，未暂存改动为空，仅保留`.zcodeignore`。

## M15 模型理解文档、摘要与多来源回答（2026-09-29）

### 预检、实现与边界

开始时目录为`D:\Users\18532\Desktop\LXH\Project\Orvia`，分支`main`；`git ls-remote --symref origin HEAD refs/heads/main`实时返回默认`main`与`946b89f548a38f0c4be651fd0dae100b8a0b031f`，与本地HEAD/origin/main一致，确认用户已手动同步M14。未跟踪`docs/DEVELOPMENT_PLAN_V2.md`完整保留并纳入M15文档提交；`.zcodeignore`保留不暂存；LICENSE在本轮预检无删除状态，未修改。先阅读AGENTS、根README、ARCHITECTURE、旧/V2开发清单、PROGRESS及chat/documents/browser/desktop模块README。M14未完成的生产签名与独立机器验收保持原状态。

- [x] √ 当前会话显式选择1–3个文档/网页不可变证据版本，摘要或问答模式、最多300字问题；原关键词检索入口保留。
- [x] √ 后端复用M12/M13证据版本、文档页/段/幻灯片及网页块定位和M06 FTS；每源最多3段×600字、总计5400字；长文只采样/取命中，预览显示精确正文、覆盖、原提取截断、缺失与OCR来源。
- [x] √ 主进程记录预览输入与revision，生成前复读复核，原生确认后才发送固定Main；renderer不能传正文、路径、模型或供应商。附件选择/网页读取/关键词检索不自动上传。
- [x] √ 模型仅生成无工具JSON；程序按本轮片段复核引用版本/定位/会话，分辨fact/inference/conflict/unknown。生成消息持久化结果、引用、覆盖、用量，复用100次预算、幂等、取消/中断及历史；语义真实性仍需人工核对。
- [x] √ 固定Main `deepseek-flash`/`https://api.deepseek.com`；单次20秒网络超时、30秒等待、1024输出token、0自动重试。Computer与Browser固定配置不变，文件规划不会把来源正文并入指令。无写操作、审批、M20意图路由或流式输出。

### 分级验证（均在项目根执行）

| 级别 | 实际命令 | 结果与 mock/真实边界 | 证据及未覆盖风险 |
|---|---|---|---|
| L0 | `npm run build`（含`npm run check`）；`backend/.venv/Scripts/python.exe -m compileall -q backend/src/orvia_backend/chat backend/src/orvia_backend/application.py` | 最终通过；无模型调用 | 构建只证明类型与打包前源码，不是安装包验收 |
| L1/L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m15_synthesis.py -q --basetemp=artifacts/test-results/M15/backend-temp --junitxml=artifacts/test-results/M15/backend.xml` | 最终3 passed；真实SQLite/FTS、两文档加网页、长文/截断/OCR/冲突/伪造引用、跨会话、取消/幂等/重启；模型mock | `backend.xml`；结构引用校验不能保证模型所述事实正确 |
| L1/L2 | `ORVIA_TEST_RESULTS=artifacts/test-results/M15`，`npx vitest run apps/desktop/tests/m15-contracts.test.ts tests/integration/m15.test.ts` | 最终4 passed；严格IPC/纯文本UI；真实Python stdio/文档提取/SQLite与缺钥拒绝；无云端 | 临时profile在M15结果目录；未使用用户文档 |
| L3 | `ORVIA_TEST_MODULE=M15`、`ORVIA_TEST_RESULTS=artifacts/test-results/M15`，`npx playwright test tests/e2e/m15.spec.ts` | 最终2 passed；真实Electron/Python/SQLite/DOCX解析、预览、结果与回查；绕过预览拒绝、原生框取消后无模型结果；模型和原生对话框在测试启动器mock | `synthesis.png`已目检；测试对话框由启动器模拟接受/取消，不替代用户在产品中手动确认 |
| 真实Main | `backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_m15_synthesis.py --run-live` | 首次1次真实调用返回结构/引用有效，但测试只要求回答主句包含固定日期字面而失败；调整为检查回答加分项结论的日期要素后再次1次调用通过：2合成来源、2结论、2引用、total_tokens=1011；每次单请求，无自动重试 | 仅当前测试进程读取根`.env.local`的Main Key，发送短合成文档/网页片段；不输出原始请求、响应或Key。未用LXH用户文件，未验证真实网页/Tavily或产品窗口真实云调用 |

本轮未做L4全量或重新打包：变更限定生成服务、会话与桌面固定入口，L0–L3已覆盖相应接口；M14发布验收仍按用户暂缓。报告、截图、临时库及测试夹具均在Git忽略的`artifacts/test-results/M15/`。真实调用费用由供应商计费，token上限不能保证精确金额；无真实用户资料上传。

### 试用、限制与提交状态

运行`npm run build`、`npm start`，在同一会话添加合成附件或读取公开网页，勾选1–3个证据版本，选择摘要/回答并填问题，预览实际发送片段，点击生成后在原生框确认。生成卡片可展开覆盖并点击来源回查。取消框不产生模型调用；缺Key提示固定Main不可用。原关键词检索仍可独立使用。用户文件的本地读取授权不等于云端发送授权，发送前应自行审查预览文本。

长文仅取有限片段，不保证全文覆盖；M06关键词为AND查询，可能漏召回；OCR分数与引用结构不证明事实，冲突/截断需人工核对。输出1024 token可能不足以容纳复杂回答，失败不会自动重试。当前源码未重建安装包；M16 Office/PDF成品、M17–M18执行类能力、M19视觉、M20统一意图与流式交互均未开发。

本轮按固定作者“踪显 <18532112451@163.com>”创建正常本地提交，主题`feat(M15): add evidence-grounded document synthesis`，实际哈希以交付回执为准。提交前显式检查status/diff/cached diff、禁止暂存路径和真实Key，`.env.local`、数据库、日志、测试结果、用户文件、`.zcodeignore`与LICENSE均不进入提交。Agent不push；用户手动同步状态在本地提交后仍为待执行。

暂存卫生：显式暂存29个本模块文件，其中包含用户此前未跟踪的完整V2规划；禁止暂存路径0、暂存真实密钥匹配0。本轮结果目录最终扫描339个文件，真实密钥匹配0，报告`artifacts/test-results/M15/hygiene.json`被Git忽略。`git diff --check`、`git diff --cached --check`通过；未暂存的工作区改动只有`.zcodeignore`未跟踪。没有读取LXH目录中的用户文件样本，本轮只使用测试进程生成的合成资料。

## M16 带来源引用的 Word／PPT／PDF 简报（2026-09-29）

### 预检、范围与实现

预检目录为`D:\Users\18532\Desktop\LXH\Project\Orvia`，分支`main`，本地 HEAD、`origin/main`及实时`git ls-remote --symref origin HEAD refs/heads/main`均为`a1ebe35be2fe503bc735e86fb6560e7bf4079d78`，远端默认分支为`main`，确认用户已手动同步 M15。工作区仅有未跟踪`.zcodeignore`，本轮保留且不纳入提交；LICENSE 未修改。阅读 AGENTS、根 README、架构、两份开发清单、进度及涉及模块 README 和源码后实施。用户确认首批为“带来源引用的简报”：Word/PDF 报告、PPT 演示摘要，来自一条已保存 M15 回答，允许编辑标题、摘要及各结论文字。未使用 subagent。

- [x] √ 新增 publication 服务：固定版式和文字预算、最多48个版面、2 MiB 输出；引用身份、定位、fact/inference/conflict/unknown 类型和来源版本由原 M15 消息决定，用户编辑不能改引用。预览含分段/幻灯片、完整引用和 SHA256 revision；成品保留人工复核说明。
- [x] √ 真实生成可编辑 DOCX/PPTX 和带嵌入中文字体的 A4 PDF，并用相应解析库读回；PDF 超出版面预算时拒绝。锁定 python-docx、python-pptx、ReportLab，随冻结包收集 Noto Sans SC 与 OFL 许可。
- [x] √ 复用当前会话 SQLite 消息、M13 Computer gateway 的安全路径校验与独占新建、fsync/字节读回。主进程复核预览版本并弹原生保存框；renderer 只传有界文字和格式，不提供路径、模板、脚本或模型设置。相同请求幂等，换目标拒绝，取消不写入。
- [x] √ 更新 desktop 卡片、preload/IPC、backend 协议、打包清单、相关 README、架构和 V2 清单。M16 不发起新模型调用；本轮没有 M17–M20 功能或视觉改版。M14 未签名安装器未重建，生产签名与独立 Windows 验收仍暂缓。

### 分级验证（命令均在项目根运行）

全部业务素材由测试生成并置于 Git 忽略的`artifacts/test-results/M16/`；只访问合成文件和临时数据库。常规 L0–L4 回归使用确定性 mock 模型；用户追问后另补做一次真实 Main→M16 集成测试。真实云端请求共1次，仅发送两条短合成来源；用户 LXH 文件读取与用户正文上传均为0。M16 产品生成步骤本身不调用模型。

| 级别 | 实际命令或设置 | 结果、证据与边界 |
|---|---|---|
| L0 | `.venv/Scripts/uv.exe lock --project backend --check`；`npm run build`（含 TypeScript 检查）；`git diff --check` | 最终通过；依赖锁、桌面类型和构建与源码一致，无模型调用 |
| L1/L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m16_publication.py -q --basetemp=artifacts/test-results/M16/backend-temp --junitxml=artifacts/test-results/M16/backend.xml` | 2 passed；真实 SQLite/FTS、M15 消息持久化、三种文件生成与读回、跨会话/过期版本/幂等/拒覆盖/错误后缀/长文控制字符；M15 回答为 mock。两条库弃用提示不影响结果 |
| L1 | 设置`ORVIA_TEST_RESULTS=artifacts/test-results/M16`，`npx vitest run apps/desktop/tests/m16-contracts.test.ts apps/desktop/tests/m15-contracts.test.ts --reporter=json --outputFile=artifacts/test-results/M16/vitest.json` | 5 passed；严格桌面契约、卡片及 M15 相邻界面回归，无云端调用 |
| L3 | 设置`ORVIA_TEST_MODULE=M16`、`ORVIA_TEST_RESULTS=artifacts/test-results/M16`，`npx playwright test tests/e2e/m16.spec.ts`；修正预览标题断言对应界面后仅重跑失败的成功场景 | 最终成功与取消两条流程均通过；真实 Electron、Python、文档解析、SQLite、三格式落盘、结果卡片、重启回查和绕过主进程预览拒绝。模型及原生对话框由启动器 mock；最初成功场景因预览未显示标题失败，补显示后定向通过，取消场景首轮已通过 |
| L4 定向冻结 | `backend/.venv/Scripts/python.exe -m PyInstaller --noconfirm --distpath artifacts/test-results/M16/frozen-dist --workpath artifacts/test-results/M16/frozen-work packaging/orvia-backend.spec`；设置`ORVIA_FROZEN_BACKEND=<M16冻结exe绝对路径>`后，`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m16_frozen.py -q --basetemp=artifacts/test-results/M16/frozen-temp --junitxml=artifacts/test-results/M16/frozen.xml` | 最终1 passed；真实冻结 Windows EXE 隔离 PATH 为 System32，经 stdio/SQLite 写出三格式；字体与许可文件实际随包。`freeze-final.log`和`frozen.xml`保留 |
| L4 定向视觉 | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/integration/m16-libreoffice.ps1 -InputDirectory <M16合成E2E输出目录> -OutputDirectory artifacts/test-results/M16/office-render-final/word`；同参数模式运行`tests/integration/m16-office.ps1`，输出至`office-render-final/slides` | 本机 LibreOffice 把合成 DOCX 渲染为2页 PDF；本机 PowerPoint 打开 PPTX 并导出3页 PDF；原生 PDF 为2页。`visual-final/`七张逐页图已目检，中文可读、无可见裁切；Word/PPT 编辑性另由解析库和真实应用打开验证 |
| 真实集成补测 | `backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_m16_publication.py`（默认跳过）；显式`backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_m16_publication.py --run-live` | 1次固定 Main `deepseek-flash`/`https://api.deepseek.com`真实调用通过：2条短合成来源、3条结论、2个引用，供应商报告 total_tokens=1388；同一条已保存结果本地生成并读回 DOCX/PPTX/PDF。HTTP20秒、总等待30秒、输出最多1024 token、零自动重试；总 token 包括输入，故可大于输出预算。Key 仅测试进程内存读取，报告仅计数和状态，无原始请求/响应。`live-integration.json` |

首次 LibreOffice 命令因 Windows 启动器先返回、文件稍后出现而误判失败；脚本改为最长10秒有界等待，随后通过。Microsoft Word COM 实际打开合成 DOCX，但其 PDF 导出和另存均长时间未返回，已停止仅由本轮启动的进程，并采用 LibreOffice 逐页验收；此现象是本机 Office 自动化限制，不能推断用户机器的 Word 行为。上述渲染和冻结属于 M16 定向 L4，不等于重新发布或独立 Windows 验收。没有做全量回归，复用 M14/M15 已通过的无关边界结论。

### 试用、限制与提交状态

先运行`.venv/Scripts/uv.exe sync --project backend --locked`、`npm run build`、`npm start`。在会话中生成 M15 摘要或多来源回答，点击结果上的“制作 Word／PPT／PDF 简报”，选择格式，编辑标题、摘要和结论，核对预览版面、来源及提示，点击保存并在原生对话框选择一个新文件名。再次保存需重新确认；取消不落盘。当前 M14 安装包没有 M15/M16 新源码，试用 M16 请运行本地开发版。

首批仅固定文字简报，不含自定义模板、图片、图表、公式、宏、标书或完整行业调研。编辑文字可能改变语义，引用编号只映射原证据，不保证编辑后的叙述得到来源支持；OCR、截断、冲突仍需人工回查。Word 物理分页和字体替换受实际编辑器影响，复杂长文可能因有界版面拒绝；PDF 为排版成品而非文字编辑格式。补测的真实调用仅验证合成 M15 回答进入 M16，本身不授予用户资料自动上传权限。本机 Word COM 导出未完成，LibreOffice 与 PowerPoint 的合成文件目检结果不代替独立机器或生产发行验收。

固定作者“踪显 <18532112451@163.com>”创建正常本地提交，主题`feat(M16): generate cited Word PowerPoint and PDF briefs`，具体哈希见交付回执。提交前显式暂存、检查 status/diff/cached diff 与敏感信息；`.env.local`、`.zcodeignore`、LICENSE、用户文件、数据库、日志及本轮产物不纳入 Git。Agent 不 push；M16 提交后待用户手动 push。完成后立即停止，不开始 M17。

暂存卫生：显式暂存42个 M16 文件，禁止暂存路径0、暂存真实密钥匹配0；扫描3108个本轮产物，真实密钥匹配0。报告`artifacts/test-results/M16/hygiene.json`被 Git 忽略。`git diff --cached --check`通过；本轮文件之外保留未跟踪`.zcodeignore`。

用户询问为何未做真实模型测试后，补充上表真实 Main→M16 集成验证。原提交`84527f5c15cbae6f4766567d269600e717393149`不改写；补测脚本与文档另作正常本地提交。补充提交暂存4文件，禁止路径0、真实密钥匹配0；扫描3110个本轮产物，真实密钥匹配0，报告为忽略的`artifacts/test-results/M16/hygiene-live-addendum.json`。未再次构建安装包、未运行无关全量测试，不 push。

## M17 代码生成、网页原型、旧临时文件隔离（2026-09-29）

### 预检、授权与交付

项目目录 `D:\Users\18532\Desktop\LXH\Project\Orvia`，分支 `main`，预检本地 `fcdcd00`，实时 `git fetch origin` 与 `git ls-remote --symref origin HEAD refs/heads/main` 证实远端默认 `main` 为 `73a6d3f`，本地领先 1 个提交；用户是否曾手动 push 以此实时结果为准。工作区仅有未跟踪 `.zcodeignore`，保留且不纳入提交；LICENSE 不恢复、不修改。已阅读 AGENTS、根 README、架构、两份开发清单、进度、涉及模块 README 及代码。未使用 subagent，未读取 LXH 用户资料。

用户确认五项首批范围：TS/React/Vite＋原生 HTML/CSS/JS、每次最多12文本文件/64 KiB；可逐项审批修改已授权项目；可交互网页及内置受限预览；仅当前用户 Temp 顶层超过30天的 `.tmp/.log`；同卷隔离、30天受限恢复。三项均已实现，无 M18–M20 功能。

- [x] √ 代码：显式选择项目内最多3个 UTF-8 文件（各8 KiB）、最多2个当前会话 M12/M13 来源片段或一条 M15/M16 已保存结果；复用 M06 检索与证据归属。显示实际拟发送内容，需求和选择绑定版本，原生确认后固定 Computer 返回 JSON 草稿。每文件显示完整源码和差异，逐文件原生批准；后端重核授权根、基线身份/哈希并读回，不覆盖预览后变更。生成成功不等于静态检查或运行通过。
- [x] √ 原型：1–4 页结构化文案，固定生成可编辑 HTML/CSS/JS；React 受限预览导航和表单反馈，不执行生成代码。mock 明确标注，未接真实业务、依赖安装、服务启动或部署。
- [x] √ 清理：Windows 当前账户 Temp 顶层限量扫描，显示文件名、大小、时间和风险；原生框绑定选中项及计划版本。执行前再检查身份/年龄/占用，逐项同卷隔离并哈希核验，失败/中断保留状态且不重放；30天内按账本受限恢复，冲突拒绝覆盖。候选大小、已隔离量和实际释放量分别显示，释放量为0；无永久删除、系统目录或注册表接口。

### 分级验证（项目根执行）

常规测试用合成项目、合成 Local/Temp、临时 SQLite 和 mock Computer/原生对话框；文件副本、报告、截图均在 Git 忽略的 `artifacts/test-results/M17/`。真实调用另行显式运行，仅发送人工编写的合成需求及合成 `App.tsx`；不发送 LXH 文件正文。模型固定 `glm-5.3-flashx` / `https://open.bigmodel.cn/api/paas/v4`，每次最多4096输出 token、HTTP20秒/总等待30秒、零自动重试，2次请求（代码1、原型1），密钥只在测试进程读取根 `.env.local`；报告不含密钥及原始请求/响应。

| 级别 | 实际命令 | 结果与证据 |
|---|---|---|
| L0 | `npm run check`；`backend/.venv/Scripts/python.exe -X utf8 -m compileall -q backend/src/orvia_backend`；`npm run build` | 全部通过；TypeScript、Python 语法和 Vite 构建通过；无模型调用 |
| L1/L2 定向及相邻回归 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m17_services.py backend/tests/test_m17_chat.py backend/tests/test_m15_synthesis.py backend/tests/test_m16_publication.py backend/tests/test_m13_documents.py -q --basetemp=artifacts/test-results/M17/backend-regression-temp --junitxml=artifacts/test-results/M17/backend-regression.xml`；新增边界后只跑 `backend/tests/test_m17_services.py::test_cleanup_skips_link_and_busy_candidate`；最终 `backend/tests/test_m17_services.py backend/tests/test_m17_chat.py` | 相邻回归19 passed，新增硬链接/占用拒绝1 passed，最终 M17 7 passed；真实 SQLite、网关、证据引用、冲突、隔离恢复，模型 mock。既有库弃用提示不影响结果 |
| L1 桌面契约 | `npx vitest run apps/desktop/tests/m17-contracts.test.ts apps/desktop/tests/chat-contracts.test.ts --reporter=json --outputFile=artifacts/test-results/M17/vitest-regression.json` | 通过；严格 IPC 契约和卡片，无云端调用 |
| L3 Electron 流程 | 设置 `ORVIA_TEST_MODULE=M17`、`ORVIA_TEST_RESULTS=artifacts/test-results/M17`；`npx playwright test tests/e2e/m17.spec.ts`，补 800×600/必填后只重跑 `-g '代码逐项'` | 最终成功/取消两条通过；真实 Electron→Python、逐文件应用、原型交互、隔离恢复、绕过预览拒绝；Computer 与原生对话框 mock。截图 `m17-prototype-800x600.png`、`m17-workspace.png` |
| L4 定向旧动作边界 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m10_action_safety.py backend/tests/test_computer_actions.py backend/tests/test_application_actions.py -q --basetemp=artifacts/test-results/M17/backend-action-regression-temp --junitxml=artifacts/test-results/M17/backend-action-regression.xml` | 16 passed；既有路径网关、审批动作、应用协议回归；合成文件，无真实清理或模型调用 |
| 真实合成 Computer | `backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_m17_development.py --run-live` | 2次真实请求通过，代码和原型各形成有效草稿，写入0；初次脚本参数把生成字段传给预览，0次云调用即失败；仅修复脚本并复测。摘要 `live-development.json` |

没有因 M17 改动重新冻结或重建安装包；M20 完成后按 V2 待办统一重建并核对。L4 为旧文件动作边界定向回归，不等于全量发布验收。真实调用证明供应商当前能返回受限草稿，不证明模型生成代码正确、安全或可运行。外部进程可在检查与文件系统操作之间竞态，特殊权限/ACL、满盘或真实用户 Temp 大规模样本未作默认破坏性测试；不把隔离等同腾出磁盘空间。

### 试用与同步

按根 README 启动最新开发版，新建会话并选择自建合成项目目录；展开代码/原型面板，填写需求及显式上下文，逐字核对上云预览和原生确认，再审查完整差异/源码并逐文件写入。原型可在内置组件点击导航、试填表单；如需运行生成网页，请在自己审查后另行处理，本模块不执行。系统清理面板应先审查每个候选的大小/风险，只批准明确可隔离的项目，必要时在期限内恢复。真实 Temp 未被本轮测试清理。

固定作者“踪显 <18532112451@163.com>”创建正常本地 M17 提交，具体哈希见 `git log` 和交付回执；Agent 不 push。M14 安装包仍不含 M15–M17，生产签名和独立 Windows 验收继续暂缓；M18–M20 不在本轮。

提交卫生：显式暂存36个 M17 文件，`git status`、`git diff`、`git diff --cached --stat/--check` 已核对；禁入路径0、暂存文件与根开发 Key 精确匹配0、私钥块标记0。`.env.local`、`.zcodeignore`、LICENSE、数据库、日志、用户文件和 `artifacts/test-results/M17/` 均未暂存。提交前再次 `git ls-remote --symref origin HEAD refs/heads/main` 显示远端 `main` 仍为 `73a6d3f`；本地已有未推送的 `fcdcd00`，M17 提交会继续增加本地领先数，push 仍由用户手动完成。
