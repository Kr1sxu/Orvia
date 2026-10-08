# 开发进度与验证证据

## 当前状态（2026-10-03，M20功能及完整包本机验收完成）

M15–M19已实现、验证并提交；M19提交 `6f87fe016f922846cbdabaa83f3796fd0861c8ec` 用户手动push，10月3日实际fetch/ls-remote再次确认远端默认main与基线一致、0/0。M20四项确认A已完整实现，开发L0–L4对应验证、原生框/IME和真实stdio持久化通过；安装版目录/OCR/引用导出/三格式成品、私有Python LPAC/UIA/可见Chromium对照通过。完整0.3.0-rc.1两种身份未签候选已重建并审计，隔离旧0.2→0.3升级保留历史、旧授权失效。真实Main开发首次失败保留，安装独立1次成功11增量/2引用/三格式；总2次预算已耗尽。自有卸载及配置保留验证通过；本轮代码与记录统一本地交付，提交定位见文末；待用户手动push。旧M14/M19包、.zcodeignore和LICENSE历史状态保留；生产签名/独立Windows验收暂缓，Agent不push。见[M20方案](M20_DESIGN.md)、[验收矩阵](M20_TEST_MATRIX.md)及末节实际证据。

## 历史状态（2026-09-30，M19预检与候选设计）

M18三项已实现/验证/提交，用户手动push已完成。本轮`git fetch origin`及`git ls-remote --symref origin HEAD refs/heads/main`实时核对，本地HEAD、origin/main和远端main均为`9195d209d3d036b6d66d5c74068832a991a6a6d6`，ahead/behind=0/0。M19已授权，仅完成预检、独立候选设计与原生窗口实验，五项用户设计决策待确认，整个模块未完成；未暂存/提交，不开始M20。详细候选见[M19_DESIGN](M19_DESIGN.md)，本轮证据见末节。M14生产签名/独立Windows验收和M20后全功能安装版对照待办仍保留。

## 历史状态（2026-09-30，M18 三项交付时）

用户确认的 M18 脚本、桌面点击、浏览器写操作三项源码已全部实现，通过实际 LPAC/UIA/可见Chromium、Electron审批闭环及分级验证，完整记录见本文末节和[确认设计](M18_DESIGN.md)。正常本地提交以包含本节的 M18 提交及交付回执为准，待用户手动 push；真实模型/真实网站/账号调用为0。M19–M20 未开始；M14 生产签名和独立 Windows 验收仍暂缓，旧包不含 M15–M18，M20 后重建安装包并核对开发版待办保留。Agent 不 push。

## 历史状态（2026-09-29，M15）

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

## M18 实施前预检与候选设计（2026-09-30，历史阶段）

用户明确只实施脚本、桌面点击、浏览器写操作三项同模块能力，要求先完成不依赖决策的预检设计，再确认首批执行范围。本阶段不把模块名称当作任意执行授权，不删减三项目标，不勾选 M18 完成。

项目位置正确，分支 main；`git status --short --branch` 原仅未跟踪 `.zcodeignore`，`git branch -vv`、`git remote -v`、`git log -8 --oneline --decorate` 和 `git show -s --format=fuller HEAD` 已核对。`git fetch origin` 成功；`git ls-remote --symref origin HEAD refs/heads/main` 确认远端默认 main、HEAD 为 `19b1f8a7d4db03927d3eb60949c1de53be7b0727`，`git rev-list --left-right --count HEAD...origin/main` 为 `0/0`。因此 M17 与前一项 V2 文档提交已经同步，保留上一轮历史待 push 记录，不将其视为当前状态。Agent 没有 push、改 TLS 或重写历史。LICENSE 当前为已跟踪且无差异，只核对状态，未恢复、修改或暂存。

已阅读规定文档、相关 README 和应用/网关/会话/审批/退出代码，复用 M17 与 M11 的已有测试结论。三项只读评估分别委派子 Agent，均无修改文件所有权，未传递或读取真实 Key。候选设计和拟改文件、公共权限链路、状态、原生隔离前提、L0–L4 方案见 [M18_DESIGN.md](M18_DESIGN.md)。本机家庭中文版且 WindowsSandbox.exe 不存在；脚本建议 LPAC 加 Job 的真实合成验收，不能用路径校验/工作目录冒充 OS 沙箱。桌面建议独立 UIA worker，Browser 建议独立专用写会话/HTTP 出口和逐实际请求确认，现有只读能力不据此扩权。

本阶段仅新增设计和更新 V2/进度文档，L0 `git diff --check` 通过，`git diff --cached --stat` 为空，`git check-ignore artifacts/test-results/M18/preflight.json` 确认产物路径被忽略；LF/CRLF 转换提示不是检查失败。未改代码、配置或依赖，按文档-only 规则未运行 L1–L4，也没有执行脚本、读取用户窗口、网页提交或真实模型调用。预检摘要为忽略的 `artifacts/test-results/M18/preflight.json`。

已经集中请求五项选择：脚本语言/运行时与来源、隔离/文件/网络权限、桌面应用与动作、浏览器站点/动作/登录、逐步审批/取消/核验/恢复与证据保留。当前待用户回复，执行接口未实施，未暂存文件、未创建 M18 commit；待三项确认范围全部实现验证记录后，按固定作者正常本地提交并停止。M19–M20 未开始，M14 生产签名和独立 Windows 验收暂缓、M20 完成后重建安装包并核对开发版的待办均保留。

## M18 三项实现与验收（2026-09-30）

### 授权、实现和复用

预检已实时确认 main/HEAD/origin/main/远端默认 main 同为 `19b1f8a7d4db03927d3eb60949c1de53be7b0727`，ahead/behind=0/0，上一轮两个本地提交已由用户同步。初始工作区只有未跟踪`.zcodeignore`，保留且不提交；LICENSE干净且本轮不恢复、修改或暂存。规定文档及相关代码已读，先设计再集中确认权限。用户最终确认：Python3.12粘贴/原生.py/另行审查固定Computer草稿三来源；私有运行时、LPAC+Job、只读输入复制、隔离写、每文件回传审批、无网络/提权/依赖安装；桌面每任务原生选普通权限应用和唯一UIA动作；Browser每任务原生确认准确公共HTTPS站点及form/message/upload/delete/transaction类别，专用可见窗手工登录、Cookie仅内存。每步及实际外发另行原生批准；取消阻止后续、自有进程回收、未知不重试、无通用撤销，最小哈希/事实审计。

脚本、桌面、Browser适配器及各自测试分别委派三个子Agent，独占文件已明确，无并发同文件修改，无真实Key传递；主Agent负责Application/Chat装配、共同账本/契约、主进程授权和整合E2E/文档/Git。只读交叉审查发现的问题分别回交原所有者修复。

- `automation/`复用Store/ChatRepository、Computer gateway/PathPolicy、固定模型快照和M17显式文件结果；新增SQLite步骤条件更新、300秒计划、会话归属与版本复核、终态不重放、重启interrupted。状态/取消/待请求旁路长任务，桌面派发全局串行。源码/页面/模型不能授予权限。
- Python私有标准库运行时从固定3.12安装复制，私有exe/DLL/pyd固定manifest变换解决LPAC SxS失败，原安装不改；变换后原签名失效，以完整哈希核验。挂起→Job→零cap/LPAC语义/Low integrity/非提升/UIAccess=0/Win32k禁止及Job UI0xff核验→恢复。30秒、512MiB、4进程上限、stdout+stderr16KiB；输入8×2MiB/总16MiB，只读副本；产物512目录项/12文件/各2MiB/总16MiB，有界遍历和退出后读回。回传新文件经独占创建/fsync/句柄与字节hash复核，不改原输入。
- 桌面固定PowerShell5.1 MTA可信工作器，绑定同用户TokenUser、Session、exe身份、PID创建时间、HWND/class，密码/安全界面拒读；UIA Value/Invoke/SelectionItem/Toggle/Focus，目标/相对布局/前景/焦点复核，无坐标退化。common保存框只允许准确Save按钮走`save_new`，私有staging→原生新路径副本/hash，应用当前路径仍staging。普通应用会自行保存/联网，外发类别在点击前另批业务动作，不能由桌面逐HTTP拦截。
- Browser专用非持久Chromium，公开DNS固定IP/TLS出口、全部route拦截，禁止continue/私网/个人profile/Worker/子框架/WebSocket/下载。任何非GET含HEAD/OPTIONS、动态GET、后续导航、声明GET写端点均实际请求独立审批。普通表单/JSON/multipart有界字段、文件字节hash、遮盖与完整性标记；请求版本180秒，拒绝/过期零外发。初始GET写端点先交付尚未加载的sid再审批；HTTP重定向拒绝直接跟随，须准确授权最终页。2xx只回执，新文字须在之前不存在且提交后实际DOM出现才核验，不能当服务器业务真值。
- 固定21项preload/Zod/Pydantic接口，无通用IPC/执行器/解释器/绝对路径/renderer approved；main保留实际预览并原生逐步确认，backend再次复核。64KiB双向JSON最终字节预算拒绝转义放大，返回固定错误而不破坏连接。三项卡片有完整源码/计划、实际状态/账本、产物回传和外发预览；不开展M19视觉或M20自然语言路由。

### 实际验证命令与结果

报告、合成源码/输入/输出、私有运行时、fixture可执行文件、SQLite、日志和截图统一在被Git忽略的`artifacts/test-results/M18/`。云模型/真实网站/账号调用均为0。模型提案只做固定Computer mock，缺凭据明确不可用，未宣称真实供应商可用；LPAC、UIA和Chromium为本机真实能力。原生选择/审批框仅由测试启动器替换，不冒充原生框视觉验收。

| 级别 | 实际命令 | 结果与证据 | mock / 真实组件与未覆盖风险 |
|---|---|---|---|
| L0 | `npm run build` | 最终通过，`build-complete.log`；两套严格tsc及Vite | 无模型；非安装器构建 |
| L0 | `backend/.venv/Scripts/python.exe -X utf8 -m py_compile backend/src/orvia_backend/automation/windows_isolation.py backend/tests/test_m18_isolation.py backend/tests/m18_isolation_probe.py` | 通过；桌面Python/PS AST亦通过，组件validation.json | 固定源码语法，不替代原生验收 |
| L0 最终AST | 项目根以`backend/.venv/Scripts/python.exe -X utf8 -`调用`ast.parse`检查本轮automation、M18测试/E2E及4个改动的共享Python文件；PowerShell `Parser.ParseFile`检查`automation/desktop_worker.ps1`；`git diff --check` | 25个Python文件通过、PS错误0、diff通过；`syntax-final.json`、`syntax-powershell-final.json` | 语法解析无额外执行、无模型；具体范围固定在本轮文件 |
| L1/L2 | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_m18_service.py backend/tests/test_m18_protocol.py backend/tests/test_m18_desktop_service.py -q --basetemp=artifacts/test-results/M18/common-tree-final-temp --junitxml=artifacts/test-results/M18/common-tree-final.xml` | 11 passed；输入规范化新增断言另跑service 6 passed，`input-normalized.xml` | 执行器/UIA/模型/网络替身；Application/SQLite/协议真实；审批归属/版本/重复/取消/重启/私密审计/读取竞态/树预算 |
| L1/L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m18_isolation.py -q --basetemp=artifacts/test-results/M18/isolation-release-validation --junitxml=artifacts/test-results/M18/isolation-release-validation.xml` | 13 passed/0 skip，27.73s；收紧子进程WinError5单项另1 passed，`isolation-process-exact.xml` | 真实LPAC/Job/令牌/句柄/读写/注册表写打开拒绝/环境/超时/取消/输出/内存及父崩溃回收；socket为WSAStartup10107拒绝，未访问远端；4为上限，本机普通子进程被拒 |
| L1/L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m18_desktop.py backend/tests/test_m18_desktop_service.py -q --basetemp=artifacts/test-results/M18/desktop-unit-temp --junitxml=artifacts/test-results/M18/desktop-unit.xml` | 11 passed/1 skip；skip的原生项下列单独启用通过 | UIA mock/Application SQLite真实；身份/漂移/密码/取消/预算/全局隔离/保存核验；不代表所有应用兼容 |
| L2 原生UIA | `$env:ORVIA_M18_REAL_DESKTOP='1'; backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m18_desktop.py::test_real_uia_synthetic_window -q --basetemp=artifacts/test-results/M18/desktop-real-temp --junitxml=artifacts/test-results/M18/desktop-real.xml` | 1 passed，31.06s；`desktop-validation.json` | 真实自有WinForms/Win32 UIA：输入/focus/invoke/toggle/select、合成原生焦点变化、common保存框和新副本、自有helper取消；未选用户应用 |
| L1/L2 Browser | `$env:ORVIA_BROWSER_TEST='1'; backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m18_browser.py backend/tests/test_m18_browser_engine.py -q --basetemp=artifacts/test-results/M18/browser-final-security2-temp --junitxml=artifacts/test-results/M18/browser-final-security2.xml` | 30 passed，26.72s | 真实headless Chromium、DNS/HTTP替身；五类别真实请求审批前0/批准后1、multipart、DOM、GET/autosave、越站/Worker/非HTTPS/硬链接/预算/发送中取消、重定向停止；无真实网站 |
| L1 main/UI | `npx vitest run apps/desktop/tests/backend.test.ts apps/desktop/tests/m18-ipc.test.ts --reporter=json --outputFile=artifacts/test-results/M18/main-cancel-final.json`；`npx vitest run apps/desktop/tests/m18-ui.test.ts --reporter=json --outputFile=artifacts/test-results/M18/m18-ui-save.json` | 15 passed + UI4 passed | native/backend mock；注入拒绝/跨CID/旧版本/重连清理/实际外发另批/终态清理/转义/保存按钮可达，非OS能力证明 |
| L3 | `$env:ORVIA_TEST_MODULE='M18'; npx playwright test tests/e2e/m18.spec.ts` | 最终1 passed/40.7秒，`electron-final-usable.log`；先前修复后1 passed/46.2秒，`electron-complete.log` | 真实Electron/Python/SQLite/LPAC/UIA/可见Chromium；原生框、空凭据、固定Computer及DNS/HTTP替身；完整脚本预览/执行/回传，UIA输入/点击，写审批前0/批准后1，拒绝/取消/旧版不重放，终端界面恢复可用；非安装版/真实账号 |
| L4 定向共享回归 | `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_computer_actions.py backend/tests/test_application_actions.py backend/tests/test_m10_action_safety.py backend/tests/test_chat.py backend/tests/test_server.py backend/tests/test_browser.py backend/tests/test_m12_browser_chat.py backend/tests/test_m17_services.py backend/tests/test_m17_chat.py -q --basetemp=artifacts/test-results/M18/regression-fixed-temp --junitxml=artifacts/test-results/M18/regression-fixed.xml` | 86 passed；原有LangChainPendingDeprecationWarning保留，不阻塞 | 文件网关/审批/聊天/协议/只读Browser/M12/M17 mock与本地真实组件；不重跑无改动的M13/M16解析/Office或独立安装器 |
| L4 桌面/私有stdio回归 | `npx vitest run apps/desktop/tests tests/integration/backend.test.ts --reporter=json --outputFile=artifacts/test-results/M18/desktop-complete.json` | 最终71 passed；早期68 passed另保留 | Electron API mock、真实Python管道/握手/退出；无真实云调用 |
| L1/L2 最终整合 | `$env:ORVIA_BROWSER_TEST='1'; backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m18_browser.py backend/tests/test_m18_browser_engine.py backend/tests/test_m18_browser_runtime.py backend/tests/test_m18_browser_visible.py backend/tests/test_m18_service.py backend/tests/test_m18_protocol.py backend/tests/test_m18_desktop_service.py -q --basetemp=artifacts/test-results/M18/final-backend-temp --junitxml=artifacts/test-results/M18/final-backend.xml` | 45 passed/36.12秒 | 最终可见布局/Chromium sandbox、真实renderer令牌/回收与共同账本复核；新增XML/metadata边界后最小重跑见下两行，未重复无关测试 |
| L1/L2 运行时和生命周期 | `$env:ORVIA_BROWSER_TEST='1'; backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m18_browser_runtime.py backend/tests/test_m18_browser.py backend/tests/test_m18_browser_engine.py -q --basetemp=artifacts/test-results/M18/runtime-lifecycle-final --junitxml=artifacts/test-results/M18/runtime-lifecycle-final.xml` | 34 passed/20.15秒 | 4项合成运行时篡改/链接/XML/一致目录边界，30项真实headless引擎与网络替身；包含初始化失败回收保护 |
| L2 真实可见浏览器 | `$env:ORVIA_BROWSER_TEST='1'; backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m18_browser_visible.py -q --basetemp=artifacts/test-results/M18/visible-complete-temp --junitxml=artifacts/test-results/M18/visible-complete.xml` | 1 passed/11.72秒；`visible-report.json`、`visible-browser.png`在对应临时目录 | 与产品相同四项环境，完整可见Chromium153；3个renderer原生令牌Untrusted/非提升，无--no-sandbox，写审批前0/批准后1+新DOM，关闭后自有进程已回收；DNS/HTTP仍为合成替身 |

### 失败、修复与最小重跑

1. 初次Chromium完整浏览器下载部分超时，SDK重试后成功安装Chrome153/revision1243，`chromium-install.log`保留；未修改TLS、代理系统设置或自动下载产品依赖。
2. 原生Python初始SxS失败，采用只变换私有运行时manifest；后端干净环境缺LocalAppData改由KnownFolder读取，未拓宽环境白名单。TokenInformationClass46本机不支持87，LPAC改实际AccessCheck语义核验。Windows DirEntry缓存nlink=0改真实lstat。上述正常/负例均原生复测通过。
3. Electron首次目录创建竞态由测试等待chatList存在解决；随后真实LPAC ACL阶段5。实际medium进程对自建目录有WRITE_DAC、无WRITE_OWNER，合并DACL+LABEL会被拒。改仅自有资源DACL先授权当前owner再设置mandatory label，不提权/接管系统ACL。AccessCheck新诊断1338修为同时获取Owner/Group，后原生完整13项及Electron整链通过。早期`electron-first`至`electron-sixth`和isolation诊断失败保留，不冒充通过。
4. Browser最初纯click核验结果字段、未外发动作终态和后台会话关闭问题，经重复核验/取消/发送后回执用例修复。最终追加URL/DTO/控件句柄预算、secret key截断前识别、上传独立文件、HEAD/OPTIONS逐项审批。初始GET写端点“goto等审批但尚未返回sid”死锁改异步交付；新增首跑28 passed/2 failed，修正空白页基线及不直接跟随重定向后定向2 passed、全套30 passed；`browser-final-security.xml`/`browser-bootstrap-repair.xml`/`browser-final-security2.xml`分别保留。
5. 交叉审查补修save_new按钮原被UI禁用、输入`./`别名生成幽灵步骤、导出元数据检查后的字节替换、产物树无界展开、终态取消与main旧审批身份、浏览器审计路径/查询泄漏；上述最小目标集合通过。
6. 共享回归首次误写不存在的`backend/tests/test_actions.py`，未执行测试，`regression.xml`/log保留；改实际文件列表后86 passed。LF/CRLF、NO_COLOR与既有LangChain弃用警告不是测试失败。
7. 增强L3的可见Chromium在真实产品干净环境发现`BROWSER_RUNTIME_UNAVAILABLE`，此前headless结果不代表可见窗成功；`electron-final.log`/`electron-visible-diagnostic.log`保留。先定位SxS 14001，私有版本子目录补manifest/ELF后能启动，但启用sandbox后创建页时主进程退出0xC0000005；固定环境/短Temp/只读ACL实验未解决，相关`browser-visible-*`失败/超时记录保留。仅改变私有副本布局为根chrome.exe、其余DLL/manifest/资源同一版本目录后，真实可见sandbox/请求/DOM流程通过；依据对照结果推断混合DLL路径是本机触发因素，未取得完整崩溃堆栈。源码/SDK/系统PE字节不变；最终只给自有公开程序的AppContainer/LPAC组只读执行，不保留诊断用Everyone/RestrictedCode ACL、环境扩充、DEBUG或Chrome日志参数。修复中一次复制函数块错位造成合成runtime失败，立即修正后3项通过；恶意XML及metadata硬链接新增负例后4项通过。最终原生renderer令牌/回收和L3可见闭环如上，绝不以早期no-sandbox/headless实验冒充最终验收。

### 试用、限制和Git收尾

`npm run build`、`npm start`后新建对话展开“M18可控执行”。脚本完整预览→原生逐步批准→实际状态→逐文件回传；桌面原生选普通应用→观察控件/明确动作/预期结果→原生批准→读回；浏览器原生准确站点和类别→专用窗手工登录→控件计划/批准→实际外发字段/文件/hash/完整性单独批准→页面核验。缺完整可见Chromium时显式运行`backend/.venv/Scripts/python.exe -m playwright install chromium`，不会静默回退个人浏览器。可选固定Computer提案仅已预览≤1000字需求，一次/30秒/4096输出token/零重试、原生费用确认，返回草稿仍需另批执行，本轮真实模型请求0。

限额是上限，不承诺任意脚本/应用/网站兼容；Python部分原生标准库/GUI/网络/子进程被OS拒绝，LPAC仍有系统基础只读及私有系统存储，磁盘为25ms采样而非配额、瞬时可能超额。宿主强杀Job回收已验证，但unique AppContainer profile可能残留；正常finally尝试删除，未单独核验profile删除成功。任务副本/产物无按日期自动清理。冻结后端脚本明确不可用，专用runtime资源须在M20重建时验收；本轮spec只携带固定UIA资源，不称冻结包通过。新建文件中断可能留部分文件，人工核对，不自动覆盖或删除。

桌面无盲坐标/键鼠事件回退；终端/IDE/安全/提权/已知个人浏览器不接管；普通应用自行保存/联网仍可能有副作用，控件读回不证明业务真值，保存应用路径为staging。Browser复杂CDN/子框架/Worker/WebSocket/302登录或提交可拒绝，初始资源GET是否有服务器副作用无法普遍证明；脱敏/截断预览不称全量，2xx+新DOM文字不证明交易结算。未知或已外发取消结果不重试，无通用撤销。本机合成验收不代表独立Windows、多用户、所有权限组合/安全软件/真实站点或供应商可用。

本轮仅M18；M19–M20不实施，M14生产签名/独立Windows暂缓和M20安装版对照待办保留。提交前按固定作者正常本地commit；明确暂存M18文件、审查status/diff/cached与敏感信息，`.zcodeignore`、LICENSE、密钥、报告/数据库/用户数据均不纳入。Agent不push、不改TLS/重写历史/发布Release，本地提交与用户手动push状态分别记回执。

最终三项实际实现/分级验收/文档记录全部成立，V2的M18清单已勾选。提交前再次`git fetch origin`、`git ls-remote --symref origin HEAD refs/heads/main`，远端仍为`19b1f8a7d4db03927d3eb60949c1de53be7b0727`，本地提交前ahead/behind=0/0；LICENSE状态为空，`.zcodeignore`仍未跟踪。本机自有M18 Chrome及fixture进程检查为0，无用户进程被关闭。固定作者正常M18提交以包含本节的`feat(M18): add approved isolated scripts desktop and browser writes`为准；提交后本地main领先远端1，待用户手动push。完成后立即停止，不开始M19。

提交卫生：显式暂存58个M18文件，`git status --short`、`git diff`、`git diff --cached --stat/--check`和关键授权/协议/账本的cached diff已核对。复用既有检查函数，实际命令`backend/.venv/Scripts/python.exe -X utf8 -c "import sys; sys.path.insert(0,'backend/tests'); from hygiene_m10 import main; raise SystemExit(main('M18'))"`：禁止路径0、暂存与当前根开发密钥精确匹配0，35052个本轮普通产物文件精确匹配0，不沿测试reparse遍历；只读密钥用于本机内存匹配，无云调用/值输出。独立暂存复检包含`.zcodeignore`、LICENSE、数据库/日志/产物/运行时等禁入检查及完整私钥块检查，全部0，报告`hygiene.json`、`staged-current.json`均被忽略。最后仅进度文档补记录并显式重新暂存/复检，不重跑无关代码测试。

## M19 预检、候选设计与独立实验（2026-09-30，待设计确认）

用户明确授权本轮仅M19，窗口/字体/非文字图标/全部已实现界面共同完成，不提前M20。开始前完成目录、status、分支/log/remote/default-main、fetch、ls-remote和ahead/behind核对：HEAD/origin/main/实时远端main均为`9195d209d3d036b6d66d5c74068832a991a6a6d6`，0/0，确认M18已由用户手动push。初始仅`.zcodeignore`未跟踪；LICENSE无差异、未修改或暂存。历史M18待push/预检设计/验证中记录保留；V2当前状态已按事实修正。Agent未push、未修改TLS或历史。

参考图先在仓库、Codex附件/临时目录及旧工作目录查找未命中，继续查当前用户Temp顶层找到`codex-clipboard-32eee0ac-dbc7-4032-8731-148404855163.png`并实际查看，原图副本位于本轮design/reference.png。没有要求重新上传，也没有根据截图认定准确字体。只借鉴浅色中性背景、窄侧栏、留白与圆角，不引入参考产品品牌/自动任务/技能/团队/推荐/促销。候选设计见[M19_DESIGN](M19_DESIGN.md)，交互预览与截图位于本轮design/；三个自行绘制几何图标、三组强调色、两组字体，以及原生/大圆角取舍已经形成可审查结果。通过异步问题集中请求五项决策，当前尚无用户确认，生产源代码/模型/权限/打包配置均未更改。

只下载了官方Inter和JetBrains候选字库/原OFL到忽略目录，复用仓库Noto字库与许可，没有安装字体或增添生产依赖。Noto原始17,772,300字节，Inter352,240字节，JetBrains270,224字节，候选原始总计约17.54MiB；实际分发方案/安装增量待确认后验证。Pillow读回Noto为可变字库（fvar存在；默认实例名Thin），候选CSS使用其100–900字重轴；不将默认实例名误当只支持细体。

### 本阶段实际命令与范围

| 级别 | 命令/检查 | 结果 | 范围与证据 |
|---|---|---|---|
| L0 预检 | `git status --short`、`git branch -vv`、`git log -8 --oneline`、`git remote -v`、`git symbolic-ref refs/remotes/origin/HEAD`、`git fetch origin`、`git ls-remote --symref origin HEAD refs/heads/main`、`git rev-list --left-right --count HEAD...origin/main` | 成功，0/0 | 仓库实时同步只读；无push |
| L0 候选资源 | 官方原字体许可读取、字节大小、`Get-FileHash`与Pillow字库读回 | 成功，字体确为可解析候选；许可证不替代产品字体打包验收 | 本轮design/fonts/含字库与各自原OFL；本地资源，无模型 |
| L0/L1 设计板 | `node tests/e2e/m19-design-review.cjs` | 最终passed，3组FontFace实际load成功、JS错误0、900px页面横向溢出false，5张候选截图 | 真实Chromium153 Headless Shell；合成静态内容/本地file字体；不是产品组件/Electron流程验收。`design/review-check.json`与welcome/workflow/typography/review-narrow截图 |
| L2 独立候选窗口 | 清除`ELECTRON_RUN_AS_NODE`后，`Start-Process -FilePath (Resolve-Path node_modules/electron/dist/electron.exe) -ArgumentList @('tests/e2e/m19-window-probe.cjs') -WindowStyle Hidden -Wait -PassThru`，stdout/stderr定向重定向至本轮结果目录 | 最终exit0、5状态；普通/最大化/最小化/还原/760×560 | 真实Electron44.4.5、Windows11 build26200/25H2、DPI96/scale1，未加载产品后端/凭据；`window-probe/window-report.json`和4张真实桌面截图，`probe-background-stdout/stderr.log` |
| L0 测试脚本 | `node --check tests/e2e/m19-design-review.cjs`、`node --check tests/e2e/m19-window-probe.cjs`、PowerShell Parser.ParseFile检查m19-desktop-capture.ps1、`git diff --check` | 成功，PS解析错误0，diff无空白错误 | 测试代码语法与文档；未因文档变化重跑代码构建或M18全套 |

独立窗口使用不透明窗口、roundedCorners:true、thickFrame:true、hidden标题栏和原生overlay控制。本机DwmGetWindowAttribute33返回成功/偏好2；普通/还原/最小尺寸截图中四角像素是背景，而向内10px是窗口颜色，实际可见外轮廓圆角，弧度明显小于参考图。DWM偏好值本身不作为圆角证明。最大化真实截图与native bounds单独保存；最小化记录isMinimized=true。窗口探针没有测试产品拖动、用户双击/边缘缩放/贴靠/全屏，不据此勾选M19窗口完成。截图侧按实际DWM边界裁切，用自有置顶合成背景覆盖周边；最大化不加周边padding，避免保存个人任务栏。

失败与修正：设计板首次直接启动SDK完整chrome.exe为spawn UNKNOWN，改用已有固定Headless Shell进行静态候选检查；没有修改SDK、系统环境/TLS或产品M18浏览器策略。未诊断完整Chrome该次启动错误为已解决。字体初测在切换离开代码视图后OrviaMono显示unloaded，改在显式FontFace.load后记录解析状态，3组当时均loaded；未使用的字体状态仍如实保留，未将卸载状态抹为加载。原生截图PS5.1首次因UTF-8无BOM中文解析失败，改测试文件UTF-8 BOM和显式UTF-8输出后exit0；`probe-stderr.log`保留首跑。第一次探针背景被启动隐藏属性遮住，观察截图后补showInactive/置顶测试背景并缩小最大化裁切范围，最终自有背景截图覆盖此前图片，最终日志另存probe-background-*。这些修正仅测试侧。

### 当前未完成与停止条件

五项设计选择（强调色、图标方向、字体、Windows支持范围、圆角兼容策略）仍待用户确认。全部M19实施/产品L0–L3/窗口与图标打包定向L4/实际EXE安装器任务栏快捷方式核验/敏感信息检查及正常本地提交尚未完成，V2所有M19实施验收项保持未勾选。当前不创建部分完成commit，不将候选图标或原生探针称最终产品。不以等待设计选择擅自缩减Windows或圆角目标。

M14生产签名和独立Windows验收继续暂缓，旧0.2.0-rc.1包没有改动；M20后完整安装包与开发版对照待办保持。全阶段真实模型/真实网站/账号调用0；官方字体下载是资源获取，不是业务模型调用。未暂存/提交，`.zcodeignore`和LICENSE继续保留原状。确认后继续同一M19，最终全部实现/验证/记录/固定作者本地commit后停止，push由用户手动执行。

## M19 确认方案实施与当前验收（2026-09-30，未完成）

用户已明确“强调色选B 非文字图标选B 其余选项选A”：雾蓝`#335FC7`、本项目原创折帆图标、内置Noto Sans SC/Inter/JetBrains Mono与各自原OFL、Windows11 x64普通桌面、原生系统小圆角及控制。上一节待确认是确认前历史，本节为当前事实。参考图已实际找到并查看；不据截图识别准确字体。用户随后选择“先继续其他检查，稍后再验收桌面”，因此当前不运行抢占桌面的原生窗口/安装启动/M18可见流程，不把部分通过标为整个M19完成。

### 已实施与复用

- `window-presentation.ts`接入现有主进程：1120×880/最小760×560、不透明窗口、hidden标题栏+42px原生overlay、roundedCorners/thickFrame与原生控制；F11/Escape切换实际全屏，拖动标题区不含业务控件。没有新增通用或窗口控制IPC；renderer隔离、CSP/网络拒绝、固定模型、主进程原生审批、后端复核及M18隔离未改变。
- `Visual.tsx`的原SVG折帆用于标题/侧栏/欢迎页，功能图标与文字可访问名称分开。`style.css`统一字体层级、浅色/雾蓝与成功/警告/错误语义色、布局/圆角/边框/阴影、表格和源码滚动、长文本、焦点/禁用/悬停/加载/减少动态/forced-colors。业务组件及事件继续复用，M18独立workspace类共用视觉规范；权限文案和原文不裁掉。测试仅更新装饰图标后的按钮名称，没有引入M20统一入口/路由/流式。
- 字体保留原字节、原名称、原OFL，100–900的Noto/Inter可变层级与Regular代码；可靠Windows回退、代码无连字、数字仅统计使用tabular-nums，运行时不联网。原始前端资源17.54MiB，与M16后端Noto仍重复，未以子集删字减体积。资源manifest记录来源与SHA256固定身份，不猜测上游发布版本。可选fontTools诊断显示未安装，未添加依赖，采用实际FontFace/PIL解析与hash核对。
- `brand.svg`维护源、9个透明PNG尺寸和多帧ICO、生成器及resources README齐备。Vite `assetsInlineLimit:0`让小SVG符合原`img-src self`；不扩充data源。builder改`signExecutable:false`保留PE编辑，图标与三原许可实际打包。独立`packaging/m19-visual.config.cjs`使用唯一测试产品/appId/快捷方式名，结果仅写M19，旧M14安装包未改；复用旧冻结资源只验UI/图标，不能当M20全功能发行验收。

### 实际命令、结果与证据

所有结果在被忽略的`artifacts/test-results/M19/`，真实模型/账号/真实网站调用均0。下列命令从仓库根运行；可见桌面项尚未通过，不和独立候选探针混淆。

| 级别 | 实际命令 | 结果与记录 | 真实/替身与限度 |
|---|---|---|---|
| L0 | `npm run build` | 通过；最终`build-csp.log`，类型+main编译+Vite，独立SVG/3字库资源 | 本地构建；CSP保持；不代表原生窗口 |
| L0 资源 | `node apps/desktop/scripts/generate-icons.cjs`；`node apps/desktop/scripts/generate-resource-manifest.cjs` | 通过；`icons-generation-final.log`、`manifest-generation.log`与生产manifest | 可信自有SVG、已有headless Chromium；无产品后端/模型 |
| L1 | `npx vitest run apps/desktop/tests/m19-visual.test.ts apps/desktop/tests/m11-ui.test.ts apps/desktop/tests/m18-ui.test.ts apps/desktop/tests/m18-ipc.test.ts apps/desktop/tests/m15-contracts.test.ts apps/desktop/tests/m16-contracts.test.ts apps/desktop/tests/m17-contracts.test.ts --reporter=json --outputFile=artifacts/test-results/M19/unit.json` | 首次22 passed/1 failed：禁用文字对比度3.893；其它19项通过。修复禁用文字后最小`npx vitest run apps/desktop/tests/m19-visual.test.ts --reporter=json --outputFile=artifacts/test-results/M19/unit-css-final.json`，4 passed；最终测试读取真实CSS变量，不镜像固定色 | Electron接口/审批/backend为mock；IMEs/键盘/模型契约/隔离桥及window options，无真实OS证明。初始失败与`unit-m19-fixed.json`保留，不重复累计相同用例 |
| L1 静态组件 | `npx vitest run apps/desktop/tests/m19-gallery.test.tsx --reporter=json --outputFile=artifacts/test-results/M19/gallery-unit.json`；`node tests/e2e/m19-gallery.cjs` | 1 passed；最终`gallery-browser-final.log`、`gallery/report.json`、states-900/500.png | 实际React SSR合成审批/文件/M15/M16/M17/M18组件，源码转义、禁用批准、焦点/悬停、动画减少、900/760/500长文本无横溢；不执行event/IPC/effect，不当L3 |
| L2/L3 页面 | `ORVIA_TEST_MODULE=M19`与`ORVIA_TEST_RESULTS=artifacts/test-results/M19/flows`下`npx playwright test tests/e2e/m19.spec.ts` | 首次产品套件4 passed/1 failed，`product-first.log`/`product-first.json`；100/125/150/200%页面/字库/图形/最小窗/设置Tab循环与Escape/ShiftEnter/减少动态均通过，product/resources-*.json与welcome/minimum-*.png | 真实Electron+Python/SQLite，空凭据与Main替身；倍率用force-device-scale-factor，不是更改系统DPI，实际系统96DPI。本套原生项失败，详见下一节 |
| L3 受影响流程 | 同M19环境，`npx playwright test tests/e2e/m10.spec.ts tests/e2e/m11-ui.spec.ts tests/e2e/m12.spec.ts tests/e2e/m13.spec.ts tests/e2e/m15.spec.ts tests/e2e/m16.spec.ts tests/e2e/m17.spec.ts` | 13 passed/约2分钟；`flows-first.log`与flows/计划/完成/失败/设置窄窗/证据/OCR/导出/综合回答/成品/代码原型截图 | 真实Electron/Python/SQLite/合成解析写入/导出；模型、DNS/HTTP与原生确认由既有启动器mock；没有重跑无关M18后端全套。该轮在独立SVG修复前，功能结论有效，品牌加载以后续4倍率检查为准 |
| 定向L4 构建 | `npx electron-builder --config packaging/m19-visual.config.cjs --win --publish never` | 最终exit0，`package-shortcut.log`；唯一视觉EXE/NSIS新包只位于M19/release | 真实未签名包，旧M14冻结后端/Chromium；不宣称M15–M18安装功能或M20安装版验收 |
| 定向L4 实际资源 | `backend/.venv/Scripts/python.exe -X utf8 backend/tests/m19_resource_audit.py`；`node tests/e2e/m19-assets.cjs` | 最终PE两实际文件各9尺寸与源ICO精确字节匹配；ASAR3字体/独立SVG、包外ICO/三OFL实际hash一致；`pe-icons.json`、`assets-audit-final2.log`/json；icon-review/icons-light-dark.png实际原PNG明暗背景已查看 | 实际包PE/ASAR，不是源码存在/mock证明；静态图标小尺寸仍可辨三折面，透明边缘可见；不替代任务栏/快捷方式 |
| 定向L4 Windows资源提取 | `powershell -NoProfile -NonInteractive -File tests/integration/m19-shell-icons.ps1` | exit0；Windows ExtractAssociatedIcon从实际EXE/安装器取32px图标，PIL逐像素与源图一致；`shell-icons.json`/png、`shell-icons-pixels.json`，两个NotSigned | 真实Windows Shell资源接口，不启动程序，不清用户缓存，非任务栏/安装器可见窗口验收；像素核验已并入PE审计脚本 |
| L0 脚本/Git | `node --check`检查M19 cjs；PS Parser.ParseFile检查capture/native/taskbar/install/shell脚本；`git diff --check`、`git status --short`、`git diff --cached --stat` | 语法/空白通过；index为空，未暂存或提交 | LF/CRLF提示保留；LICENSE无差异、`.zcodeignore`未跟踪，未触碰 |
| L0 敏感预检 | `backend/.venv/Scripts/python.exe -X utf8 backend/tests/m19_hygiene.py --working` | exit0；改动69文件、禁入0、已配置密钥精确匹配0、私钥块0；4148普通产物文件密钥匹配0；`hygiene-working.json`/log | 仅在本机内存读取密钥用于匹配，不输出值；合法生成PNG固定名称白名单，不沿reparse，4MiB块预算。working不是最终暂存验收，提交前必须再检查真实index |

### 未通过、修正与待验收

1. 初次图标Electron离屏生成出现UnknownVizError，相关早期logs保留；最终改只用已有headless Chromium渲染自有SVG，通过且不改产品运行时。
2. 实际资源审查发现SVG被Vite内联data URI，与已有CSP不符；改assetsInlineLimit0并重建，4倍率FontFace/品牌加载以及ASAR独立SVG通过。未放宽CSP或renderer网络。
3. 禁用文字初始对比度3.893，改为`#626d79`后真实CSS对比度至少4.5通过；只重跑M19目标项。静态悬停首跑读取动画起点颜色误判，改等待computed背景变化后通过；不是修改产品动画来掩盖结果。
4. 产品原生测试首跑完成了系统命中区域、移动API、双击最大化/还原、最小化检查，但F11全屏断言失败。桌面原生截图实际受到其它前台窗口遮挡，ordinary/maximized/restored三张无效图片已删除，不保留或作为产品圆角证据；失败log/JSON保留。测试恢复后增加显式focus，capture增加GetForegroundWindow精确HWND核验，未经最小复跑不能称修复。尚需核对输入协议/焦点并完成F11/Escape、贴靠与真实外轮廓。独立候选窗口早期成功仅是探针，不替代此项。
5. ASAR读取首跑因Windows反斜杠路径未标准化失败，修正检查用斜杠、extract用path.normalize后实际三字库/SVG/许可hash通过，`assets-audit.log`/`assets-audit-final.log`失败与final2通过均保留；包内容没有为通过检查而改变。

### 保留全部目标与接续步骤

待用户提供可见桌面时段后，设置`ORVIA_M19_DESKTOP_ALLOWED=1`，只重跑`tests/e2e/m19.spec.ts`的原生产品窗口项（`-g '真实产品外轮廓'`），核对拖动/缩放命中、最小化/最大化/还原/双击、全屏/贴靠/最小尺寸和真实外轮廓/系统DPI，失败继续定位不降目标。当前gate仅防日常误占前台，skip不是通过。

`tests/integration/m19-install.ps1`已准备并语法检查，实际Install尚未执行；仅接受全新本轮安装/快捷方式与唯一测试标识，记录固定EXE/卸载器hash/注册身份。安装后执行实际安装版`tests/e2e/m19-packaged.spec.ts`（空safeStorage与固定角色，不调用云），核对页面离线资源、实际任务栏唯一测试按钮原生裁切、快捷方式目标/图标，再读回安装EXE/卸载器PE图标并按自有记录卸载。不能以当前已构建/PE通过称安装/任务栏验收完成，不清系统图标缓存或删除普通Orvia安装。

受CSS影响的M18只需最小现有L3闭环`tests/e2e/m18.spec.ts`，设置`ORVIA_TEST_RESULTS`到M19结果目录；已调整该测试的结果路径覆盖，不重跑无改动的M18隔离/backend全套。原生框/模型/HTTP仍为合成替身，真实LPAC/UIA/专用Chromium范围沿既有结论记录。当前此项尚未重跑。

剩余验收通过后更新最终中文文档与V2勾选，再status/diff/cached与敏感index复核、显式暂存M19文件、固定作者正常commit、记录待用户手动push并停止。当前尚未暂存/提交，不将部分完成记为M19完成。M14签名/独立Windows与M20后完整安装包对照保留；不push、不改TLS/重写历史/发布Release、不开始M20。

非桌面收尾：共同间距/大容器圆角已提为复用变量，数值与已测界面保持一致。新实际`npm run build`通过（`build-spacing.log`）；`npx vitest run apps/desktop/tests/m19-visual.test.ts apps/desktop/tests/m19-gallery.test.tsx --reporter=json --outputFile=artifacts/test-results/M19/unit-spacing-final.json`为5 passed，`node tests/e2e/m19-gallery.cjs`再次实际读取新CSS通过（`gallery-spacing-final.log`）。同步定向重建exit0（`package-spacing-final.log`），新ASAR/hash/明暗图标检查通过（`assets-spacing-final.log`），Windows关联图标重新提取通过（`shell-icons-final.log`），两实际PE/源图与Shell像素核验通过（`pe-icons-spacing-final.log`）。没有因等效间距变量重复跑13项业务流程。

待跑两个产品测试入口`npx playwright test tests/e2e/m19.spec.ts tests/e2e/m19-packaged.spec.ts --list`识别6项成功（`pending-tests-list.log`），这只是编译发现测试，不是执行通过。原生F11/Escape测试改为前台HWND/PID先核对，再发固定Win32快捷键；DevTools页面键盘不能独自证明系统快捷键，物理键路径仍待桌面时段实际复跑。5个PS脚本Parser均0（`ps-parse.json`），更新固定快捷键后native脚本再次解析0。本阶段没有再次操作前台。

末次`git ls-remote --symref origin HEAD refs/heads/main`仍确认远端main/默认HEAD为9195d20，与本地HEAD及origin/main一致、0/0；LICENSE无差异，只有`.zcodeignore`未跟踪且保持不提交。卫生预检末次为70个工作树改动文件、4158个普通产物文件，禁入/密钥/私钥块均0（`hygiene-working-final.log`；初始JSON另存`hygiene-working-initial.json`）。这些是本阶段记录，不替代后续新增产物与最终暂存复核。当前可独立完成的实现/审查已落盘，仍无M19 commit；待可见桌面继续同一模块。

## M19 桌面验收与最终交付（2026-09-30，已完成）

用户随后明确“可以验收桌面”。前述待确认、未完成、暂缓桌面时段为历史记录，本节取代其当前状态：B雾蓝、B原创折帆、其余A的全部目标已实现并完成本机分级验收。真实窗口、字体、图标、已实现界面的统一视觉均纳入M19，没有删减或提前实施M20。V2的19项M19验收清单已勾选；正常本地提交后待用户手动push。

### 实际交付与验收证据

欢迎、历史侧栏、消息、输入框、设置、文件结果、审批、证据引用、导出和M15–M18卡片共用浅色变量、雾蓝强调色、间距/边框/圆角/阴影与状态。悬停、焦点、禁用、加载、成功、失败、空状态、长中文/混合文字、滚动与减少动态均有样式；原组件业务事件、键盘和权限链复用。没有自动任务、技能广场、团队、推荐/促销、统一自然语言路由、“＋”入口合并或流式协议。

三原OFL及完整字库离线随包；Noto Sans SC/Inter/JetBrains Mono分层并有系统回退，代码禁用连字。SVG为原创三折帆维护源，九个透明PNG和ICO覆盖16/20/24/32/40/48/64/128/256px。源字库/hash/许可与生成流程见resources README和manifest，前端原字库约17.54MiB，与M16后端Noto当前重复携带。

真实产品窗口`product/native-window.json`核对同一HWND/PID，六张原生桌面裁切位于`product/{ordinary,maximized,restored,fullscreen,minimum,snapped}.png`。普通、还原、760×560最小窗各四角像素为自有合成背景，向内为窗口内容；最大化、全屏、贴靠四角为窗口色，实际符合原生小圆角/屏幕边缘方角策略。DWM偏好不作为唯一证据；系统DPI96，窗口1120×880，标题命中2、左右/底边10/11/15、thickFrame/min/max控制存在。移动、标题区双击最大化/还原、最小化、F11/Escape、贴靠与关闭通过。操作由测试侧Win32/Electron API驱动，不称人工鼠标拖拽验收；命中区域与实际移动/缩放/控制行为共同取证，renderer截图仅证明内容。

实际定向包安装、两次自有同标识升级、安装版启动、快捷方式和卸载通过。`installation.json`终态uninstalled，自有EXE/注册项/Start Menu快捷方式移除，用户配置未删除。安装器、目录EXE、安装后EXE和卸载器四份实际PE各9尺寸图标与源ICO字节精确匹配，签名均NotSigned。Windows Shell四份关联图逐像素匹配源32px；实际快捷方式含系统箭头与边缘alpha变换，未叠层上半区主体轮廓59像素/全不透明主体40像素RGB与源图匹配。完整图不能声称与源图相等。原PNG明暗背景、小尺寸和快捷方式实际图已查看。

任务栏最初实际显示Electron原子图，静态PE/窗口ICO存在不能冒充成功。主进程从可信package.json仅识别固定生产`cn.orvia.desktop`或测试`cn.orvia.m19.visualtest`，app/窗口setAppDetails/安装器使用相同AppId，重启图标与命令来自可信程序路径；这只用于Windows分组，不授予任何权限。定向安装的新分组实际按钮`taskbar.png`已查看为蓝色折帆，`packaged-visual.json`记录唯一标题/PID/裁切。旧Orvia分组曾显示Electron图标，`taskbar-prior-appid.png`保留作差异，未清系统缓存或覆盖旧M14安装。生产稳定AppId保留以兼容升级；已有固定快捷方式/旧安装缓存不保证自动刷新。

### 本阶段实际命令与结果

命令均从项目根运行。产品Playwright环境`$env:ORVIA_TEST_MODULE='M19'`；仅本轮获授权可见桌面项另设`$env:ORVIA_M19_DESKTOP_ALLOWED='1'`。所有报告/截图/日志/合成数据仍只在被忽略的`artifacts/test-results/M19/`，真实模型、真实账户、真实外网业务调用0。

| 级别 | 实际命令 | 最终结果/证据 | 真实与替身范围 |
|---|---|---|---|
| L0 | `npm run build` | exit0，`build-appid.log` | TS/Vite实际构建；未改变固定角色或锁定依赖 |
| L1 | `npx vitest run apps/desktop/tests/m19-visual.test.ts --reporter=json --outputFile=artifacts/test-results/M19/unit-appid.json` | 5 passed，含固定AppId白名单、窗口选项/快捷键、实际ICO及真实CSS对比度 | Electron API mock；包元数据自有合成JSON。加前阶段19项相邻目标与1项实际SSR，共25个不同目标用例，不累加重跑 |
| L1/L2 状态 | `node tests/e2e/m19-gallery.cjs` | 前阶段最终`gallery-spacing-final.log`通过，900/760/500px长文本、悬停、焦点、字体、减少动态 | 实际React SSR/headless静态，不执行事件/IPC/effect，功能证据另由L3 |
| L2/L3 原生窗口 | `npx playwright test tests/e2e/m19.spec.ts -g '真实产品外轮廓'` | 1 passed/14.0秒，`native-hwnd-final.log/json`，真实六状态与控制 | 真实产品Electron/Python/SQLite；合成背景/文件，模型与原生业务确认沿既有替身；系统操作测试侧固定API |
| L2 原生像素 | `backend/.venv/Scripts/python.exe -X utf8 backend/tests/m19_window_evidence.py` | exit0，`window-pixels-hwnd.log`、`product/corner-pixels.json`：六状态，普通/还原/最小各四圆角 | 读取上述真实桌面PNG及边界，不读取renderer圆角 |
| L3 受影响业务 | `$env:ORVIA_TEST_RESULTS=(Join-Path (Get-Location) 'artifacts/test-results/M19/m18-flow'); npx playwright test tests/e2e/m18.spec.ts` | 1 passed/54.7秒，`m18-flow.log/json`，脚本/桌面/可见浏览器闭环 | 真实LPAC/Job/UIA/专用可见Chromium/账本，模型、HTTP与原生确认替身；仅最小受影响流程，复用M18安全结论而不重跑其全套 |
| L2/L3 前阶段结论复用 | `npx playwright test tests/e2e/m19.spec.ts`的四倍率项及前节七个业务spec | 四倍率项4 passed、业务13 passed；`product-first`/`flows-first`及对应截图 | 真实Electron/Python/合成解析/写入/导出，模型/外网/原生业务确认mock；100/125/150/200%只是渲染倍率。最后只增加AppId与测试修复，未改变业务/样式，未重复无关流程 |
| 定向L4 构建 | `npx electron-builder --config packaging/m19-visual.config.cjs --win --publish never` | exit0，`package-appid.log`，独立M19/release产物 | 真实未签名EXE/NSIS；仅复用旧M14冻结后端/Chromium做视觉资源验证 |
| 定向L4 安装 | `powershell -NoProfile -NonInteractive -File tests/integration/m19-install.ps1 -Stage Install`；同脚本`-Stage VerifyPending`、`-Stage Upgrade`（两次）、`-Stage Uninstall` | 实际安装成功后记录修正；Upgrade退出0/历史保留；最后Uninstall退出0，`uninstall.log`、`installation.json` | 只操作唯一M19测试安装路径/注册身份/快捷方式，自有hash校验，不动普通Orvia、不删用户配置 |
| 定向L4 安装版 | `npx playwright test tests/e2e/m19-packaged.spec.ts` | 1 passed/7.4秒，`packaged-appid-final.log/json`、`packaged-welcome.png`、`taskbar.png` | 实际安装EXE、空safeStorage、隔离profile/系统PATH，三字体/SVG离线，Node/通用invoke不可见；只核验视觉，不称M15–M18安装业务通过 |
| 定向L4 实际资源 | `node tests/e2e/m19-assets.cjs`；`powershell -NoProfile -NonInteractive -File tests/integration/m19-shell-icons.ps1`；`backend/.venv/Scripts/python.exe -X utf8 backend/tests/m19_resource_audit.py` | exit0，`assets-complete.log`/`assets-audit.json`、`shell-installed.log`/`shell-icons.json`、`pe-installed-complete.log`/`pe-icons.json` | 实际ASAR/包外ICO/OFL、四份PE/五张Windows Shell图；先在安装尚存在时读取，卸载后保留hash/报告/提取图 |

### 失败修正与实际覆盖限制

1. 早期前台锁阻止原生焦点与F11；测试仅对已经核对自有HWND/PID的窗口临时AttachThreadInput，激活后在finally解除，截图再次精确核对前台；未改产品权限。被遮挡图不保留为证据。
2. 原生测试创建合成背景后，`getAllWindows()[0]`实际指背景，早期最小化/尺寸误核验及native-keyboard“通过”无效。改精确选file产品窗口并核对HWND、760×560实际bounds；最小窗在贴靠前测试，避免系统贴靠状态保留尺寸影响。先前最小尺寸/像素失败记录保留，只有`native-hwnd-final`与`window-pixels-hwnd`为最终产品证据。
3. NSIS实际DisplayName带版本，最初记录核对误报未找到；安装器已成功，不重复安装。只增加固定带版本名称识别，VerifyPending核对已有安装器/EXE/注册身份/快捷方式后恢复真实记录，没有伪造原失败退出码。
4. 任务栏旧分组图不正确，setAppDetails单独指定旧分组尚未消除。定向安装/运行窗口固定同一独立AppId后新分组真实折帆通过；早期旧图保留，不把默认分组或所有已有固定项刷新当已验收。
5. 实际快捷方式有系统箭头及alpha边缘，不可能全图与源32px逐字节相同；单独核对未叠层轮廓/主体不透明颜色，再结合实际目标路径、PE九尺寸和查看原图核验，没有放宽PE或ASAR字节一致性。

实际系统Windows11 x64 25H2/build26200、96DPI；其他Win11版本/VM/AVD/Windows10、多用户和杀毒环境未覆盖。系统圆弧约8DIP，与参考图大圆弧取舍已经由用户选择A确认。渲染倍率测试不能替代不同系统DPI实机。操作系统原生审批框、外部应用/网页保持自己的视觉和权限链；renderer隔离、CSP、主进程授权、严格IPC、后端复核、固定模型和M18隔离均未削弱。

### 试用与提交停止点

开发版在根目录执行`npm run build`、`npm start`：检查欢迎/侧栏折帆、浅色字体和业务卡片；普通窗/最大化还原/最小化/双击/缩放，F11全屏、Escape退出。日常试用不等于授权真实模型请求或用户文件写入，业务仍按原权限与逐项原生审批。验收测试不读取用户文档，安装测试只创建本轮Start Menu快捷方式并已随卸载移除。

M19定向安装器仅用于本轮视觉/窗口资源验证，不是M20后完整安装包验收；M14旧0.2.0-rc.1包未改、不含M15–M18。生产签名、独立Windows以及M20完成后重建完整安装包/逐项对照开发版保持待办。

提交前再fetch/ls-remote核对main默认分支与远端仍为`9195d209d3d036b6d66d5c74068832a991a6a6d6`、ahead/behind=0/0。显式暂存M19文件并审查status/diff/cached及实际index敏感信息；LICENSE无差异、`.zcodeignore`保留且不暂存，密钥、数据库、用户数据、日志/截图/安装产物均不提交。本轮固定作者正常本地提交以包含本节的`feat(M19): unify visual design native windows fonts and application icons`为准，实际哈希见提交回执；提交后本地领先远端1，待用户手动push。Agent未push、未改TLS/网络/历史、未发布Release；本轮M19完成后立即停止，不开始M20。

首次实际index卫生检查71文件/5816普通产物文件，禁入/密钥/私钥块均0（`hygiene-staged.log`）。cached diff发现JetBrains原OFL上游行尾空格，保留原文而不修剪；同时发现core.autocrlf会在重新检出时改变SVG/许可hash。新增精确`.gitattributes -text`保护源SVG与三原许可，只对原许可允许上游行尾空格，其他文件仍执行diff --check；测试卫生脚本新增实际index资源字节/manifest校验。重新暂存原字节后做最终L0复核，原生产资源字节和已经验收包均未变化，不重复无关功能测试。

最终L0：`git diff --cached --check`退出0、工作树diff为空；`backend/.venv/Scripts/python.exe -X utf8 backend/tests/m19_hygiene.py`退出0，72个实际暂存文件、5818个普通产物文件，禁入/密钥/私钥块/产物密钥匹配/资源manifest失配全部0（`hygiene-staged-final.log`）。提交前重新暂存本段并再执行同一审查，结果见`hygiene-staged-commit.log`；源码资源原字节受到固定Git属性保护，未提交测试产物。当前完成状态与历史待验收状态分开保留。

## M20 实施与开发版验收（2026-10-02至10-03）

本轮用户明确授权M20和既定完整安装包待办，随后确认四项A。先实际核对目录、status、main、log、默认分支、fetch和ls-remote：本地HEAD、origin/main、远端main同为M19 `6f87fe016f922846cbdabaa83f3796fd0861c8ec`，0/0；用户手动push事实成立，历史“待push”仅代表当时状态。初始只有未跟踪`.zcodeignore`，LICENSE无差异；两者保持不动、不提交。已阅读根AGENTS/README、架构、两开发清单、PROGRESS、桌面/对话/协议/模型/相关业务/打包README及旧技术设计；本轮最新授权优先于旧AGENTS中“M20未获授权”。

反馈图初始搜索未找到；10月3日在当前用户Temp顶层取得并实际查看指定PNG，副本`M20/design/reference.png`。只解决图中的技术模式、两入口、要求重发和折叠结果问题；沿用M19雾蓝#335FC7、原创折帆、离线三字体、Win11原生圆角，不复刻图中旧绿色“序”。目标、涉及文件、复用组件、测试和停止点已用中文说明，独立后端/前端/打包分工无并发文件覆盖、不传Key。

### 实现和权限

唯一输入提示“你想做些什么”，后台结合指令、显式附件/URL、有效资料和权限、当前会话证据理解需求；明显只读列表不新增模型调用，唯一对象直接处理，必要歧义精简澄清。复合请求最多4步，保留依赖和每步真实核验；不支持业务、缺凭据、Tavily不可用明确说明。固定Main理解不能授予权限，文件名/正文/网页/代码/模型输出不会成为新命令。

可访问“＋”统一原生文件/文件夹入口。最多3文件、每个10MiB/合计30MiB、逐个本地解析；移除仅解绑，历史证据/引用及原文件保留，另有目录撤权。先发需求再授权时同一原请求一次接续；取消/切会话/重启/断线/过期token都失效，不串任务，不重放权限或副作用。

目录默认一级；明确递归默认3层/最高8层。5000访问项、10秒扫描墙钟总时限（含SQLite保存及发送等待）、4MiB元数据任一到限停止取下一项，说明截断、深度、拒绝及不可访问。真实批次最多40条且完整事件12KiB，全部已发现快照按最多100条/实际字节游标分页；扩展名/元数据分类不会冒充正文理解。

真实扫描批次和httpx SSE文本增量分别实现，事件绑定会话/业务请求/传输请求/流/seq。stdio每帧64KiB、Python32项单写队列/10秒背压，主进程80项/128KiB缓冲、40项/48KiB拉取、16项乱序窗口/2秒缺口超时及ACK；renderer有界保留20流。没有完成文本定时切字。模型完整JSON和M15引用核验前只有临时正文，无成功成品；流式不支持/失败须单次原生确认向同模型新发非流式请求，说明重复费用。固定三个角色/地址不变，未知结果无自动重试。

扫描批次事务、seq、历史消息分别落盘，不宣称全链原子。模型临时前缀和seq同次UPDATE先保存，16000字符且JSON编码24KiB上限；中断读取幂等恢复一条不可引用/不可成品的model_partial，无事件/模型/扫描重放。已保存成功但终态事件未输出时，根据request_id/核验前缀只协调持久状态，不把已成功文字再次说成partial、不完成剩余复合步骤；合法NUL/汉字/astral按Python长度定位。历史阅读保持逐会话草稿、滚动和焦点；底部跟随与主动查看最新结果分离。

M15发送片段预览/原生上云审批、M16三格式简报、M17代码/原型/Temp隔离、M18 LPAC/UIA/专用Browser均复用原模块契约和后端复核。UIA输入和点击使用各自新步骤token/操作基线；只推进真实completed账本，不依赖稍后写入的会话摘要。Browser填写不冒充发送，实际请求/2xx回执/SHA/指定DOM新文字核验后才完成；业务语义和交易结算仍不能由UI或HTTP证明。

### 实际命令与开发证据

以下均从项目根运行，结果在忽略的`artifacts/test-results/M20/`；后端合成pytest使用`--basetemp`，真实Electron共用`$env:ORVIA_TEST_MODULE='M20'`。日常模型/公网均mock；供应商两次预算另列。不同轮次重跑不累加为唯一用例总数。

| 级别 | 实际命令/最小目标 | 结果和证据 | 实际组件/替身 |
|---|---|---|---|
| L0 | `npm run build`；`node_modules/.bin/tsc.cmd`各M20 spec的strict/noEmit参数；PS5.1 Parser/BOM | 最终bundle `index-D7IKVKfL.js`，构建/类型/PS解析通过；对应`build`/`*strict*`/native-ime记录 | 实际TS/Vite/PS，离线M19资源 |
| L1 | `node_modules/.bin/vitest.cmd run apps/desktop/tests --reporter=json --outputFile=artifacts/test-results/M20/desktop-final.json` | 99 passed、0 failed/skip，`desktop-final.json` | React、IPC、typed事件及缓冲；Electron API mock |
| L1/L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m20_model_stream.py`及受影响chat/configuration目标 | 流目标80 passed；受影响组合127 passed；`stream`/`affected`报告及`backend-agent-report.md` | 实际httpx/严格SSE/JSON；异步mock网络，非供应商 |
| L1/L2 | `... -m pytest backend/tests/test_m20_natural.py backend/tests/test_m13_documents.py -q` | 30 passed，`natural-refined.xml`；后续UIA复合、概念/引号、迁移最小目标通过 | 实际SQLite/目录/解析，模型/网络mock；拒绝fixture注入 |
| L1/L2 | `... -m pytest backend/tests/test_m20_stream_persistence.py backend/tests/test_m20_natural.py backend/tests/test_m15_synthesis.py -q` | 42 passed，`model-success-window.xml`；NUL最小目标6 passed，`model-nul-boundary.xml` | 实际SQLite故障窗口，模型合成，不声称跨事务原子 |
| L1/L2 | `... -m pytest backend/tests/test_m20_natural.py -k 'directory or scan or resource or batch or recursive' -q` | 8 passed，`scan-wall-clock.xml`；真实next(scandir)访问恰40，sink可控clock跨限后不访问第41 | 实际枚举/存储；时间注入非真实sleep |
| L1/L2 | `... -m pytest backend/tests/test_m20_generation_errors.py backend/tests/test_m15_synthesis.py backend/tests/test_m20_natural.py -q` | 34 passed，`generation-finish.xml`；length明确1024token截断，stop+未闭JSON明确结构失败，partial保留/无成功/无自动补发 | 真ModelClient+异步合法mock SSE；无真实云调用 |
| L2 | `... -m pytest backend/tests/test_m20_transport.py backend/tests/test_m20_stream_persistence.py -q --junitxml=artifacts/test-results/M20/stdio-persistence-final.xml` | 18 passed/35.05秒；32目标前阶段通过，`transport-natural-final.xml` | 真stdio/Python/SQLite，实际kill/重启；模型mock。40条扫描后kill，3重启页不变；模型可见4字后kill，2重启partial身份/seq稳定、调用数不增/不恢复权限 |
| L4跨模块 | 受影响chat/M12/M15/M16/M17/M18 protocol目标 | 原组合42 passed/1测试构造器失败；optional EventSink伪服务构造修正后仅失败目标1 passed，`cross-protocol-final.xml` | 复用既有M18/M19结论，不无条件重跑全套 |
| L3 | `node_modules/.bin/playwright.cmd test tests/e2e/m20.spec.ts`的8项分别最小执行 | 8个不同目标均实际通过，最终`publication-system-fact`、`history-verified`、`references-partial`等日志 | 真Electron/Python/SQLite/合成文件/成品；模型/HTTP/原生决定mock。206条3页/递归207、M15引用、Word、URL、歧义/移除、取消/切会话、慢SSE/草稿、断流一次降级+重启、缺凭据/拒绝 |
| L3 | `node_modules/.bin/playwright.cmd test tests/e2e/m20-business.spec.ts`的7类最小目标 | rename1、code/prototype/cleanup/Computer4、browser1、desktop1均通过，`business-*.json` | Computer/HTTP/原生决定mock；实际代码差异/写回SHA、两页原型、Temp隔离恢复、LPAC/UIA/可见Chromium。Browser实际POST回执/DOM和桌面两操作新token核验 |
| L3离线开发对照 | `ORVIA_M20_OFFLINE_MODE=development`运行`m20-installed.spec.ts`三个grep目标 | 最终目录1 passed/25.1秒；附件1/10.7秒；凭据IPC1/4.8秒；`offline-development-results.md` | 真产品后端无ModelClient/工具替换，选择/保存固定合成路径；模型/公网0。6000中发现5000/50页、空0/撤权/重启；真实DOCX/PPTX/PNG OCR0.9758、Markdown992B/JSON1174B、引用2/2、不覆盖/解绑/坏PDF/超限；固定缺3Key/5组非法IPC拒绝 |
| L3/L4开发运行时 | `ORVIA_M20_PARITY_MODE=development`运行`m20-runtime-parity.spec.ts` | 1 passed/52.3秒，`runtime-parity-development.json/png/metadata.json` | 真后端，2自然脚本各新身份/LPAC/产物批准；越界读/写/runtime写/socket拒绝、环境清洁；真UIA set/invoke；完整可见Chromium动态GET在DNS前暂停/拒绝，外发0/LowIL。原生决定mock，非冻结/安装证据 |
| L3真实原生框 | `node_modules/.bin/playwright.cmd test tests/e2e/m20-native.spec.ts` | 1 passed/22.1秒，`native-main-cancel.json/log`、`native-C83qsv/` | 真showOpenDialog/showMessageBox返回值无替换；真实目录/文件选择→原请求接续/本机DOCX；Main原生取消后调用0。只控制本轮唯一PID/HWND合成路径，SelectionItem选中+固定BM_CLICK准确按钮；未开放产品能力 |
| L3真实Windows IME | `ORVIA_M20_IME_PHYSICAL=1`运行`m20-ime.spec.ts`的版本对应组合目标 | 1 passed/6.7秒，`ime-physical-versioned.json/log`、`ime-physical-T4t0eX/`；Electron44.4.5/Chromium152.0.7977.130 | 只自有前台HWND/输入框，OS SendInput固定NIHAO+单独门闩Space共12键；trusted start/update，ordered end实际trusted=false/data你好，草稿你好/请求1→1。无Unicode/Enter/布局切换/候选窗读取；非物理人工键盘，候选Enter只另有合成229覆盖 |

760×560最终Word/引用和URL直接回答截图已实际查看，无横溢；结果卡片作详情/证据/审批/下载，M18手工详情按需展开。真实原生窗口/三字体/折帆沿用M19完成证据，未扩测其他Windows/DPI/VM/AVD。

### 真实Main调用与失败事实

执行前已中文说明固定Main `deepseek-flash`/`https://api.deepseek.com`，合成DOCX，开发/安装各1次、全轮最多2次，网络20秒/生成30秒、零重试、每请求最多1024输出token、合计2048token；失败计次数。只输出增量计数/时间/用量/引用/成品结构，无Key或原始云请求。Computer/Browser真实模型0。测试`m20-live.spec.ts`有独占预算账本，损坏/重复消费关闭调用，不自动重置。安装安全存储使用独立合成profile，不改变用户正常配置。

开发实际命令：`ORVIA_M20_LIVE=1 ORVIA_M20_LIVE_MODE=development node_modules/.bin/playwright.cmd test tests/e2e/m20-live.spec.ts --reporter=line --output=artifacts/test-results/M20/live-development-e2e`。1 failed；2026-10-03 01:02:47 UTC消费1次。SQLite只读证据`live-stream-development-failed.json`：child流`last_seq=66`/failed、111字符已持久化、错误INVALID_GENERATION，成功synthesis及publication各0，父流程保留paused。真实供应商SSE部分增量已收到，但最终严格JSON未通过，不能称成功引用/M16或完整真实生成通过。

该首次测试在成功标签断言之前未保存观察器delta计数/首末时间，失败completion.finish_reason/usage也未持久化，所以不补造数据、不由111字猜截断原因。后续测试仅补元数据finally保存、准确区分length与JSON错误；保持strict引用校验。官方文档说明默认思考启用以及JSON可能受token预算截断；这是兼容性背景，不证明本次具体原因：[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)、[JSON Output](https://api-docs.deepseek.com/guides/json_mode/)。未更改思考参数、固定角色、供应商或地址，未自动重试/降级。安装剩余1次采用独立请求、同预算、明确30字/1结论的合成问题；实际结果另续记，开发失败账本保留。

### 失败修正与本机覆盖限制

10月2日个别工具长挂起跨夜，10月3日恢复并保留历史日志，不称通过。目录复测初次撤权未结束时Enter不发，测试改等Send enabled；扫描sink错误曾被目录ToolError边界吞掉，修为立即停止保留prefix；UIA completed账本先于消息摘要的窗口只按账本核验，不重执行；Word消息role=system导致未滚到实际成品，显式用户操作只揭示该正确新节点，不抢焦点/影响历史。这些失败与最小通过报告均保留。

Windows原生footer控件未暴露UIA Invoke/Value，测试限定准确PID/HWND/dialog/按钮ID名称后固定BM_CLICK一次，目录/文件仍实际SelectionItem选择/读回；早期launcher PID误匹配/ID和pattern失败不计通过。IME首次严格要求end trusted=true失败，真实OS组合已发生；匹配实际Chromium源码证明end走ScopedEventQueue未设置trusted，与start/update不同。只修测试断言并记录实际false，未伪造DOM输入；官方源码链见`ime-source-investigation.md`，旧失败保留。

权限错误/拒绝fixture注入不能冒充每种真实Windows ACL；UIA仅自有合成WinForms，浏览器合成站点/HTTP，无真实登录/账号/交易。真实输入法只当前HKL0804+NIHAO/Space，不覆盖其他输入法/物理候选Enter；语义/引用一致性验证不是模型事实真值。生产签名与独立Windows环境仍暂缓。

### 完整包验收阶段

2026-10-03源码冻结后正式开始公共后端冻结、旧0.2测试基线、M20 FullTest和普通生产身份0.3候选三组串行构建。78个Python运行分发与uv.lock匹配，CPython3.12.6/PyInstaller6.22.3，完整可见Chromium153.0.8010.12/rev1243与headless/辅助、UIA工作器/私有运行时、OCR和M16库、原字体/图标许可及119分发许可原件/Chromium credits已准备。此处是输入核对，不替代实际冻结/安装证据。

普通候选保留生产AppId但不安装；只使用`cn.orvia.m20.fulltest`/`Orvia M20 Full Test`的唯一隔离目录做旧0.2→0.3真实升级、历史保留/权限失效/无重放，再运行安装离线3项、运行时、固定Main和三格式成品核验。全部完成后才自有卸载，配置保留；旧M14/M19和用户正常Orvia不覆盖。完整包实际命令、hash、NotSigned、安装差异和终态须续记；当前不勾选该待办，不把M19定向视觉包当完整验收。

后续兼容收口：只读`git show HEAD:backend/src/orvia_backend/chat/__init__.py`确认旧M15生成原上限为4096，新流式路径误缩1024，已恢复stream/complete（含明确confirmed_nonstream）两支及M15截断文案4096；普通问题/意图1024不变。`... -m pytest backend/tests/test_m20_generation_errors.py backend/tests/test_m15_synthesis.py backend/tests/test_m20_natural.py -q`再次34 passed/4.62秒，`synthesis-original-budget.xml`，mock真SSE、旧nonstream及明确降级均断言4096；没有降低JSON/引用校验。

因此真实预算已在剩余调用前再次中文说明：开发过去1次1024失败保留，安装剩余独立1次4096，全轮最多2次/5120输出token，网络20秒/生成30秒/零重试，费用按实际用量计。安装短合成问题只给1条结论/30字，不重放开发失败、不改固定模型/供应商/Base URL/思考参数；两个消费记录都保留。

公共freeze首次实际成功但归档比78显式运行依赖图额外涉及锁定lxml-html-clean/Pygments/Setuptools及第三方_pytest。AnyIO测试工具的延迟导入不属产品能力，冻结排除_pytest；按实际归档分发补许可原件/版本复核，未下载/更新依赖。此前freeze作为中间证据保留，M15恢复后重新最小最终freeze再builder，不以旧冻结后端冒充最终源。

开发三格式补证：实际先设`$env:ORVIA_TEST_MODULE='M20'`、`$env:ORVIA_M20_PUBLICATION_MODE='development'`，执行`node_modules/.bin/playwright.cmd test tests/e2e/m20-publication-parity.spec.ts --reporter=line --output=artifacts/test-results/M20/publication-development-output`，1 passed/6.9秒。`m20_publication_seed.py`只读SQLite backup此前已核验mock合成回答/实际DOCX证据，原DB与源文件SHA不变、2单元/1引用、只复制app.sqlite，无Vault或目录授权。真实产品后端无模型/业务替换，三个自然请求各自新M16预览/准确合成路径保存替身/实际新文件核验/父完成，3新publication ledger同source_revision、云和公网0。

`publication-parity-development-FBbb2u/publication-parity.json`记录DOCX37378B/2页规划、PPTX31338B/3幻灯片、PDF28078B/2页；三文件实际重开、标题/全部引用/hash核验通过。PDF两页图主Agent均实际查看，正文、来源附录和页脚无缺字越界。Office未实际渲染打开，Word页数是规划/断页数，不冒充Office最终自动分页；seededAnswerOrigin明确verified mock synthetic answer，不称真实供应商回答。

最终freeze第3次exit0，`freeze-backend-final.log`及`freeze-final-input.json`/`freeze-final-inventory.json`：产品源hash稳定，2864归档模块/2756后端文件，78声明运行分发+3实际归档分发=81、142许可原件（另desktop6/bootloader与NSIS2），完整Chromium credits8296614B；_pytest/项目tests排除。实际后端SHA256 `d660514b5f72b546b2063259f424520d6ecd91a056845afc17f1419c3162bfd2`。三builder按基线→FullTest→普通候选串行，当前真实基线NSIS压缩中，未称已安装。


暂停后恢复核对：2026-10-03再次`git fetch origin`、`git rev-list --left-right --count HEAD...origin/main`及`git ls-remote --symref origin HEAD`，HEAD/origin/main/远端默认main仍为6f87fe016f922846cbdabaa83f3796fd0861c8ec，0/0。保留.zcodeignore和LICENSE历史状态，未push。

最后前端竞态收口：创建会话记录视图epoch，延迟create回包仅刷新侧栏，不能覆盖后来明确选择的会话/草稿或自动派发原需求。paused与真正completed/failed/cancelled分开；同请求接续无需新的started，真实顺序事件继续消费。等待pull/ACK后复核最新缓存，队列只操作本次目标对象；paused仅轮询主进程缓存，最多20流，切换不重放任务。不会复活协议错误或真正终态。

`npm run build`通过，最终renderer为index-DOENNuF8.js；只前端变化，复用最终冻结后端。`node_modules/.bin/vitest.cmd run apps/desktop/tests/m20-stream.test.ts --reporter=json --outputFile=artifacts/test-results/M20/stream-race-unit-final.json`8 passed。新增测试初次payload缺必要label/stage失败，补齐严格fixture后通过，失败报告保留。`ORVIA_TEST_MODULE=M20 node node_modules/@playwright/test/cli.js test tests/e2e/m20.spec.ts --grep '延迟创建|未返回的旧paused|模型流期间' --reporter=line --output=artifacts/test-results/M20/race-e2e`3 passed/24.9秒：真实Electron/stdio/SQLite，create或pull回包门闩、mock模型/原生选择，旧paused与新接续重叠后最终ACK>8；草稿/焦点/历史阅读保持、无错会话自然请求。最初通过.cmd转发正则被Windows管道解析，未执行测试；改直接node CLI，错误日志保留。

D7桌面中间包及其审计/签名报告已移入M20/intermediate-D7，保留原包；最终FullTest与普通候选按最新renderer重新构建。旧0.2基线保持不变，完整新后端SHA不变，安装记录以随后的实际结果为准。


完整最终包：`node node_modules/electron-builder/cli.js --config packaging/m20-full.config.cjs --win --publish never`及根`electron-builder.config.cjs`均exit0，`builder-full-test-final.log`/`builder-production-final.log`。普通候选521447957B/SHA256 ff419e90e6623aa2e1915cf1699d8ce14df6d7de8dc8058bc6711382ae6d090e；FullTest521447927B/dad5b9278af02c26df879fcda3e510ba8e65858ba4e2270bf6a85b26823cca68。实际Get-AuthenticodeSignature核对两安装器及两EXE均NotSigned，`signatures-final-packages.json`。`node tests/integration/m20-candidate-parity.cjs`逐文件比较22份ASAR dist与当前build完全一致、runtime-manifest一致；测试AppId/PE安装身份与普通候选不同，普通身份从未安装。最初临时比较未归一Windows路径得到0项，另次statFile路径失败，均不算证据；正式入口增加最低文件数和当前build逐字节断言，最终`candidate-business-parity-verified.json`通过。59份冻结输入源/打包文件hash仍匹配，`freeze-input-final-verification.json`；renderer单独更新不重冻后端。

实际`powershell -NoProfile -File tests/integration/m20-install.ps1 -Stage Preflight`无既有测试安装；随后InstallBaseline exit0，`ORVIA_M20_UPGRADE_STAGE=seed node node_modules/vitest/vitest.mjs run tests/integration/m20-upgrade.test.ts --reporter=json --outputFile=artifacts/test-results/M20/upgrade-seed-test.json`1 passed/另2阶段skip。Upgrade实际exit0；再设verify，`upgrade-verify-test.json`1 passed/另2阶段skip。完整资源4183文件/1298858022B与目录包逐字节hash一致，原注册身份不变、快捷方式准确，0.2→0.3是实际版本升级。5历史消息、DOCX证据/引用、Mission固定配置保留；旧目录grant为空/inspect拒绝、无自动执行。此前资源审计与正在升级的EXE替换重叠失败FileNotFound，日志保留；后续资源审计等升级完成后独立执行。

安装离线命令：`ORVIA_TEST_MODULE=M20 ORVIA_M20_OFFLINE_MODE=installed node node_modules/@playwright/test/cli.js test tests/e2e/m20-installed.spec.ts --reporter=line --output=artifacts/test-results/M20/offline-installed-output`，3 passed/34.8秒，`offline-installed.log`。真实安装EXE/冻结服务、清空开发凭据及PATH仅System32；原生选择/保存为准确合成路径替身，模型/公网0。目录空/5000上限及全部分页/重启/权限、真实DOCX/PPTX/OCR/引用导出/解绑/坏文件/超限、固定缺凭据/strict IPC均通过。

安装运行时命令：`ORVIA_M20_PARITY_MODE=installed`同node Playwright执行`tests/e2e/m20-runtime-parity.spec.ts --reporter=line --output=artifacts/test-results/M20/runtime-installed-output`，1 passed/30.8秒，`runtime-parity-installed.json`。两同会话新脚本operation与准确接续、LPAC/Job真实执行与逐个导出、越界读/写/runtime写/socket均拒绝、环境清洁；真实UIA工作器控自有WinForms；完整可见Chromium153 LowIL/无提权，无no-sandbox，动态GET在DNS前暂停/拒绝，外发0/进程回收。原生决定合成替身，无模型或HTTP替换；浏览器目标未加载，不冒充公网写操作或独立Windows。


安装三格式命令：`ORVIA_TEST_MODULE=M20 ORVIA_M20_PUBLICATION_MODE=installed node node_modules/@playwright/test/cli.js test tests/e2e/m20-publication-parity.spec.ts --reporter=line --output=artifacts/test-results/M20/publication-installed-output`，1 passed/14.3秒。`publication-parity-installed-s8EwdB/publication-parity.json`，使用与开发版同合法mock合成seed、3自然请求/3新成品账本、相同source_revision；无新模型生成、云/公网0。DOCX37378B/两页规划，PPTX31338B/3slides，PDF28078B/2页，独立重开/引用/标题全通过；PDF2页主Agent实际查看无缺字越界，Office未实际渲染。开发/安装尺寸和结构一致，容器时间元数据不要求SHA相同。

安装真实Main命令：`ORVIA_TEST_MODULE=M20 ORVIA_M20_LIVE=1 ORVIA_M20_LIVE_MODE=installed node node_modules/@playwright/test/cli.js test tests/e2e/m20-live.spec.ts --reporter=line --output=artifacts/test-results/M20/live-installed-e2e`，1 passed/13.9秒，`live-installed.log`。2026-10-03 02:00:12.973 UTC独立消费剩余1次、4096上限，固定Main/原BaseURL、合成DOCX、20秒网络/30秒生成/0重试；先确切预览，原生批准为固定测试决定，safeStorage仅隔离profile。`live-stream-installed.json`记录11个真实文本delta/20字符、同stream/request seq2–12，首增量1790992816708ms、末增量1790992816734ms、完成1790992817051ms；增量产生在完成前，不是逐字动画。真实usage输入680/输出713/总1393token，2条引用核验、成功回答持久化；不记录原始云请求或凭据。

该真实结果随后本地生成DOCX37385B/两页规划、PPTX31391B/3slides、PDF27604B/2页，三个文件均独立重开/2引用/标题/SHA核验；`live-installed-svtBKP/`中PDF2页主Agent实际查看，无中文缺字或定位越界。所有成品共用一次成功模型结果，未新增云调用。开发首次INVALID_GENERATION/111字符/seq66失败原样保留；不是同输入同预算A/B成功率比较，未猜首次失败finish_reason/usage，也未补发开发请求。总账2次已耗尽，Computer/Browser真实模型0。

逐项对照见`artifacts/test-results/M20/development-installed-comparison.md`：目录/解析OCR/导出/资料/权限/LPAC/UIA/可见Chromium/三格式行为一致；开发launcher版本返回Electron44.4.5而实际安装产品版本0.3.0-rc.1，差异明确记录。安装实际EXE及卸载器也均Get-AuthenticodeSignature=NotSigned，`signatures-installed.json`。生产签名和独立Windows验收仍暂缓，不称正式发行。

最终安装资源审计`backend/.venv/Scripts/python.exe -X utf8 backend/tests/m20_package_audit.py --installed --check-local-secrets`exit0：实际安装4257文件、142Python原许可、4PE、版本/后端/私有解释器/完整浏览器/工作器/OCR/字体图标全匹配，credentialsChecked=true；包及当次78623产物文件凭据匹配均0，禁入文件0（此时尚未暂存，不代替index检查）。普通候选`--production`资源审计亦exit0、4255文件；其秘密检查由本轮末尾全产物/index审计补齐。


`powershell -NoProfile -File tests/integration/m20-install.ps1 -Stage Uninstall`实际exit0，`install-uninstall.log`/`uninstallation.json`：只核验过hash的自有卸载器，无提权，测试EXE/注册项/快捷方式均移除，合成profile保留，正常Orvia/用户配置未检查或删除。随后`ORVIA_M20_UPGRADE_STAGE=preserved node node_modules/vitest/vitest.mjs run tests/integration/m20-upgrade.test.ts --reporter=json --outputFile=artifacts/test-results/M20/uninstall-preserved-test.json`1 passed/另2阶段skip，真实保留sentinel和app.sqlite、测试EXE不存在。至此功能验收、完整包本机安装/升级/卸载/开发对照两类授权目标均通过；生产签名及独立Windows发布验收继续未完成。最终包保留，不重新安装用户正常身份。


本轮交付提交定位：`feat(M20): unify natural chat streaming and verify full Windows candidates`，具体哈希可用`git log -1 --format="%H %s"`核对（提交哈希不写入自身内容）；push状态为待用户手动执行，Agent没有push、Release或历史改写。显式暂存116个本轮源码/测试/文档/许可文件，.zcodeignore保持未跟踪，LICENSE无差异且未暂存。测试产物、数据库、配置、安装包均在忽略树；最终index及全产物敏感审计另附计数记录。


提交前最终卫生审查：`backend/.venv/Scripts/python.exe -X utf8 backend/tests/m20_hygiene.py`修正Windows超长路径入口后exit0，`hygiene-staged-longpath.log`/`hygiene-staged.json`：actual staged index 116文件，禁止路径0、凭据匹配0、私钥块0、图标/字体manifest差异0；86024份保留产物凭据匹配0。初次普通路径扫描在归档Chromium深路径lstat失败，没有跳过文件或计通过；仅测试入口改为Windows长路径，再完整扫过。`final-index-check.json`另核对7份补充上游许可原字节、最终暂存内容及tree；无Key/数据库/日志/用户文件/构建产物入index。`git diff --check`、`git diff --cached --check`通过；除.zcodeignore外所有本轮变更显式暂存，LICENSE未动。本轮按上述提交标题正常提交后立即停止，待用户手动push。


## V3-001 按需能力工作区（2026-10-04）

本轮用户要求按照`docs/V3_OPTIMIZATION.md`开始修复，后续要求继续未完成工作。按AGENTS每轮一项完成V3-001；V3-002～005保留待设计/待确认，未扩展实施。预检路径正确，main基线`44fe9d625691a5bfbba8a3ce264335bc891c3f19`，`git ls-remote --symref origin HEAD`确认远端默认main且同SHA；已有未跟踪`.zcodeignore`、`docs/INTERVIEW.md`、`docs/V3_OPTIMIZATION.md`。前两份保留且不提交；用户指定的V3文档完整保留原内容并追加实施记录，纳入本项提交。LICENSE无差异、未暂存；未fetch/push或改网络配置。

- [x] √ 主页面按当前工作流及当前会话历史挂载M17/M18，各能力子区独立显示；普通会话连折叠标题也没有，不再自动调用m18History。
- [x] √ 有界只读`workspace_history`跨消息裁剪/重启保留最近草稿、清理计划和自动化类型；不读取用户文件、不恢复权限、不重放执行。M17可主动读取最近保存项；M18仍走原最近20条账本。
- [x] √ 原实现“你好”实际调用Main；现完整匹配简单寒暄本地回答、无模型调用。带任务句不截断，待办冲突/原生审批优先，“好的”“继续”不授予权限。
- [x] √ 局部working解除后重新检查未消费工作流token，修复上一操作回传收尾与下一任务重叠时可能漏掉预览。
- [x] √ 中文注释、README、架构/开发清单、目标分级测试与工作树/暂存敏感审查。
- [ ] 安装包重建、真实供应商调用、独立Windows/签名：本轮未执行；旧M20包不含修复。
- [ ] 用户手动push；Agent未push、未发布Release。

### 本轮验证与失败记录

结果均在Git忽略的`artifacts/test-results/V3-001/`。普通寒暄测试零模型；业务测试仅合成资料、mock模型/网络、原生选择/批准固定测试替身，真实Electron/stdio/SQLite及相应LPAC/UIA/Chromium。无真实Key或用户原文件送入测试。

| 等级 | 实际命令 | 结果与证据 |
|---|---|---|
| L0 | `npm run check`；`npm run build` | 通过。最终build在`build-final.log`，最终renderer `index-6exyWi5f.js`。 |
| L1 | `node node_modules/vitest/vitest.mjs run apps/desktop/tests/v3-workspace.test.tsx apps/desktop/tests/m17-contracts.test.ts apps/desktop/tests/m18-ui.test.ts apps/desktop/tests/chat.test.ts apps/desktop/tests/m20-contracts.test.ts --reporter=json --outputFile=artifacts/test-results/V3-001/unit.json` | 23 passed，含五能力/三工作流状态、普通正文不触发、裁剪后历史、契约预算/字段拒绝。 |
| L1 | `$env:ORVIA_TEST_RESULTS='artifacts/test-results/V3-001/gallery'; node node_modules/vitest/vitest.mjs run apps/desktop/tests/v3-workspace.test.tsx apps/desktop/tests/m17-contracts.test.ts apps/desktop/tests/m18-ui.test.ts apps/desktop/tests/m19-gallery.test.tsx --reporter=json --outputFile=artifacts/test-results/V3-001/unit-final.json` | 最终组件15 passed（含已跑相关项），图库SSR检查不是交互E2E。 |
| L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v3_workspace.py backend/tests/test_m17_chat.py backend/tests/test_m20_natural.py -q --basetemp=artifacts/test-results/V3-001/backend-temp --junitxml=artifacts/test-results/V3-001/backend.xml` | 首轮14 passed，24准备错误：并发启动时新结果父目录未建立，不是业务断言失败；XML保留。 |
| L2 | 同上加`--lf`，`--basetemp=artifacts/test-results/V3-001/backend-retry-temp --junitxml=artifacts/test-results/V3-001/backend-retry.xml` | 只重跑失败24项，24 passed/14 deselected；总38个目标均通过。真实SQLite、消息裁剪、六执行状态、重启/跨会话及无授权写入拒绝。 |
| L3 | `node node_modules/@playwright/test/cli.js test tests/e2e/v3-workspace.spec.ts --reporter=line --output=artifacts/test-results/V3-001/e2e-retry` | 2 passed/10.6s。首次测试helper错误地在填文字前等待发送按钮可用，2失败；修正测试顺序及历史nav选择器后通过。`e2e-retry.log`保留结果。 |
| L3 | `$env:ORVIA_TEST_RESULTS='artifacts/test-results/V3-001'; node node_modules/@playwright/test/cli.js test tests/e2e/m20-business.spec.ts --grep 'React\|网页原型\|临时文件\|Python\|网页写任务\|桌面复合' --reporter=line --output=artifacts/test-results/V3-001/business-e2e` | 5 passed/1 failed：第二个文件脚本未出现预览；`business-e2e.log`保留。发现working解除不重新触发工作流准备，补依赖后定向复测。 |
| L3 | 同环境，`node node_modules/@playwright/test/cli.js test tests/e2e/m20-business.spec.ts tests/e2e/v3-workspace.spec.ts --grep 'Python\|V3' --reporter=line --output=artifacts/test-results/V3-001/final-e2e` | 3 passed/31.6s；连续两个真实LPAC operation、产物逐个回传，新会话零IPC、五能力入口隔离、脚本待审批重启历史再次通过。`final-e2e.log`。 |
| L3 | 同环境，`node node_modules/@playwright/test/cli.js test tests/e2e/m20.spec.ts --grep '缺凭据' --reporter=line --output=artifacts/test-results/V3-001/missing-key-e2e` | 1 passed/4.6s；需要模型的问题仍报告缺凭据，不支持任务/内网URL拒绝。旧安装测试中的同类输入同步从纯问候改为概念问题，但安装E2E本轮未运行。 |
| L0卫生 | `backend/.venv/Scripts/python.exe -X utf8 backend/tests/v3_hygiene.py --working`；提交前同命令去掉`--working` | 复用已有index与产物审计，仅报存在性和计数；工作树0秘密/私钥/禁入路径/资源manifest差异，实际暂存审计见下文。 |

截图`electron-oiEfut/greeting.png`、`electron-Aj4YRr/restored-script.png`已实际查看：普通对话无高级工作区，重启后仅脚本及账本入口，无桌面/浏览器无关子区。最终重复验收截图另在本轮electron-*目录。窗口顶部品牌重复属于V3-002，本轮未改。旧M17/M18手工入口脚本早于M20自然入口，当前回归使用M20业务E2E，不将旧脚本称为本轮通过。

风险/限制：简单寒暄使用有限完整匹配集合，不代表所有普通问题离线回答。已有相关历史的会话继续保留相应工作区；只有内存预览且无落盘事实时不承诺取消/重启恢复。M17投影只返回最近一份草稿/清理计划，不新增历史分页；M18历史仍20条。L3原生批准是测试替身，未重跑真实手工系统确认或独立机器；此前权限链结论复用，产品没有增加测试授权入口。

交付方式：`npm run build`后`npm start`试用源码，新会话“你好”只显示聊天，再独立提出明确相关需求。正常本地提交标题`fix(V3-001): show capability workspaces only when relevant`，哈希由提交后回执给出；本地完成与手动push分别记录，提交后停止。

提交前实际index敏感检查通过：27文件，禁入路径0、真实凭据匹配0、私钥块0、资源manifest差异0；3674份本轮产物凭据匹配0（hygiene-staged.json，随后最终文档更新再检查）。V3原始文档两处Markdown行尾空格由cached diff检查指出，规范为空行/正常换行后再次检查；内容保留。仅显式本模块文件暂存，.zcodeignore与INTERVIEW.md保持未跟踪，LICENSE、数据库、日志、安装包与产物均未入index。
`git commit`首次因本机未配置作者身份失败，未产生提交；核对最近五次提交作者/提交者一致后，仅用本次命令`git -c user.name=... -c user.email=... commit`沿用已有历史身份，不写全局或仓库Git配置。

## V3-002 顶部重复品牌去重（2026-10-04）

用户明确“继续实施002”。预检main基线39cefe2，远端默认main仍44fe9d6；保留未跟踪.zcodeignore、docs/INTERVIEW.md，不push。读取AGENTS、V3设计和V3-001验证结论后，仅修改renderer顶部节点与对应CSS。侧栏保留，顶部42px原生拖动区及右侧按钮空间保留；会话标题、状态、连接信息、欢迎内容不变。系统图标/字体/安装身份和窗口主进程配置无变更。不扩展V3-003。

- [x] √ 去除顶部BrandMark和“序航 Orvia”，清理冗余字体/间距/图标CSS；有中文窗口边界注释。
- [x] √ L0：`npm run build`通过（包含两套TypeScript检查），`artifacts/test-results/V3-002/build.log`；`git diff --check`及cached检查通过。
- [x] √ L3：`node node_modules/@playwright/test/cli.js test tests/e2e/v3-titlebar.spec.ts --reporter=line --output=artifacts/test-results/V3-002/e2e`，1 passed/4.2s，e2e.log。真实Electron/Python/SQLite，隔离合成profile；复用M20测试启动器隔离凭据/原生框，本轮无模型/网络/文件选择调用。
- [x] √ 新建、问候、历史重开、1120×880及760×560窗口，标题区空文本无图标、侧栏品牌保留、42px拖动区与下一行精确衔接、无横向溢出、输入可见；最大化/还原/最小化通过真实BrowserWindow API，app.close正常退出。
- [x] √ 实际查看new-chat.png和narrow-history.png：顶部重复标识消失，会话状态可读无重叠；其他截图为history.png与narrow-new.png，结构数据window.json。
- [x] √ README、V3登记、开发清单、AGENTS和进度更新；显式暂存本模块文件并敏感审计。
- [ ] 人工原生按钮点击/拖动、独立Windows及新安装包验收未执行。原生window-presentation及资源未改，复用M19系统窗口既有结论；API验证不冒充人工点击。渲染截图不包含系统原生按钮。
- [ ] 用户手动push；无Agent推送或Release。

试用`npm start`（已构建），检查新对话顶部和历史对话；42px保留空间用于系统窗口操作，不缩窄原生命中区。风险为未重建安装包，旧M20候选不含V3源码修复。本轮无后端/权限/模型变化，不重跑业务全量回归。正常本地提交标题`fix(V3-002): remove duplicate titlebar branding`；沿用已核对历史作者的单次git -c身份，不修改Git配置；提交后停止。
最终实际index卫生审计：复用backend/tests/m19_hygiene.py并将RESULT明确指向V3-002；9暂存文件、69产物，禁入路径/凭据/私钥/资源manifest差异全部0，证据hygiene-staged.json。无用户文件、数据库、日志或构建产物暂存。

## V3-003 历史会话管理（2026-10-04）

用户本轮明确要求“会话消息和证据也永久删除”，替代最初讨论的审计正文保留建议。仅本模块：菜单、置顶、改名、永久删除，不开始V3-004/005。预检main起点539d560（V3-002），远端默认main已知44fe9d6；无重置、无push，预存未跟踪`.zcodeignore`、`docs/INTERVIEW.md`保留且不提交。

- [x] √ 更多按钮支持悬停/焦点、方向键/Home/End、Escape归还焦点、外部点击与会话切换关闭、portal视口约束。置顶先分组、最近活动排序；标题与Mission同步，旧库原位迁移，固定模型快照保持。
- [x] √ 原生永久删除确认默认取消；运行中、后台收尾、待审批（包括代码草稿）、不确定结果、开放Browser会话或未恢复隔离文件阻止删除。全部历史检查，不截为最近20项。程序再次核对，不取消/批准外部副作用。
- [x] √ 清除本地消息、证据、FTS/上下文、任务账本/条目、草稿/资料/扫描/流、全部所属图checkpoint和私有脚本输入输出副本，撤销目录与桌面权限，清空相关内存计划和流缓冲。用户原文件和已导出成品保持；失去会话撤销入口。只保留随机UUID与清理进度，无正文审计。
- [x] √ 跨文件/数据库删除先标记pending；失败不报成功，旧身份不可读；启动幂等继续清理，不恢复或重放任务。私有目录拒绝非UUID、越界和重解析点；隔离用户文件不作为私有副本处理。

测试均输出到`artifacts/test-results/V3-003/`，真实模型0、真实用户资料0、真实供应商网络0。L3真实Electron+Python+SQLite，原生对话框选择由测试启动器模拟，不冒充人工点击原生窗口。

| 等级 | 实际命令/结果 | 证据与边界 |
|---|---|---|
| L0 | `npm run check`初次发现遗漏的固定方法类型与LiveStream字段；修正后通过。`npm run build`通过 | TypeScript及Vite；无安装包重建 |
| L1/L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v3_management.py backend/tests/test_chat.py backend/tests/test_v3_workspace.py -q --junitxml=artifacts/test-results/V3-003/backend-final.xml`，31通过 | 真实临时库、合成文件；重命名/置顶迁移、跨会话隔离、删除/恢复和原有聊天/显示回归 |
| L1/L2 | 同pytest执行`backend/tests/test_v3_management.py::test_delete_all_local_evidence_and_private_copies_only`，1通过，报告`delete-expanded.xml` | 增补初始输入checkpoint、全部历史线程、权限撤销、晚到消息拒绝和完成任务条目清理；首次证据夹具不足导致快照校验失败，改为直接检查保留会话存储后通过 |
| L1/L2 | 同pytest执行`backend/tests/test_v3_management.py::test_management_persistence_validation_and_migration backend/tests/test_v3_management.py::test_private_copy_rejects_reparse_before_removing_files`，2通过，报告`migration-reparse.xml` | 增补取消置顶再次重启，以及重解析属性注入后保留文件；合计32个不同后端用例 |
| L1 | `npx vitest run apps/desktop/tests/v3-management.test.ts apps/desktop/tests/chat.test.ts apps/desktop/tests/m20-transport.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V3-003/unit.json`，19通过 | 契约、IPC来源限制、M20传输回归 |
| L1 | `npx vitest run apps/desktop/tests/m20-transport.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V3-003/transport-final.json` | 新增删除缓存测试初次缺少provisional契约字段：13通过/1失败；补全合成事件后只重跑`-t 'V3-003'`，1通过/13未选中，报告`transport-delete-retry.json`；合计20个不同桌面用例 |
| L3 | `$env:ORVIA_TEST_MODULE='V3-003'; npx playwright test tests/e2e/v3-management.spec.ts`，1通过 | 改名、空标题、置顶排序、重启、窄窗口、键盘/外部关闭、原生取消/确认默认值、当前置顶会话删除与再重启；`e2e.json`和`conversation-menu.png`，截图已实际查看 |

已有LangGraph依赖弃用提示，未改依赖。磁盘取证擦除、外部备份/供应商副本不属删除范围；外部进程恶意文件系统竞态未宣称彻底消除。待审批或不确定任务没有强制删除入口，不应为删除而批准不需要的操作。清理永久失败时启动可能保持不可用，需先解决存储/路径异常；不会声称已删成功。新安装包、真实模型、独立Windows验收未执行。旧M20安装包不含本轮修复。

- [x] √ README、模块README、架构、开发清单、V3记录、中文注释与提交前检查完成。
- [x] √ 正常本地提交，标题`fix(V3-003): manage history and permanently delete conversations`；沿用既有一次性作者身份，不修改持久Git配置。
- [ ] 用户手动push；Agent未推送或发布。

试用：`npm start`，将焦点或鼠标移到左侧历史会话，打开更多菜单；改名与置顶重启后保留。只对可以丢弃的测试会话确认永久删除。提交后停止，不开始下一项。

最终实际index卫生审计：复用backend/tests/m19_hygiene.py，将RESULT指向V3-003；30暂存文件、74产物，禁入路径/凭据/私钥/产物凭据/资源manifest差异均0，证据hygiene-staged.json。git diff --check与git diff --cached --check通过；未暂存用户文件、数据库、日志和构建产物。

## V3-004 复合目标与完成判定（2026-10-04）

用户“继续004”授权。预检main基线652b3f3，远端默认origin/main已知44fe9d6，读取AGENTS、V3原复现、既有M20/V3验证记录。预存`.zcodeignore`、`docs/INTERVIEW.md`保留，不纳入提交；不push、不发布、不重建安装包，不进入V3-005。

根因：路由动词与连接词漏识别扫描/分析/输出/给出等；单个obvious结果覆盖复合意图；协调器仅走完模型返回步骤就终结，无全目标事实；局部澄清替换掉剩余目标；非流式普通回答降级后直接终结；文档可能选取无关旧synthesis。

- [x] √ 明确分句逐一保留原文目标和顺序，未支持项/未知项占位；原文完整保留。目标最多16项、能力执行最多4步，超限明确拆分不执行。应用闲置、全盘垃圾识别/风险分析明确能力缺口，不作为目录扫描结果。
- [x] √ SQLite追加step_states，实际完成、未开始、待授权/审批/信息、不支持、部分结果、前置缺失、已接受限制、失败/取消/中断分别记录；全局完成校验计划长度/位置/全部目标事实。
- [x] √ 不支持或受限项必须选择“接受此项未完成或受限范围，继续”或取消；普通继续拒绝，token一次性且绑定会话。接受不等于实际完成，不授予权限；每项都需明确处理，余下目标不丢弃。
- [x] √ 澄清只替换当前目标；普通回答经批准降级后继续余下步骤。文档绑定当前请求已核验引用回答；元数据不足/缺前置时暂停，不用无关历史回答生成文档。
- [x] √ 目标进度独立于消息裁剪；刷新重开/进程重启显示已保存目标，旧token失效，无扫描/模型/副作用重放。旧版无逐目标事实时不倒推伪造。
- [x] √ UI目标清单独立滚动，原因折叠，结束/取消后整体折叠保留最新回答视口；等待状态显示等待信息或选择。

所有报告、隔离E2E profile、截图在`artifacts/test-results/V3-004/`。后端真实临时SQLite/checkpoint和合成目录，模型/失败仅mock。Electron/Python真实通信与本地Word输出；原生目录/模型发送/保存选择由测试启动器模拟。真实模型0，不扫描真实C盘、用户目录或真实应用；不访问真实供应商，不把模拟原生选择称为人工验收。

| 等级 | 实际命令与结果 | 范围/证据 |
|---|---|---|
| L0 | `npm run check`、`npm run build`通过；构建含两套TypeScript检查 | UI/契约/产物；未打安装包 |
| L1/L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m20_natural.py -q --junitxml=artifacts/test-results/V3-004/natural.xml`，初次25通过/4失败 | 4旧断言期待不支持或受限扫描直接结束；改为暂停并显式选择，按消息kind读取扫描结果 |
| L1/L2 | 同pytest运行`backend/tests/test_v3_compound.py backend/tests/test_m20_natural.py`，33通过，`compound.xml` | 完整复现指令、跨会话/重复token拒绝、全部目标逐项接受、未生成无依据文档、原文件保留、局部澄清不丢尾、重启不重放；含M20原有29项回归 |
| L1/L2 | 同pytest运行`backend/tests/test_v3_management.py backend/tests/test_v3_workspace.py backend/tests/test_m20_stream_persistence.py`，31通过，`regression.xml` | V3会话管理/按需工作区及模型前缀持久化兼容 |
| L1/L2 | 同pytest运行`backend/tests/test_v3_compound.py`，扩展为6通过，`compound-final.xml`；完成门槛加强后6通过，`gate-final.xml` | 新增普通回答降级继续余下步骤、无关旧回答不能生成本请求文档；不同后端用例合计67项（含后补快照预算用例） |
| L1 | `npx vitest run apps/desktop/tests/v3-compound.test.tsx apps/desktop/tests/m20-contracts.test.ts apps/desktop/tests/m20-ui.test.tsx --reporter=default --reporter=json --outputFile=artifacts/test-results/V3-004/unit.json`，9通过 | 状态契约、无权限字段、只读进度、原有M20展示；最后折叠调整仅重跑v3-compound，1通过，progress-ui-final.json |
| L3 | `$env:ORVIA_TEST_MODULE='V3-004'; npx playwright test tests/e2e/v3-compound.spec.ts` | 首次刷新后测试未重开历史会话导致定位失败，修正测试按已有产品行为重开后1通过。完整原指令、目录选择接续、目标保留、无Doc调用、重启不重放、零模型；截图compound-progress.png实际查看 |
| L3 | 设置同上MODULE及`ORVIA_TEST_RESULTS=artifacts/test-results/V3-004`，`npx playwright test tests/e2e/v3-compound.spec.ts tests/e2e/m20.spec.ts --grep 'V3-004|先摘要需求后附件|网址自然请求复合'` | 2通过/1失败：新增展开清单挤走网页摘要视口。修复为完成/取消后折叠，再只重跑`m20.spec.ts --grep '网址自然请求复合'`，1通过；支持的附件→引用回答→Word链路已通过 |
| L3 | 同环境`npx playwright test tests/e2e/m20.spec.ts --grep '缺凭据、不支持任务'`，1通过 | 不支持任务现在显式取消后才能新请求；仍拒绝内网URL，缺凭据无备用模型。不同Electron流程合计4项通过 |

已知限制：无任意自然语言完备性承诺，未知分句保守澄清；超4能力步骤保留完整原文要求拆分，不自动扩大执行预算。重启只恢复展示，不自动恢复执行，需核对后新请求。已安装应用/使用频率、全盘垃圾识别和完整风险分析仍未实现；目录大小不等于可清理大小。旧版已错误完成任务没有逐目标证据，不追溯伪造状态。已有LangGraph弃用警告，未改依赖。未做真实供应商调用、独立Windows或新安装包验收。

- [x] √ 中文注释、根与模块README、架构、开发清单、V3记录和敏感检查。
- [x] √ 正常本地提交，标题`fix(V3-004): preserve compound goals and verify completion`，沿用既有作者的一次性git -c身份，不改持久配置。
- [ ] 用户手动push；Agent未推送/发布。

试用`npm start`，输入“列出目录，然后统计空间”并只选择合成测试目录；或输入V3-004完整原指令，检查首步后剩余目标、不支持项和专用接受/取消选择。未批准用户文件变更或真实外发。提交后停在V3-004。

补充L2：`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v3_compound.py::test_long_progress_keeps_all_identities_with_bounded_transport -q --junitxml=artifacts/test-results/V3-004/progress-budget.xml`，1通过。目标进度展示独立12KiB预算，完整原文与16项目标身份/状态不丢弃，长标题/原因只缩短展示摘录，避免挤爆stdio快照；包含2000个非BMP字符输入边界。

收尾复核：局部澄清改用真实路由解析补充文本，避免再次把旧未知句作为新目标导致循环，同时保留原目标标签与后续目标；有现成资料/明确网页的风险问答仍进入资料链。最后重跑test_v3_compound.py为7通过（compound-final.xml），前端v3-compound为1通过；完整累计67个不同后端/9个前端用例。新增DTO字符串长度按Unicode码点对齐Python；当前选择提示使用自然语言，不展示task_decision内部标识。

最终实际index审计：复用backend/tests/m19_hygiene.py、RESULT=V3-004，24暂存文件、1287产物，禁入路径/凭据/私钥/产物凭据/资源manifest差异全部0（hygiene-staged.json）。git status、git diff、git diff --cached与空白检查已核对；未暂存用户文件、数据库、日志或构建产物。

## V3-005 文档回答信息分层（2026-10-04）

用户“继续005”授权。预检：main/HEAD 5fe4d1a，origin为Kr1sxu/Orvia，远端默认origin/main仍为44fe9d6；保留未跟踪.zcodeignore、docs/INTERVIEW.md。本轮仅005，不push/不打安装包。

- [x] √ PDF/DOCX/PPTX/图片统一状态；短预览不误判全文缺失。默认答案与文件名/定位引用，证据ID/哈希/版本/读取时间/提取方式在来源详情保留；历史消息只改展示，不改审计记录。
- [x] √ 发送预览保留准确内容与范围、DeepSeek固定接收方和费用；按钮“确认发送并生成回答”，原生二次确认与取消不发送依旧有效。
- [x] √ 提示模型组织主要内容、发现、方法或结论、局限，只说明与当前问题有关的缺失影响；不编造无依据栏目。部分采样/读取不全仍明确限定回答范围。
- [x] √ OCR导入依赖缺失返回固定原因；其它失败给出可操作建议。校验、提取预算、固定模型、权限链不变。

报告、截图和隔离profile统一在 `artifacts/test-results/V3-005/`。模型全为mock、真实供应商调用0；L1/L2使用真实SQLite和本地解析/OCR。L3真实Electron-Python通信、正常PDF实际解析；缺页/OCR不可用由专用测试后端注入，选择文件/原生确认由测试启动器模拟。没有访问真实用户资料，不代表人工原生确认或真实模型质量验收。

| 等级 | 实际命令与结果 | 覆盖 |
|---|---|---|
| L0 | `npm run build`通过（含两套TypeScript检查），`git diff --check`通过 | 开发构建，未重建安装包 |
| L1/L2 | `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v3_document_presentation.py backend/tests/test_m13_parser.py backend/tests/test_m13_documents.py backend/tests/test_m15_synthesis.py -q --junitxml=artifacts/test-results/V3-005/backend.xml`，30通过 | OCR缺依赖原因、实际解析/预算、证据保存、引用、过期确认、越权拒绝 |
| L1 | `npx vitest run apps/desktop/tests/v3-document-presentation.test.tsx apps/desktop/tests/m13-contracts.test.ts apps/desktop/tests/m15-contracts.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V3-005/unit.json`，初次8通过/6失败 | 新fixture漏content_hash和旧文案断言；修正后只重跑失败两文件，9通过（unit-final.json）；原M13的5项已通过 |
| L1 | 同vitest命令仅m15-contracts，3通过（labels.json）；仅v3-document-presentation，6通过（presentation-final.json） | 最后按钮名称及重复失败提示调整后最小集合；不同前端用例合计14项 |
| L3 | `$env:ORVIA_TEST_MODULE='V3-005'; $env:ORVIA_TEST_RESULTS='artifacts/test-results/V3-005'; npx playwright test tests/e2e/v3-document.spec.ts tests/e2e/m20.spec.ts --grep 'V3-005|先摘要需求后附件'` | Word流程已通过；初次新启动器在Python -I下缺测试模块搜索路径，修正；随后3通过/1失败，partial测试未等附件完成便Enter，改为等待发送按钮可用 |
| L3 | 同环境 `npx playwright test tests/e2e/v3-document.spec.ts --grep 'normal|partial'`，2通过；`--grep 'normal|ocr'`，2通过 | 正常PDF、缺页、OCR故障、取消后零模型、再次确认一次模型、文件名页码引用回查；新增截图实际查看。最后去重失败提示后仅`--grep ocr`重验，1通过 |

不同Electron流程合计4项通过。截图检查覆盖默认回答（normal-HltinG/answer.png）、来源详情、OCR失败（ocr-B0FerW/result.png）；截图发现重复错误提示后去重。既有LangGraph弃用警告未改依赖。已更新M15/M16/M20原有E2E按钮定位，未声称重跑全部历史/真实模型测试。

已知限制：正文仍受8000字/50单元、每来源最多3片段限制；不能称为全文阅读。具体缺失对问题的语义影响由受约束模型判断，前端不推测相关性；未做真实模型生成质量评估。OCR模型文件损坏等worker故障仍使用读取服务错误，不冒充已诊断依赖缺失。旧回答文本不重生成。不扩展解析能力、自动安装、授权或业务。

- [x] √ 根/模块README、架构、开发清单、V3文档和中文注释更新。
- [x] √ 正常本地提交，标题 `fix(V3-005): simplify document answers and source details`，沿用一次性git -c身份。
- [ ] 用户手动push；Agent未推送/发布、未重建安装包、未做独立Windows验收。

试用 `npm start`，添加合成PDF后输入“总结这份文档”；核对发送内容、取消或明确批准，答案中点击文件名/页码可查看原文详情。本轮提交后停在V3-005。

暂存审计：复用 backend/tests/m19_hygiene.py（RESULT=V3-005），实际index 28文件、最终1347产物，禁入路径/凭据匹配/私钥/产物凭据/资源manifest差异均0。git status、git diff、git diff --cached及空白检查已核对；两项用户预存未跟踪文件保留且未暂存。

补充L3：同V3-005环境运行 `npx playwright test tests/e2e/m20.spec.ts --grep 网址自然请求复合`，1通过；确认共享摘要组件的网页来源回查与小窗口无横向溢出。不同Electron流程最终合计5项。

## V4-DOC 设计文档交付（2026-10-07）

用户要求落实已确认的 V4 文档方案，本轮只交付文档，不开发十一项能力。预检：工作目录为 Orvia，main / HEAD `5d6d0e9`，origin 为 Kr1sxu/Orvia，本地已知远端默认分支为 origin/main；检查既有历史、AGENTS、旧技术设计、架构、清单和 V3 进度。保留预存未跟踪 `.zcodeignore`、`docs/INTERVIEW.md`，不纳入提交；不 fetch、不修改远端或网络配置。

- [x] √ 新增 [V4_OPTIMIZATION.md](V4_OPTIMIZATION.md)，覆盖原审查表全部十一项缺口（不含开发时间调整），分别说明现状、目标、输入输出、依赖、权限边界、失败处理、验收标准和未完成清单。
- [x] √ 固定选择：Redis 可选本地服务、SQLite 保留事实；本地 Qwen3-Embedding-0.6B；内置及用户导入 Skills；自动跨会话记忆候选与逐批原生确认 Main 发送；本地／远程 MCP 只读工具；普通权限 Shell 与 Windows 进程逐次审批；调研最多十网页／两轮；安全读取和检索最多额外重试两次。
- [x] √ README 增加设计入口；未将 V4 目标写入 ARCHITECTURE 已实现能力，本文开发清单的 V4-001～011 均保持未完成。
- [ ] V4-001～011 开发、运行验证及安装包；本轮未授权、未执行。
- [ ] 用户手动 push；Agent 不推送或发布。

### 本轮验证（文档-only）

本轮仅 L0，非 mock、真实模型 0、真实服务调用 0；不运行 L1～L4 代码测试，不执行构建、依赖安装、模型下载、数据库迁移。

| 等级 | 实际命令与结果 | 证据与边界 |
|---|---|---|
| L0 | `$v4DocAudit \| & backend/.venv/Scripts/python.exe -X utf8 -`（本轮内联文档检查），28 项通过、0 失败 | `l0-audit.json`；11 模块、原表 11 缺口、每模块必备字段、全部未完成、确认取舍、6 本地链接、README／进度入口与忽略目录。只检查本地链接存在，官方外部链接沿用规划阶段核对，不冒充本轮联网验证 |
| L0 | `git diff --check`、`git diff --cached --check`通过；检查 `git status --short`、`git diff`、`git diff --cached`与暂存名单 | 本轮仅 README、PROGRESS、V4 文档；预存未跟踪文件、代码、数据库、密钥、日志和报告未暂存 |
| L0 | 下列实际敏感审计命令通过，限定 RESULT 为 V4-DOC | `hygiene-staged.json`；实际暂存 3 文件，禁入路径、原始密钥匹配、私钥块、产物密钥匹配和既有资源 manifest 差异均 0。读取根凭据只用于本进程匹配，输出仅存在性和计数，不发送请求 |

```powershell
backend/.venv/Scripts/python.exe -X utf8 -c "import pathlib,sys; sys.path.insert(0,str(pathlib.Path('backend/tests').resolve())); import m19_hygiene as audit; audit.RESULT=pathlib.Path('artifacts/test-results/V4-DOC').resolve(); audit.RESULT.mkdir(parents=True,exist_ok=True); raise SystemExit(audit.main())"
```

本轮结果目录为 `artifacts/test-results/V4-DOC/`（Git 忽略）。阅读入口为根 README 或本文链接，无新增功能试用步骤。限制：文档确定路线和权限取舍，依赖版本、具体契约与资源预算须在对应模块实施设计中锁定；不能将目标能力写成简历已完成事实。

本地交付提交标题为 `docs(V4): plan capability expansion without implementation`，本节随该正常本地提交保存，实际 hash 见 Git 历史；沿用既有作者的单次 `git -c` 身份，不修改持久配置。提交后停止，不开始 V4-001，用户手动 push 单独保持未完成。

## V4-001 可选本地 Redis 辅助服务（2026-10-07）

用户本轮明确授权仅001、必要依赖、subagent和正常本地commit；取代上文V4-DOC对001的“未获实施授权”历史状态，其余模块仍未实施。预检目录Orvia/main/HEAD `4f1b74a`，origin Kr1sxu/Orvia；`git symbolic-ref refs/remotes/origin/HEAD` 为origin/main；`git ls-remote --symref origin HEAD`验证远端main/`5d6d0e9`，不fetch/push或调整网络。预存未跟踪 `.zcodeignore`、`docs/INTERVIEW.md`原样保留且不暂存；现工作区无LICENSE删除。复用V3/M20的事实存储、固定模型、审批和恢复结论，未把旧安装包当新代码验收。

- [x] √ 默认关闭、精确回环地址/端口/库号、固定设置与私有协议；配置/健康、显式启停和恢复、可见降级。按钮只改变Orvia连接，不管理Redis进程。
- [x] √ 独立REDIS_PASSWORD/redis引用，仅Electron主进程读取开发凭据，经Initialize/credentials.replace注入后端内存；发布safeStorage加密无明文回退，撤回立即断旧连接，公开状态无密码。
- [x] √ SQLite请求插入/状态修订/删除触发器维护随机UUID和版本，旧数据按100项批次重建；审批、正文、证据和完成事实仍在原SQLite链。
- [x] √ Redis缓存仅task_id/version/status，30秒TTL；通知仅随机UUID/version，256条/60秒；消费者核对SQL，最多20项最近只读投影。关闭/降级/队列丢失用本地通知更新投影，单独计数；旧缓存/重复/延迟通知不执行或覆盖新事实。
- [x] √ 删除标记即时清理本地关联，status复核剔除已删/旧版本，晚到通知不能复活会话；Redis不可用时无正文随机元数据可能保留到原TTL，不能作为证据使用。
- [x] √ 有意义中文注释/模块README、根README/AGENTS、架构/开发清单/V4状态、相关验证与敏感审计。

主Agent整合/桌面/真实服务/文档/提交；subagent只修改新auxiliary目录和test_v4_auxiliary.py，另一subagent只读审查，不传递真实Key或用户资料。不提前开发002；审查补齐实际投影与本地消费者、配置保存失败原连接保留、SQLite异常不杀观察器、服务端裁剪超长回复。初始化失败完整释放观察器/数据库，允许合法重试。

### 具体契约与资源

`auxiliary.status/configure/probe`固定私有方法；renderer只有对应三IPC，没有通用Redis、URL、SQL或命令。最终配置必须为本地地址127.0.0.1/::1、端口1～65535、db0～15、布尔enabled。status包含连接state、固定reason、独立凭据存在性、Redis/本地计数和最多20个{task_id,version,status}，不回显错误正文或原始会话标识。派生表不保存请求正文/用户路径/审批token。

2秒后台轮询；每轮发布最多100修订、Redis与本地消费合计100；工作总预算1.5秒，另最多0.25秒关闭；单操作连接/读写0.25秒、探测0.5秒、单连接、retry=0。Lua仅返回不超过128字节的通知/256字节缓存，恶意值丢弃。Redis故障熔断，设置轮询3秒仅读已知状态，不自动重新连接；用户配置/检测/凭据更新或重启重新注入才探测，不重放业务。SQLite存储故障明确原因；模型调用、文件执行等重试政策未扩展。

### 安装与真实服务

预检Python3.12.6、uv0.12.5已存在，Redis客户端未装；已有Docker Desktop/WSL，初始引擎不可用，用户启动后引擎29.7.2正常。只执行 `C:/Users/18532/.local/bin/uv.exe add --directory backend --python .venv/Scripts/python.exe 'redis==7.0.0'`，项目venv安装客户端及重新安装同版editable项目，uv.lock只新增redis，不升级其它依赖。客户端MIT、PyPI官方版本/Python3.12兼容性已检查；[来源](https://pypi.org/project/redis/7.0.0/)、wheel339526字节，SHA256 `1e66c8355b3443af78367c4937484cd875fdf9f5f14e1fed14aa95869e64f6d1`。uv跨盘hardlink回退复制属安装提示，已安装成功；没有全局依赖或模型下载。

真实兼容性验收夹具使用官方Redis7.2.4-alpine/BSD-3-Clause，镜像约18,841,207字节，固定digest `sha256:c8bb255c3559b3e458766db810aa7b3c7af1235b204cfdb304e79ff388fe1a5a`；[官方镜像](https://hub.docker.com/_/redis)、[许可](https://redis.io/legal/licenses/)。该旧版仅用于本轮隔离夹具，不代表生产部署建议。实际命令：

```powershell
docker pull redis:7.2.4-alpine
docker run --detach --name orvia-v4-001-test --publish 127.0.0.1:16379:6379 --memory 96m --cpus 0.5 redis@sha256:c8bb255c3559b3e458766db810aa7b3c7af1235b204cfdb304e79ff388fe1a5a redis-server --save '' --appendonly no --maxmemory 32mb --maxmemory-policy allkeys-lru
```

实际inspect核验回环端口、96MiB/0.5CPU及镜像digest，INFO确认为7.2.4；无持久数据卷，缓存上限32MiB。测试用合成请求、认证密码及独立profile；不访问用户资料。验收后停止专用测试容器，Docker Desktop与镜像保留；不操作用户其它容器。Orvia产品不自动部署服务或写这些Docker参数。

### 实际验证

结果统一在 `artifacts/test-results/V4-001/`，Git忽略。真实模型调用0；默认测试无需Redis，live脚本只有显式ORVIA_REDIS_TEST_PORT才运行，断容器仅允许准确专用名。L3真实Electron–Python/SQLite/Redis；已有启动器只模拟模型/网页以及原生目录选择，不把模拟选择称人工验收。无需L4：独立可选辅助模块，原业务相关L1～L3已覆盖，未改执行/模型/打包链。

|级别|实际命令/结果|证据与边界|
|---|---|---|
|L0|`npm run check`、`npm run build`通过（最后构建包含类型检查）；`C:/Users/18532/.local/bin/uv.exe lock --directory backend --check`通过|只开发构建，无安装包；92个锁定包，新增Redis，无其它版本更新|
|L1/L2|`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_application.py backend/tests/test_configuration.py backend/tests/test_v3_management.py -q --basetemp=artifacts/test-results/V4-001/regression-data --junitxml=artifacts/test-results/V4-001/regression.xml`，44通过|真实临时SQLite，模型网络mock；配置、不可变角色、删除/恢复及原有边界|
|L1/L2|同pytest运行 `backend/tests/test_v4_auxiliary.py backend/tests/test_v4_auxiliary_protocol.py backend/tests/test_application.py backend/tests/test_chat.py::test_chat_persistence_idempotency_and_restart_grant`，`--basetemp=artifacts/test-results/V4-001/final-data --junitxml=artifacts/test-results/V4-001/backend-final.xml`，14通过|7模块边界+2协议/失败初始化+4应用+1目录/重启；Redis失败/污染fake，无真实模型。含新投影、本地降级、SQL故障、时间预算；与44项部分重叠|
|L1|`$env:ORVIA_TEST_RESULTS='artifacts/test-results/V4-001'; npx vitest run apps/desktop/tests/v4-auxiliary.test.ts apps/desktop/tests/credentials.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V4-001/unit.json`|初次16通过/1失败：旧断言假设全部凭据均已配置，新Redis默认缺失；修正断言并补独立引用测试，只重跑credentials为16通过（credentials-final.json）|
|L1|同vitest运行 `apps/desktop/tests/v4-auxiliary.test.ts apps/desktop/tests/credential-sync.test.ts`，`--outputFile=artifacts/test-results/V4-001/contracts-final.json`，4通过|最终projection/错误reason契约、拒绝远端/命令/正文字段、同步故障停止旧后端；safeStorage单测为mock适配器|
|L2真实服务|设置 `ORVIA_REDIS_TEST_PORT=16379`、`ORVIA_REDIS_TEST_CONTAINER=orvia-v4-001-test`，同pytest运行 `backend/tests/test_v4_auxiliary_live.py`，`--basetemp=artifacts/test-results/V4-001/live-data --junitxml=artifacts/test-results/V4-001/live.xml`，3通过|真正Redis读写、cache污染/重复/过期版本、删除后晚到通知、docker stop/start实际断服、requirepass与撤回、完整等待31秒验证30秒TTL|
|L2真实服务|同live命令加 `-k 'not ttl'`，`--basetemp=artifacts/test-results/V4-001/live-final-data --junitxml=artifacts/test-results/V4-001/live-final.xml`，2通过/1未选中|移除redis7弃用参数并完成初始化清理后最小相关复验；已通过TTL不重复等待|
|L3|设置 `ORVIA_TEST_MODULE=V4-001`、`ORVIA_REDIS_TEST_PORT=16379`，`npx playwright test tests/e2e/v4-auxiliary.spec.ts`，1通过；增加本地projection断言后同命令1通过|真实服务设置/错误端口TCP失败/恢复/重启/关闭、寒暄零模型；截图connected/disabled/local-projection已查看；v4-e2e-console.log保存最终命令输出，共享e2e.json被下一流程覆盖|
|L3|设置MODULE与 `ORVIA_TEST_RESULTS=artifacts/test-results/V4-001`，`npx playwright test tests/e2e/m20.spec.ts --grep '无技术模式、先需求后目录授权'`，1通过|Redis默认关闭，真实批次/205条合成文件/完整分页/深度/撤权，原生选择模拟；scan-e2e.json|

共57个不同后端用例（含3真实Redis用例）、20个不同前端用例、2个Electron流程通过。subagent先跑模块测试：6项通过；补SQL故障测试时fake上下文封装失败，修正测试后只重跑该项通过，主Agent最终7项均纳入backend-final.xml通过。初次live产生redis retry_on_timeout弃用提示，移除参数后live-final仅剩原有LangGraph弃用提示；未因此升级旧LangGraph。主Agent最终验收的临时目录、profile、报告和截图均在本模块忽略目录。subagent早期命令未带basetemp/junitxml，临时合成SQLite曾位于pytest默认Temp，这是目录约定偏差；未伪称当时已有项目内报告。实际早期命令为 `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_v4_auxiliary.py -q`（4/4/6通过，最后6通过1失败）及同命令仅SQL失败用例（1通过）。检查后仅对可确认属于新模块的pytest-308/309/310内12个测试目录逐项核验路径/无重解析点并用Move-Item归档到 `artifacts/test-results/V4-001/early-pytest/`，清单early-artifacts-archive.json；未操作其它临时目录。最终backend-final.xml包含完整7项通过。

### 限制、试用和交付

仅请求状态元数据缓存/只读通知，没有正文缓存、后台业务执行、分布式锁或完整历史列表；大量旧数据按批次重建，不保证立即全量呈现。命中仍核对SQLite，未做性能收益基准。仅验收本机Redis7.2.4单实例；未验证其它版本、Cluster、TLS、ACL组合、恶意本地服务的全部资源行为；EVAL不可用会降级。用户负责部署账户/升级和全服务资源限制，应用不随安装器部署Redis。生产safeStorage在本轮使用mock存储适配器回归，未做新发布版/独立Windows验收。旧安装包不包含V3及V4新代码；不访问真实模型或供应商。

试用 `npm start` → 设置 → Redis辅助服务，填用户已部署的回环服务端口/库号并启用。可关闭辅助连接后选择合成目录扫描，或在服务停止时观察降级；服务恢复后点击检测。开发密码写被忽略.env.local的REDIS_PASSWORD后重启；需要认证但未提供时明确降级，不填假值、不借用模型Key。完整模块公共接口/示例见backend/src/orvia_backend/auxiliary/README.md。

- [x] √ 正常本地提交，标题 `feat(V4-001): add optional local Redis auxiliary service`；实际hash见Git历史和交付消息，沿用既有单次git -c作者，不改持久配置。
- [ ] 用户手动push；Agent不推送、不发布、不重建安装包。V4-001提交后停止，V4-002未开始。

收尾L0：本轮内联Python文档/忽略/锁定检查29项通过，l0-doc-audit.json由XML交叉统计57个不同后端用例。`git status --short`、`git diff`、`git diff --cached`及两套diff --check已核对；显式暂存本模块35文件，预存两文件未暂存。敏感审计复用扩展REDIS_PASSWORD检查的backend/tests/m19_hygiene.py，实际index的禁入路径、真实密钥匹配、私钥块、模块产物真实密钥匹配和资源manifest差异均0，hygiene-staged.json；仅报告凭据存在性，不输出值。实际审计命令：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -c "import pathlib,sys; sys.path.insert(0,str(pathlib.Path('backend/tests').resolve())); import m19_hygiene as audit; audit.RESULT=pathlib.Path('artifacts/test-results/V4-001').resolve(); raise SystemExit(audit.main())"
```

`docker stop orvia-v4-001-test`已执行，保留已停止的专用容器/镜像便于用户自行试用；未关闭Docker Desktop或更改其它容器。本轮没有push或安装包命令。

## V4 连续授权与 V4-002 实施（2026-10-07）

用户 `/goal` 已授权002→004→003→005→006→007→008→009→010→011逐模块连续实施，每模块实际验证、记录与独立commit后自动继续，取代此前相应停止要求；001不重复实施，不push/Release/重建安装包。模型首次下载仍需准确来源/版本/体积/校验预览及用户确认。

预检：Orvia/main，HEAD `a6c9d30`，001独立提交及PROGRESS证据齐全；`git ls-remote --symref origin HEAD`核对远端main/`5d6d0e9`，不fetch或更改网络。预存未跟踪`.zcodeignore`、`docs/INTERVIEW.md`保留，不暂存；无LICENSE删除。原001测试结论复用，不重复真实Redis或旧模型测试。

本模块主Agent负责application、桌面固定协议/原生审批/界面、整合、验证、文档与提交；subagent独占新skills目录、test_v4_skills.py，另一subagent只读审查。无真实Key或私人资料传递，不提前实施后续模块。复用当前LangGraph/Pydantic/SQLite，无新依赖。

- [x] √ V4-002 实际实现、权限/版本/组合边界、L0～L3验证及文档。
- [x] √ V4-002 敏感审计和独立正常本地commit，标题及证据见本节。
- [ ] 用户手动push；Agent不推送、不发布、不重建安装包。

### 实施决策与真实能力

自有workflow.json schema_version=1，不宣称任意Skill包兼容。SKILL.md只是完整审查的不可信说明，不注入模型指令。内置File Organize实际执行一级清单40项→空间统计前5项；Memory Context/Query Rewrite/Web Research/Report Build分别等待003/006/010，不可计划。导入可引用固定五个读取工具和已声明依赖Skill，参数仅结构化前序结果引用，不执行脚本/表达式/安装/文件变更。原有文件变更审批链保留。

skills_registry保存快照/hash/版本/启停generation，skills_executions保存计划和逐步结果；事务追加表，不改旧user_version。每个步骤固定ComputerGateway/Pydantic权限与参数复核，LangGraph推进必须有完整结构化事实与SQLite保存；任何不完整/截断/errors停止为limited，不伪报completed。坏审批、版本失效写failed；原生取消零调用保存interrupted，重启旧planned/running中断，旧token不复活、不重试。专用Mission只读任务独立于聊天，最近20记录及准确结果可回查；不会以聊天删除清除独立任务账本。原生选择/批准后仅主进程注入目录及grant，完成/取消/异常均撤销本次grant；默认不授予文本正文或系统权限。

预算：仅本地普通目录、恰好2文件，SKILL.md8KiB/workflow16KiB/两文件64KiB硬限/完整审查32KiB；第三个目录项立即拒绝；PathPolicy和打开句柄防链接/联接/竞态。最多32导入，每页10、审查16、内存计划64；每包16节点/16依赖/4层组合/32叶步骤。输入8KiB、复制表达式16KiB、隐藏checks/output及计划40KiB、结果含逐步事实32KiB，执行10秒，主进程响应15秒留持久化余量。固定object/string/integer/boolean schema；双端ID/UTF16字段长度一致，拒绝控制字符/重复JSON键/非有限数/未知schema。复制前预算防重复引用指数膨胀；循环检查不因依赖禁用被遮蔽。具体结构/API/输入输出/示例/限制见skills/README。

### 验证与证据

全部结果在`artifacts/test-results/V4-002/`，Git忽略。无新增依赖、外网服务、真实模型调用；真实SQLite/LangGraph/ComputerGateway/合成文件读取与合成失败注入分开。L3为真实Electron–Python，已有m20测试启动器只模拟原生选择/确认和模型网络；测试中模型调用计数为0，不冒充人工原生验收。未访问用户真实文件。L4不必启动：增加有界只读框架及固定接口，已有初始化/配置/删除相关L1/L2回归，未变更模型/执行副作用/发布链，不重建安装包。

|等级|实际命令与结果|证据与限制|
|---|---|---|
|L0|`npm run check`、`npm run build`通过；`backend/.venv/Scripts/python.exe -m compileall -q backend/src/orvia_backend/skills`通过|最终构建仅开发版，含TypeScript检查，无打包；原LangGraph弃用提示保留|
|L1/L2|`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_v4_skills.py -q --basetemp=artifacts/test-results/V4-002/skills-tmp --junitxml=artifacts/test-results/V4-002/skills-junit.xml`，36通过/1跳过；追加审计后同命令41通过/1跳过|真实临时SQLite/组合引用/目录工具；注入失败、超时和超限为合成，符号链接创建权限不足skip|
|L1/L2|主Agent同pytest运行 `backend/tests/test_v4_skills.py backend/tests/test_v4_skills_protocol.py backend/tests/test_application.py backend/tests/test_configuration.py backend/tests/test_v3_management.py -q --basetemp=artifacts/test-results/V4-002/final-data --junitxml=artifacts/test-results/V4-002/backend-final.xml`，80通过/1失败/1跳过|协议旧fixture期待错误授权后仍可执行原计划；新的消费语义已保存failed，修正fixture重新计划，不修改生产语义|
|L2|同pytest仅`backend/tests/test_v4_skills_protocol.py`，`--basetemp=artifacts/test-results/V4-002/protocol-complete-data --junitxml=artifacts/test-results/V4-002/protocol-complete.xml`，1通过|真实应用/gateway两步骤、重复/越权拒绝、重启持久化、固定配置；此前protocol.xml和protocol-final.xml也通过，错误审批消费改变后本项最小复验|
|L1/L2|同pytest模块加`-k 'cancel_history or exponential or pagination or identifier or hidden or timeout or control'`，`--basetemp=artifacts/test-results/V4-002/audit-data --junitxml=artifacts/test-results/V4-002/audit-final.xml`，4通过；`-k runtime_repeat`，runtime-audit-data/runtime-audit.xml，1通过|追加取消/重启/失效账本、满额中文分页、隐藏展开、合成时钟晚到响应、重复输出拒绝；复用仍有效先前项|
|L1/L2|同pytest模块`-k human_summary`，summary-audit-data/summary-audit.xml，5通过；`-k 'missing_cycle or disabled_dependency'`，topology-data/topology-final.xml，2通过|控制字符/UTF16、失效Unicode、禁用依赖无法隐藏循环；未对全库重复测试|
|L2|subagent `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_v4_skills.py -q -k 'human_summary or junction'`，`--basetemp=artifacts/test-results/V4-002/skills-boundary-tmp --junitxml=artifacts/test-results/V4-002/skills-boundary-junit.xml`，6通过；最后同命令筛选 -k disabled_dependency，--basetemp=artifacts/test-results/V4-002/skills-last-tmp --junitxml=artifacts/test-results/V4-002/skills-last-junit.xml，1通过|真实普通权限`mklink /J`合成目录联接被拒绝，解除联接不删除指向目录；非提权。5项summary与主Agent重复不重复计数|
|L1|`npx vitest run apps/desktop/tests/v4-skills.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V4-002/unit-final.json`，2通过|固定renderer边界，无路径/grant/批准/自由方法透传，响应契约；无真实模型|
|L3|`$env:ORVIA_TEST_MODULE='V4-002'; npx playwright test tests/e2e/v4-skills.spec.ts`，最终1通过|启停、内置两步骤、原生取消、导入取消/登记、导入属性读取、重启记录回查/零模型计数；最终e2e.json及electron目录截图|

不同后端用例合计93通过、1跳过（Skills48+协议1+旧回归44）；前端2通过，Electron1完整流程通过。早期L3第一次因builtin名称fixture变化失败，第二次开发中初始化未连通；在迁移与名称稳定后最小流程通过，扩展导入/history后再验证通过，最后复验仍通过；没有将中间失败隐藏为通过。已实际查看skills.png与restart.png，M19视觉、可读中文步骤和展开技术事实无横向溢出。敏感审计和提交见下节。

subagent另有已复用的审计最小集合：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_v4_skills.py -q -k 'maximum_chinese or repeat_output or runtime_repeat or timeout_unknown or cancel_history or human_summary' --basetemp=artifacts/test-results/V4-002/skills-review-tmp --junitxml=artifacts/test-results/V4-002/skills-review-junit.xml`，10通过/37未选择；后续主Agent/边界复验重叠项已去重。完整目标报告skills-junit.xml被最后41通过/1skip结果覆盖，早先36项结论不伪称仍有独立XML。

### 限制与试用

`npm start`→设置→Skills工作流，选File Organize，输入`{"path":"."}`，原生选择合成目录并确认计划；完整目录不超过40项，否则明确limited。模块README给出单文件属性包与组合示例，导入、更新须重新审查；最近工作流记录只读取事实，不恢复授权。默认不能读取正文；不具有任意Skill脚本、并行/条件节点、自动重试或恢复执行。静态schema及资源预算不证明任意资料正确。只读工作线程超时后可能在现有FileTools自身预算内收尾，程序忽略晚到结果、不重试、不接续；不能强杀任意文件系统调用。独立Mission账本当前无UI删除入口。原生选择/确认模拟、未独立Windows/发布模式验收，旧安装包未包含本模块。

当前模块提交标题为`feat(V4-002): register reviewed skills and run bounded workflows`，实际hash见Git历史；沿用一次性git -c身份，不改持久配置。提交完成后自动进入V4-004，不等待继续授权；模型首次下载仍需用户明确确认。

收尾L0：内联XML去重审计`l0-audit.json`确认93不同通过/1跳过/最终未解决失败0、README存在、产物忽略、真实模型0。检查`git status --short`、`git diff`和`git diff --cached`及两套diff --check；显式27本模块文件，用户预存两文件不暂存。敏感审计复用下列真实命令，`hygiene-staged.json`：禁入路径、真实密钥匹配、私钥块、产物真实密钥匹配、资源manifest差异均0，仅输出凭据是否存在和计数。无数据库/日志/用户文件/测试产物入index。

```powershell
backend/.venv/Scripts/python.exe -X utf8 -c "import pathlib,sys; sys.path.insert(0,str(pathlib.Path('backend/tests').resolve())); import m19_hygiene as audit; audit.RESULT=pathlib.Path('artifacts/test-results/V4-002').resolve(); raise SystemExit(audit.main())"
```


## V4-004 已完成：本地混合检索（2026-10-07）

**当前事实摘要**：首次下载已获明确批准，六个固定官方工件核验、真实本地语义/资源与Electron验收已完成，102个不同后端用例、2个前端契约、2个Electron流程通过。交付独立正常本地commit标题 `feat(V4-004): add verified local embeddings and scoped hybrid retrieval`，实际hash以Git历史为准。按用户最新指令本模块完成后暂停，003及其后未开始；完整Goal尚未完成，所有提交仍待用户手动push。下方“实施中/待批准/未执行/自动继续003”为先前阶段历史，当前结果以末尾验收记录与最新停止点为准。

前置模块002已正常提交`c1ca871`；001为`a6c9d30`，均未push。本模块开始前复核main/历史/工作区，仅预存未跟踪`.zcodeignore`与`docs/INTERVIEW.md`保留，不读取其私人正文、不暂存。初始实施阶段004未完成、未暂存、未commit，003及以后未开始；完整Goal仍未完成，004最终状态见下。主Agent负责模型工件/运行器、应用/桌面和整合；subagent独占retrieval service/README/目标测试，另一subagent只读审查，已交接停止写入。

- [x] √ 本机开发代码：固定工件清单与本地独立工作器、SQLite向量/FTS5/余弦/RRF、准确有效关联范围、原生下载确认与模型目录选择、设置检索界面、资料回答原文分块/定位接入。
- [x] √ 已完成的合成嵌入契约、真实SQLite/FTS、关键词Electron流程与旧权限/删除/文档/配置回归，证据见下；这些不等于真实Qwen验收。
- [x] √ 首次模型权重下载用户确认：2026-10-07用户明确“批准下载”，沿用已展示官方固定修订/六文件/体积/许可/摘要；现在允许下载并继续004真实验收，历史等待记录保留。
- [x] √ 下载/逐文件校验固定Qwen、真实中文/混合语言语义基准及工作器树RSS/时间/向量和SQLite大小、实际模型Electron与重启流程；准确命令、指标与限制见末尾验收。
- [x] √ 最终模块/项目文档、开发清单、暂存敏感审计与V4-004独立正常本地commit；标题与提交后状态见末尾交付记录及Git历史。
- [ ] 用户手动push；Agent不push/Release/重建安装包。004完成并commit后按用户最新指令暂停，003未开始。

### 已实施的技术决定

仅已明确纳入范围的context_documents/context_chunks原文；不扫描目录或重读原文件。ScopedRetrieval只使用当前会话有效材料，最多3份/每份50单元，构造最多150准确source标签（总48KiB），查前限定SQL，查后复核关联；解除关联不能恢复旧正文到普通回答。空范围[]直接零结果/零嵌入，不转None扩大历史。UI清除当前会话全部向量可释放历史派生预算，原文件/导出/原文FTS保留。

固定1024维little-endian float32，正文SHA256、文档hash、模型修订和预处理签名绑定；FK context_chunks ON DELETE CASCADE覆盖来源替换/删除和会话purge。每任务512段/全库4096段、每段600码点、query200、候选总512、向量读取128/批；模型调用最多8段/请求，工作器内部4段、1024tokens、不静默截断。重建120秒（含排队/核验）、单批30秒，锁外嵌入与事务二次快照/持久epoch，清理/删除/版本变更后晚到结果不写回。关键词最多32去重词OR召回，余弦独立排序、RRF60、重复正文仅嵌入一次，保留全部SQLite来源和最多8个显示定位，输出32KiB明确受限。没有有效索引时零查询嵌入；损坏/超限/签名不匹配/缺模型明确keyword_only原因。

运行器仅可信固定CPU库，4线程/float32、官方query instruction/left padding/last-token pooling/L2；HF离线local_files_only、trust_remote_code=False、safetensors。独立进程剥除Key/代理/Python用户环境；每0.1秒RSS监测、超过6GiB终止，属于监测阈值而非OS硬上限，准备/请求/取消终止晚到工作器，不自动重试。启动应用不加载模型，点击加载此前模型重新校验已批准路径；配置写入原子替换并拒悬空链接。下载只有主进程原生确认后的固定入口，准确HTTPS及摘要/900秒/临时文件有界清理，无网络降级、不覆盖已有工件、不联网补文件。推理是否正确仍待真实模型测试。

保持三角色固定模型与供应商、SQLite事实、原有审批/权限链。资料回答分块改为与context一致600/overlap80，命中准确匹配eid/unit/chunk/text；完整发送预览、原生批准和严格引用验证保留。旧M15合成seed补实际material_added，模拟产品attach/read有效关联，不能用测试直接save绕过M20集合。

### 模型准备待决与依赖事实

官方模型`Qwen/Qwen3-Embedding-0.6B`，修订`97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`，Apache-2.0。[官方说明](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)、[固定文件目录](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/tree/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3)。只获取官方API元数据（model-source.json），尚未下载下表工件。总1207469240字节≈1.12GiB；可由用户批准首次下载到项目忽略的私有目录，或提供已有目录核验。具体待决来自V4_OPTIMIZATION第2.2节与Goal第三部分的“本地模型…首次下载确认”，不是普通依赖安装追加确认。

|文件|字节|官方校验算法/摘要|
|---|---:|---|
|config.json|727|Git blob SHA1 cef2749ee93607b8f9a58ec72f4f6bfaf874e71d|
|merges.txt|1671853|Git blob SHA1 31349551d90c7606f325fe0f11bbb8bd5fa0d7c7|
|model.safetensors|1191586416|SHA256 0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd|
|tokenizer.json|11423705|SHA256 def76fb086971c7867b829c23a26261e38d9d74e02139253b38aeb9df8b4b50a|
|tokenizer_config.json|9706|Git blob SHA1 7345216a0785dc7086e8c245b2a9d3896ce2b756|
|vocab.json|2776833|Git blob SHA1 4783fe10ac3adce15ac8f358ef5462739852c569|

已检查Python3.12.6、uv0.12.5、CPU i7-14650HX、31.73GiB内存与D盘约153GiB可用。未发现已有Qwen工件，不用其它本地模型替代。先核查[官方PyTorch CPU wheel索引](https://download.pytorch.org/whl/cpu/torch/)、[Transformers4.57.6](https://pypi.org/project/transformers/4.57.6/)、[Safetensors0.7.0](https://pypi.org/project/safetensors/0.7.0/)、许可/兼容性/下载摘要，runtime-source.json。实际安装命令：

```powershell
C:/Users/18532/.local/bin/uv.exe add --directory backend --python .venv/Scripts/python.exe --optional embeddings 'transformers==4.57.6' 'safetensors==0.7.0' 'torch @ https://download-r2.pytorch.org/whl/cpu/torch-2.8.0%2Bcpu-cp312-cp312-win_amd64.whl#sha256=2be20b2c05a0cce10430cc25f32b689259640d273232b2de357c35729132256d'
```

CPU PyTorch2.8.0+cpu，BSD-3-Clause，wheel619352539字节；Transformers4.57.6 Apache-2.0、wheel11993498字节；Safetensors0.7.0 Apache-2.0、winabi3wheel341380字节。pyproject可选embeddings与uv.lock固定来源/版本/hash，105锁定包、只新增13、已有版本变化0。实际新增安装12库：filelock4.0.12、fsspec2026.9.0、huggingface-hub0.36.2、jinja2 3.1.6、markupsafe3.0.4、mpmath1.3.0、networkx3.7、safetensors0.7.0、sympy1.14.0、tokenizers0.22.2、torch2.8.0+cpu、transformers4.57.6；同版editable项目重新安装。hf-xet1.7.0仅跨平台锁定，当前marker未安装。dependency-audit.json按安装分发清单统计新增文件约3247006488字节（约3.02GiB，不含权重/uv缓存/全venv或文件系统分配），全部项目venv；未升级既有库、不装GPU/全局资源。uv跨盘hardlink回退复制是提示，安装成功。真实导入AutoModel/AutoTokenizer/torch通过，torch.cuda.is_available=False；不等于模型推理通过。

### 当前验证（仍缺真实Qwen）

产物统一`artifacts/test-results/V4-004/`，Git忽略，模型/云端API调用0。后端36目标用例为真实临时SQLite/FTS＋合成嵌入；运行器测试用MockTransport或进程/RSS替身，不访问实际下载服务。Electron为真实Electron–Python/SQLite/原文解析，m20-launch仅模拟原生文件选择/确认，首次下载取消，没有下载请求；不冒充人工原生或模型验收。L4评估：仅可选本地检索，无发布或副作用业务变更，当前先做相关L0～L3，真实模型/资源和最终审查仍未完成。

|级别|实际命令/结果|报告|
|---|---|---|
|L0|`npm run check`、`npm run build`通过；`C:/Users/18532/.local/bin/uv.exe lock --directory backend --check`通过；`backend/.venv/Scripts/python.exe -m compileall -q backend/src/orvia_backend/retrieval`通过|仅开发构建，无安装包；105锁定包|
|L1/L2|`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_v4_retrieval.py -q --basetemp=artifacts/test-results/V4-004/retrieval-tmp --junitxml=artifacts/test-results/V4-004/retrieval-junit.xml`，29通过|初轮；后续只重跑新增/变动项|
|L1/L2|同pytest目标加`-k 'signature_change_during or keyword_does_not'`，retrieval-audit-tmp/retrieval-audit-junit.xml，2通过；`-k 'empty_scope or astral_unicode or batch_scope or deadline or vector_contract or normalization'`，retrieval-boundary-tmp/retrieval-boundary-junit.xml，11通过|每个路径前缀均artifacts/test-results/V4-004/|
|L1/L2|同目标`-k 'clear_epoch or three_documents or batch_scope'`，retrieval-scope-tmp/retrieval-scope-junit.xml，3通过；`-k 'missing_or_invalid or runtime_signature_change or signature_change_during or persistent_vector or source_deletion'`，retrieval-query-tmp/retrieval-query-junit.xml，12通过|150定位兼容、并发clear epoch、缺索引零查询嵌入|
|L1/L2|同目标`-k 'batch_scope or rebuild_race or candidate_limit or three_documents or missing_or_invalid or real_sqlite'`，retrieval-final-tmp/retrieval-final-junit.xml，10通过|目标按test ID去重36通过，非36+其它重复数|
|L1/L2|`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_embedding_runtime.py backend/tests/test_v4_retrieval_protocol.py backend/tests/test_m15_synthesis.py backend/tests/test_application.py -q --basetemp=artifacts/test-results/V4-004/integration-data --junitxml=artifacts/test-results/V4-004/integration.xml`，11通过/2失败|原fixture直接save缺有效关联；补material_added和空scope后最小复验|
|L1/L2|同pytest仅test_v4_retrieval_protocol.py及test_m15_synthesis.py::test_preview_generate_conflict_restart_isolation_and_idempotency，recheck-data/recheck.xml，2通过；新增50单元后仅test_v4_retrieval_protocol.py，scope-data/scope.xml，2通过|保留旧失败历史，实际失败均已解决；旧M15其它项复用integration.xml|
|L1/L2|同pytest仅test_v4_embedding_runtime.py，runtime-final-data/runtime-final.xml，6通过|官方清单/流式SHA与Gitblob/额外代码拒绝/缺模型零联网/取消与RSS终止/固定HTTPS下载MockTransport、降级HTTP拒绝与临时清理|
|L1/L2|同pytest运行test_v3_management.py test_m13_documents.py test_configuration.py，regression-data/regression.xml，48通过|真实删除/文档/角色配置相关回归；模型网络mock|
|L1|`npx vitest run apps/desktop/tests/v4-retrieval.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V4-004/unit.json`，2通过|renderer拒路径/来源/URL/批准，响应非BMP600码点/finite/未知字段|
|L3|`$env:ORVIA_TEST_MODULE='V4-004'; npx playwright test tests/e2e/v4-retrieval.spec.ts`，1通过|缺模型、原生下载取消、合成DOCX关键词、清向量、重启原文查询；e2e.json/electron-A6fsjV截图|

XML按(classname,name)取最新结果去重99个不同后端用例通过、0未解决失败/0skip，verification-in-progress.json。两张Electron截图已生成，keyword.png已实际查看，中文原文/降级/会话选择/细节可读，无横向溢出。子任务只读审查发现空scope、50单元兼容、UTF16/码点、悬空配置链接、清理晚到重建及缺索引浪费推理；均实际修复和相应最小验证。仍有原LangGraph弃用提示，不为此升级依赖。

当前工作树敏感审计命令：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -c "import pathlib,sys; sys.path.insert(0,str(pathlib.Path('backend/tests').resolve())); import m19_hygiene as audit; audit.RESULT=pathlib.Path('artifacts/test-results/V4-004').resolve(); original=audit.git_names; audit.git_names=lambda *args:[name for name in original(*args) if name not in {'.zcodeignore','docs/INTERVIEW.md'}]; raise SystemExit(audit.main(working=True))"
```

hygiene-working.json：27当时模块工作文件，禁入/真实Key/私钥/161产物Key/资源manifest差异均0，仅输出Key是否存在。预存两文件排除、不读取；不把工作树审计当cached提交检查。当前已检查git status/diff/diff --check/cached（空），尚未暂存；文档收尾后需最终审计。没有push或安装包操作。

### 续接点与限制

首次下载准确版本确认已待答。用户批准后才下载六文件、按固定摘要核验，并显式运行`backend/tests/live_v4_embedding.py`（ORVIA_EMBEDDING_MODEL_PATH设已批准普通目录）；该脚本只有固定16主题/8问题合成资料、不读Key、不下载，报告相同FTS5 OR基线与vector/hybrid Recall@5/MRR@5/时间/RSS/SQLite大小及删除/隔离/去重/重启。尚未运行，所有真实模型指标空缺。随后补实际模型Electron、必要失败项修复、准确文档与最终审计、独立004commit；再自动进入003。

目前可`npm start`→添加合成文档→设置→本地混合检索选择会话，缺模型关键词查询；首次下载原生取消不下载。运行库约3.02GiB、固定权重另约1.12GiB；首次下载许可未被依赖安装授权替代。未验证真实Qwen性能/大满额索引资源、未知网络速度、发布模式、独立Windows或GPU；RSS为抽样阈值，引用仅结构/身份校验，不证明语义真实性。旧安装包不含本模块。不能以目前代码/构建/mock标完整004完成，不越过模块顺序。

本次等待前收尾：同工作树敏感命令在全部文档更新后再次通过，hygiene-working.json实际34模块文件/210产物，禁入/密钥/私钥/资源manifest均0；cached仍空，预存两文件保留。compileall包含live_v4_embedding.py语法通过，但未实际运行模型脚本。最后HEAD仍c1ca871，004无提交。


### V4-004 自动续接边界补审（仍待首次模型下载确认）

上一Goal轮已产生实质代码/验证/文档进展；本轮自动续接不包含下载批准，继续不依赖模型的边界审查。新增发现并修复两项：chat purge删除retrieval_epochs代数记录，仅保留既有随机ID墓碑，兼容初次迁移尚无检索表；prepare总180秒包含排队、两次父核验和加载，避免阶段60+120+60叠加超过桌面190秒等待。下载900秒加prepare180秒仍在主进程1100秒等待内，不自动重试。未下载模型或进入003。

实际最小复验命令：`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retrieval_protocol.py::test_chat_delete_removes_vectors_and_epoch_leaves_only_tombstone backend/tests/test_v3_management.py::test_delete_all_local_evidence_and_private_copies_only backend/tests/test_v3_management.py::test_confirmed_delete_failure_resumes_on_restart -q --basetemp=artifacts/test-results/V4-004/delete-final-data --junitxml=artifacts/test-results/V4-004/delete-final.xml`，L1/L2三项通过。`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_embedding_runtime.py -q --basetemp=artifacts/test-results/V4-004/runtime-deadline-data --junitxml=artifacts/test-results/V4-004/runtime-deadline.xml`，L1七项通过。全部XML按ID去重101个不同后端通过、0失败/跳过；未改UI源码，不重复既有构建/关键词L3。

已补显式真实Qwen Electron流程：原生选择固定工件/建立2片段/实际hybrid/重启加载/云端调用计数0，只有ORVIA_EMBEDDING_MODEL_PATH显式设置才执行，否则skip；尚未运行，不冒充模型验收。L0 `ORVIA_TEST_MODULE=V4-004 npx playwright test tests/e2e/v4-retrieval.spec.ts --list`确认2个流程可发现，此命令仅列出，不执行模型或关键词流程；原1通过仍有效。git diff --check通过、cached仍空。真实模型基准和该第二Electron流程留待批准后执行。

同一实质待决事项仍为V4第2.2节/Goal明确要求的首次模型下载确认，现有开发代码和所有可独立验证均已完成，不能用自动续接文本代替批准。不创建未验收004 commit，不推进003。

### V4 Goal 受阻记录（2026-10-07）

首次模型下载确认的同一条件已连续三Goal轮出现：首轮实现/验证并请求准确固定版本；第二轮补删除与准备总期限/测试；第三轮核对仍无用户明确批准或已有目录，已无可独立完成的当前模块工作。按Goal规则标blocked，不标完成、不越过顺序。当前HEAD c1ca871；004未暂存/未commit，101个不同后端通过，但真实Qwen脚本与模型Electron均未执行。用户批准首次固定官方Qwen六文件约1.12GiB下载，或提供已有目录后续接004真实验收与独立提交，继而依授权顺序推进余下模块；原完整目标保留。模型来源/固定修订/许可/六文件校验信息见本模块上表。无push、Release或安装包操作。

### V4-004 下载批准后续接（2026-10-07）

用户明确“批准下载”，已解除同一首次模型待决条件；沿用固定修订97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3及上表摘要，不改模型。复核main/HEAD c1ca871和工作区，保留已有004实施文件与预存两文件。现开始项目私有.orvia/models六文件下载、逐文件核验和真实本地验证；无云端正文、push或安装包。完整后续模块授权继续有效，004完成并独立commit后自动继续003。

下载续接初次真实执行：`backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_v4_prepare.py`，首次MODEL_DOWNLOAD_FAILED/约21秒、无模型文件，download-live-first-failed.json保留。小文件连接诊断download-network-check.json：已有SSL_CERT_FILE配置、代理未配置；trust_env=False连接超时，沿用已有环境时官方固定config HTTPS200/727字节。下载器改为沿用既有HTTPS证书/代理配置，验证仍开启，不改系统/Git设置，工作器仍离线剥除代理。顺便修复旧ready工作器掩盖本次下载失败，失败关闭旧工作器并明确降级。L1 `backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_embedding_runtime.py -q --basetemp=artifacts/test-results/V4-004/download-fix-data --junitxml=artifacts/test-results/V4-004/download-fix.xml`7通过；修正后显式重新执行live_v4_prepare，当前尚在下载，不视为完成。

用户最新停止点：2026-10-07“完成本模块后先暂停，待我指令再继续”。当前模块为V4-004；下载已批准，继续全部实际验证、记录和独立commit，完成后按用户要求暂停Goal，不开始003及后续，不push/打包。此项取代此前本轮004commit后自动开始003的要求；历史计划保留。

### V4-004 最终真实验收与交付（2026-10-07）

下载批准与停止调整均来自用户直接指令。固定官方修订仍为97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3，不更换角色模型或供应商；审批、SQLite事实、有效资料范围与引用核验保留。实际权重目录`.orvia/models/qwen3-embedding-0.6b/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`、私有配置`.orvia/embedding-model.json`及全部报告均Git忽略，不入安装包。模型六文件共1207469240字节，运行库新增文件约3247006488字节，版本/来源/许可/安装命令见上述依赖事实，未安装额外未来模块资源。

实际下载修正后显式重跑`backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_v4_prepare.py`：六文件大小/官方摘要全部核验、离线预加载通过，download-live.json，165.453秒包含下载与加载。保留第一次失败与连接诊断，不自动重试、不关闭TLS校验、不改系统或Git网络配置。下载器沿用既有HTTPS证书配置；模型推理仍完全离线、剥除Key/代理、拒绝远程代码。

资源审查发现Windows项目venv的python.exe是启动器，仅其RSS约4MiB会漏计真正模型子进程。已修复为启动器及已识别自有后代合计RSS，最多4个子进程，关闭/超限/取消回收自有工作器树；psutil Process绑定进程身份，未操作用户应用。之前download-live.json和real-1791371306895570300/benchmark.json中的launcher-only peak不作资源验收依据，保留为历史。实际最小复验：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_embedding_runtime.py -q --basetemp=artifacts/test-results/V4-004/process-tree-data --junitxml=artifacts/test-results/V4-004/process-tree.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_embedding_runtime.py -k launcher_child -q --basetemp=artifacts/test-results/V4-004/process-tree-extra-data --junitxml=artifacts/test-results/V4-004/process-tree-extra.xml
$env:ORVIA_EMBEDDING_MODEL_PATH=(Resolve-Path -LiteralPath '.orvia/models/qwen3-embedding-0.6b/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3').Path
backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_v4_embedding.py
backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_v4_resources.py
backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_v4_resources.py --token-only
npm run build
$env:ORVIA_TEST_MODULE='V4-004'
npx playwright test tests/e2e/v4-retrieval.spec.ts --grep '显式已有Qwen'
```

|级别|实际结果与证据（共同前缀artifacts/test-results/V4-004/）|性质/限制|
|---|---|---|
|L1|运行器全套当时7通过，process-tree.xml；新增launcher_child最小1通过/7未选择，process-tree-extra.xml|mock进程/RSS/下载边界；不称真实资源验收|
|L2/L3真实本地模型|live_v4_embedding.py修正资源后完整通过，real-1791371496972254000/benchmark.json|真实Qwen/SQLite/FTS，固定16主题8问题，云模型调用0；无用户资料或密钥|
|L2资源|首次live_v4_resources.py满批8×600码点通过，14.109秒/1024维有限单位向量，601码点拒绝；resource-1791371578309173900/resources.json|该次整体失败于错误fixture假设600emoji会超过1024tokens，实际仅601tokens；保留报告，不称整次通过|
|L2资源失败项最小复验|固定分词器实测600个𒀀为1201tokens，改fixture后--token-only通过，0.141秒拒绝MODEL_TOKEN_LIMIT并关闭工作器；resource-1791371736233745400/resources.json|复用前次满批与字符阶段通过证据，token阶段单独实际重测，不静默截断|
|L0|npm run build含TypeScript检查通过；此前uv lock --check/compileall通过，文档-only不重复代码测试|只新增已锁定optional embeddings，既有库版本变化0|
|L3|实际模型Electron1通过/27.7秒，e2e.json、electron-real-6VWdQa/hybrid.png|原生目录选择/确认由m20-launch模拟；真实固定Qwen核验、2片段建立索引、hybrid检索、重启复用向量并显式重载模型；云调用0|

全部后端JUnit按(classname,name)以最后结果去重：**102个不同用例通过，0未解决失败/跳过**；前端目标契约2通过。Electron关键词1通过（electron-A6fsjV）复用，加上述真实模型1通过，共2个不同流程，未把默认未设置模型目录的skip当真实验收。verification-final.json记录统计与闭合；keyword.png、restart.png、hybrid.png均已实际查看，中文状态、原文、通道和来源详情可读，无横向溢出。最后进程清理检查固定worker模块进程数量0，不输出其它进程命令或私人资料。

硬件Intel Core i7-14650HX、RAM34075090944字节、Windows 11 build26200、Python3.12.6，CPU float32/4线程，Torch2.8.0+cpu、Transformers4.57.6、Safetensors0.7.0；无CUDA，固定签名Qwen/Qwen3-Embedding-0.6B@97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3:1024:qwen-lasttoken-v1。以下同一合成集/相同FTS5 OR基线单次指标：

|通道|Recall@5|MRR@5|平均查询秒|
|---|---:|---:|---:|
|keyword|1.0|0.7541666667|0.002000|
|vector|1.0|1.0|0.509750|
|hybrid|1.0|0.9166666667|0.509750|

向量与混合耗时分别包含独立query嵌入、SQLite候选/余弦或FTS/RRF。中文transport同义和energy/signal中英混合预定语义检查均通过；17片段16种正文去重、来源删除、Mission隔离、重启、有限单位1024维均通过。准备9.125秒、建立索引3.156秒、脚本总31.047秒；工作器树RSS峰值3720794112字节（约3.47GiB），8×600满批峰值3807604736字节（约3.55GiB），token复验峰值3752095744字节。阈值6442450944字节=6GiB，每0.1秒抽样监测，**不是OS硬上限**；不是完整Electron应用内存。

SQLite建立向量前122880字节，最终196608字节包括事实与FTS表；删除一条来源后实际16条向量BLOB合计65536字节。不能将数据库总大小称纯向量索引大小。三通道Recall相同，MRR排序不同；这是8个固定问题的单次观察，无统计置信区间或普遍收益声明。未实际跑满4096段全库长期负载，满额/并发/版本预算由有意义fixture及真实SQLite边界验证；未验收GPU、其它系统、独立Windows、人工原生流程、发布运行时/安装包。引用结构与身份校验不保证原文语义真实；相似度与缓存不能当执行完成事实。保留原LangGraph弃用提示，本轮未升级其版本。L4评估：已跑相关文档/删除/角色配置回归48项及真实模型/资源/L3，不涉及发布或新的文件副作用，因此不重复与本模块无关的全量/打包验收。

最终审查与文档：固定接口/严格输入、普通路径与六文件摘要、准确SQL来源范围、模型/内容签名、空scope、512/4096片段、150来源、32KiB输出、600码点/1024tokens、30/120/180/900秒期限、epoch晚到写入、FK删除与会话purge、取消与工作器树回收均有实现及相关证据。模块README、根/backend/desktop README、ARCHITECTURE、DEVELOPMENT_PLAN、V4状态与本PROGRESS已更新。提交前检查git status、git diff、git diff --cached与diff --check，仅显式选择当前004的38个文件；预存.zcodeignore/docs/INTERVIEW.md、权重/私有配置/数据库/日志/测试产物不纳入。最终hygiene-working.json/hygiene-staged.json记录真实Key/私钥/禁入文件/测试产物/资源manifest检查，最终实际工作树与cached审计各38文件；工作树298个产物文件，首次cached审计298个，新增审计报告后最后cached审计299个；禁入路径、真实Key命中、私钥块、产物Key命中、资源manifest差异均0，仅记录凭据是否存在，不输出值。git diff为空（无未暂存的模块修改），cached diff --check通过；两个用户预存文件仍未跟踪、不读取或暂存。

交付独立正常本地commit标题 `feat(V4-004): add verified local embeddings and scoped hybrid retrieval`；完整hash可用 `git log -1`核对，提交回执另外保存于忽略的证据目录，未amend既有002/001。所有本地提交仍待用户手动push，无Release或安装包重建。试用`npm start`→添加明确选择的资料→设置→本地混合检索→加载此前模型（或原生选择该固定目录）→选择会话→建立当前资料索引→检索关联资料；清除会话向量保留原文/FTS/原文件，缺模型明确关键词降级。

**停止点**：完成V4-004验证/记录/独立提交后依用户最新指令暂停Goal，待用户指令继续V4-003。未开始后续模块；原完整Goal不标完成。

## V4-003：五轮上下文与自动长期记忆（2026-10-07）

用户“继续目标”解除004后暂停，从003恢复原连续Goal順序，完成当前模块实际验证、文档、审计、独立本地commit后自动继续005；不push、发布或重建安装包。预检目录正确，main/remote HEAD origin/main，历史004=757fefc、002=c1ca871、001=a6c9d30；工作区仅预存.zcodeignore与docs/INTERVIEW.md未跟踪，保留、不读取或暂存，004不重复实施/下载。主Agent拥有聊天/Application/删除接入、文档和验证；memory_core独占新memory目录与test_v4_memory.py；memory_desktop独占4个新desktop文件和目标unit测试，禁止并发修改、提前开发后续或传递凭据。

当前目标：精确request_id轮次绑定、最近5个已结束请求轮与当前待结束状态；工具/澄清不占新轮，失败/取消/中断不压缩为成功。SQLite保存版本化候选、批准批次、摘要、长期记忆与来源/撤回；本地发现偏好/人物/项目候选不调用模型，Main整理前准确批次/固定模型/用途/费用原生确认。跨会话检索仅本地，不自动授予正文外发或文件权限。预算raw24KiB/轮4KiB/消息2KiB，较早摘要每批10轮，候选64/会话、记忆512全库，模型30秒/1024输出token/零重试；实际字段随源码与验证更新。现有依赖足够，不为未来模块安装工具。

- [x] √ 实际实现与代码审查。
- [x] √ L0类型/语法、L1轮次/预算/来源/模型结果，L2接口/删除/固定Main/原权限相关回归，L3真实Electron本地候选/原生取消/批准mock/重启/纠正忘记；真实模型与mock分开记录，默认不调用真实模型。
- [x] √ 模块与项目文档、V4/开发清单/PROGRESS；独立正常本地commit标题及敏感审计回执见下文与Git历史。

所有报告放artifacts/test-results/V4-003/并保持Git忽略。实现由主Agent整合；子Agent交接后仅只读审查，没有并发编辑。最终新增memory七表（含FTS5及无正文memory_attempts），请求精确归属、五个完整终态轮及当前未结束/失败事实接入普通回答、路由与旧规划器；跨会话记忆不自动进入云请求。本地明确中文候选、准确冻结预览、固定Main 30秒/1024token一次整理、逐字来源与候选身份校验、冲突、纠正、忘记、资料撤回和既有会话purge均实现。忘记保留原始消息、抑制该派生身份且清摘要/预览正文；纠正保存明确用户来源，不计新模型轮。来源确认不证明客观真假。

审查修复：长期支持按精确来源点查，不因1000消息窗口截断被撤销；窗口外请求最多补一对用户/助手，同文旧请求不猜测。独立调用账本网络前事务写running；正文缓存最多20份，账本最多128次/会话，淘汰/纠正/忘记不删除调用事实，启动未知转interrupted，同revision不重发，满额拒绝新调用。选批同时按实际发送24KiB及完整预览32KiB计算，旧摘要重复支持仍计预算，容不下返回MEMORY_BUDGET而非空内容。摘要12条/12KiB、候选64/会话、记忆512全库、长期来源128/会话、单记忆8支持、列表各20/32KiB及搜索10/16KiB有界。Memory Context声明式组合仍明确未就绪，待006接入；不以002框架注册占位冒充组合业务完成。

实际命令（均在项目根；Main mock，无真实云调用）：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_memory.py -q --basetemp=artifacts/test-results/V4-003/core-accept-data --junitxml=artifacts/test-results/V4-003/core-accept.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_chat.py backend/tests/test_m20_natural.py backend/tests/test_v3_management.py backend/tests/test_m15_synthesis.py backend/tests/test_v4_retrieval_protocol.py backend/tests/test_application.py -q --basetemp=artifacts/test-results/V4-003/regression-data --junitxml=artifacts/test-results/V4-003/regression.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m20_natural.py::test_three_materials_limit_and_removed_source_never_sent backend/tests/test_v4_memory_protocol.py -q --basetemp=artifacts/test-results/V4-003/regression-recheck-data --junitxml=artifacts/test-results/V4-003/regression-recheck.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_memory.py backend/tests/test_v4_memory_protocol.py -q --basetemp=artifacts/test-results/V4-003/ledger-data --junitxml=artifacts/test-results/V4-003/ledger.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_memory.py -k cross_chat_conflict -q --basetemp=artifacts/test-results/V4-003/forget-ledger-data --junitxml=artifacts/test-results/V4-003/forget-ledger.xml
backend/.venv/Scripts/python.exe -X utf8 -m compileall -q backend/src/orvia_backend/memory backend/src/orvia_backend/chat backend/src/orvia_backend/application.py
npx vitest run apps/desktop/tests/v4-memory.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V4-003/desktop-memory-unit.json
npm run check
npm run build
$env:ORVIA_TEST_MODULE='V4-003'
npx playwright test tests/e2e/v4-memory.spec.ts
```

|级别|实际结果/证据|性质与闭合|
|---|---|---|
|L0|compileall、npm run check、npm run build、git diff --check通过|TypeScript首次Zod泛型返回丢失导致implicit any，保留诊断，修正显式ZodEffects<T>后通过；build含类型检查，不打安装包|
|L1核心|core-accept.xml22通过，审查新增5项后ledger.xml核心27＋协议3共30通过，forget-ledger.xml最小1通过|真实SQLite/FTS、合成来源，固定Main mock；早期15通过2失败已最小修复复验，后续21/支持3/窗口3通过均保留历史|
|L2协议/回归|regression.xml64通过1失败；regression-recheck.xml4通过（失败项1＋协议3）；ledger.xml协议3通过|撤回来源已安全拒绝，但新检索返回SOURCE_UNAVAILABLE与旧STALE_APPROVAL契约不同，统一审批失效后最小通过；协议首次2失败含路由authored结构及测试错误error.code层级，已修正|
|L1桌面|desktop-memory-unit.json8通过|严格输入、Unicode码点/字节、取消零调用、旧完整预览变更、失败不重发、忘记取消/修正失效；原生dialog模拟|
|L3|e2e.json1通过/11.9秒，账本修复后重复同一相关流程1通过/11.9秒|真实Electron–Python/SQLite；6寒暄0调用→合成候选路由/回答2mock→取消0增量→批准整理1mock→重启/跨会话/纠正/忘记无额外云调用。初次fixture错误message_count字段失败保存e2e-first-fixture-failed.json，改为真实messages投影后通过|

JUnit按(classname,name)最终结果去重：**95个不同后端用例通过，未解决失败/跳过0**（27核心＋3协议＋65相关回归），verification-final.json记录归属，8桌面契约＋1不同Electron流程。截图electron-1Fu2VF/approved.png、forgotten.png及最终electron-Dp6xRL/approved.png已实际查看：中文状态、摘要/记忆来源、纠正/忘记与本地搜索可读，纵向滚动，无横向溢出。曾误读不存在旧fixture截图路径仅工具查找失败，不改变测试结果。没有真实Main整理、人工原生/独立Windows、安装包验收；没有新工具、依赖或模型下载。复用004固定模型/依赖，不重装。

L4评估：此次改变聊天上下文/删除派生数据，已执行65项相关权限/聊天/资料/删除/协议回归及真实Electron流程；没有发布或新的文件执行副作用，因此不重复无关全量/打包。有限中文候选和敏感规则不能保证识别任意表达/凭据；准确发送仍须用户审查。严格逐字摘录较抽象摘要更保守，摘要或来源预算用尽必须新建会话，不能静默丢旧事实。跨会话为FTS5/jieba，无记忆全量向量化；混合资料检索仍属于004。保留LangGraph原有弃用提示。

提交前检查git status/git diff/git diff --cached及敏感扫描；实际回执hygiene-working.json/hygiene-staged.json和commit-receipt.json保存在忽略目录，统计不读取预存.zcodeignore/docs/INTERVIEW.md。显式选择003文件，排除真实凭据、数据库、日志、测试产物/权重/用户文件，不amend前模块。独立正常本地提交标题 `feat(V4-003): add five-round context and approved source-backed memory`，实际hash见Git历史/回执（避免自引用改变提交）；仍待用户手动push，无Release或安装包重建。

试用：npm start→合成会话“我的偏好是简洁回答”→设置→记忆与上下文→选会话/准备预览→核对instructions和实际input→原生批准；本地查询命中后查看来源会话可纠正/忘记。完成003独立提交后按继续目标自动进入005，不恢复历史暂停。


## V4-005：实体关系与知识图谱（2026-10-07）

V4-003已实际交付独立本地commit **9bd8864**；003最终95个不同后端/8桌面/1Electron通过，无真实云调用，工作树仅预存两个文件。按“继续目标”自动继续005，未开始006。主Agent接入Application/删除/现有IPC、审查/E2E/文档/提交；graph_core独占graph目录及test_v4_graph.py，graph_desktop独占4个新增graph桌面文件，禁止并发修改或传递凭据。

设计：SQLite保存来源/全文版本绑定的人物、项目和文件实体、固定方向类型的关系与支持；来源身份不同或同名不自动合并。本地查询歧义须显式选择entity_id，向前至多两跳、固定预算，不生成SQL、不将关系路径当现实执行事实。Main抽取逐批准确原文/供应商/用途/费用原生确认；关系须程序核验中文明确模板和方向，只有名字在原文不够证明关系。矛盾保留conflict，撤回/删除撤销支持。沿用项目依赖，无新安装/模型下载。模型mock、真实SQLite和实际Electron分开记录，产物仅artifacts/test-results/V4-005/。

- [x] √ 实际实体/关系/证据持久化、准确批准/校验、歧义/冲突/至多两跳/来源撤回和会话purge。
- [x] √ L0契约/类型/语法，L1核心来源/方向/预算/未知不重发，L2固定接口/聊天删除/相关回归，L3实际Electron批准取消/提取/本地查询/重启；L4评估。
- [x] √ README/架构/开发清单/V4/进度、独立正常本地commit标题与敏感回执见下文/Git历史；提交前不进入006。

实际实现：GraphService独立于既有MissionGraph，仅用SQLite已存明确用户原文和当前ready资料。实体person/project/file和四种固定方向关系绑定cid+origin+完整原文版本+kind+name；同来源不同unit可共享身份，不同来源或会话同名不合并。Graph Source保存准确quote、定位和全文hash，资料全部unit正文参与版本；显式敏感内容全文过滤。候选、列表、预览、query不发云；Main准确原生批次批准后30秒/1536token一次调用，额外字段、陌生来源、错误方向、不支持类型或非完整独立模板句拒绝。最终事务再核对会话未删除/ready关联/全文版本与关系句，截断之外否定后缀也不能绕过校验。

审查修复与决策：子串关系校验收紧为独立完整句，仅有限固定“解释，”前缀；否定/条件/可能/计划/姓名后缀/短项目名拒绝，包括模型将“如果/不是”伪装作人物名字。对已批准来源中互斥负责人检查覆盖，遗漏另一位或空arrays拒绝整批并不消费source；完整双方保留conflict并阻止路径，不用模型省略掩盖冲突。graph_processed无正文(cid,source_id,version)128项成功来源处理事实使后批接续，实际20来源按16+4批次、缓存清理/重新初始化通过；不是保证全文完整抽取。graph_attempts128次独立调用事实网络前running，成功同事务completed、失败failed，启动interrupted；20份预览淘汰不准重发。来源撤回清其processed和正文缓存，撤回标识保留；chatpurge六表同事务删除，删除journal先禁止支持，即使原文还在也query0。

预算：来源发现最多3资料/每文档前50unit/最近128明确用户消息；片段2048UTF8字节、每批16、实际发送24KiB/预览32KiB，任何截断可见。实体512/全库、关系1024/全库、8来源/条、128有效支持来源/会话；list每类20/32KiB。query本地精确/有界名字包含，歧义最多20候选不生成路径；选准确identity后只读同cid+origin+version最多512边，前向两跳、20路径/32KiB，visited排除环/撤回/冲突。其它会话512条边不挤掉当前scope路径有目标实测，数量和字节上限先到者有效。固定失败协议MISSING_CREDENTIAL/MODEL_TIMEOUT，不泄漏供应商响应、不给未知结果鼓励重试；本地query仍可用。

实际主Agent验证命令（根目录；产物前缀artifacts/test-results/V4-005/，Main mock或缺凭据0真实调用）：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_graph_protocol.py backend/tests/test_application.py backend/tests/test_v3_management.py backend/tests/test_v4_memory_protocol.py backend/tests/test_v4_retrieval_protocol.py backend/tests/test_m20_natural.py::test_three_materials_limit_and_removed_source_never_sent -q --basetemp=artifacts/test-results/V4-005/integration-data --junitxml=artifacts/test-results/V4-005/integration.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_graph_protocol.py -q --basetemp=artifacts/test-results/V4-005/integration-recheck-data --junitxml=artifacts/test-results/V4-005/integration-recheck.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_graph_protocol.py -k model_failure -q --basetemp=artifacts/test-results/V4-005/error-contract-data --junitxml=artifacts/test-results/V4-005/error-contract.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_graph.py backend/tests/test_v4_graph_protocol.py -q --basetemp=artifacts/test-results/V4-005/final-core-data --junitxml=artifacts/test-results/V4-005/final-core.xml
backend/.venv/Scripts/python.exe -X utf8 -m compileall -q backend/src/orvia_backend/graph backend/src/orvia_backend/application.py backend/src/orvia_backend/chat/coordinator.py backend/src/orvia_backend/chat/management.py
npx vitest run apps/desktop/tests/v4-graph.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V4-005/desktop-graph-unit.json
npm run check
npm run build
$env:ORVIA_TEST_MODULE='V4-005'
npx playwright test tests/e2e/v4-graph.spec.ts
```

|级别|结果/证据|性质/闭合|
|---|---|---|
|L0|npm run check/build、compileall、git diff --check通过|无新依赖/安装/模型下载；build非安装包|
|L1核心|最后43核心通过；此前37完整＋coverage/scope3＋prefix14含2新增＋empty_conflict1去重43，精确子Agent命令见模块README|真实SQLite合成原文，Main mock；预算fixture曾错误要求恰好20路径，实际32KiB先截断约10，改为有效1～20/字节/truncated并最小复验，不把数量上限当必达数|
|L2|integration.xml27通过含3图谱协议＋24相关回归，新增processed后协议3复验通过，error-contract.xml新增2通过；final-core.xml核心43＋协议5共48通过|真实Application/SQLite、准确预览/固定Main mock、来源移除/原文保留、六表purge、私有字段/SQL/三跳/bool拒绝、缺Key/超时后零第二调用；复用仍有效的相关回归，不重复无关项|
|L1桌面|desktop-graph-unit.json9通过|Unicode/实际字节、身份/版本/方向、歧义无路径、额外字段拒绝、原生取消0、旧完整正文失效、unknown一次性许可、clear失效；dialog模拟|
|L3|首次1通过/12.2秒，边界/processed后1通过/12.2秒，最终scope/冲突修复后1通过/12.5秒，均同一个流程|真实Electron–Python/SQLite；Main HTTP替身与原生确认模拟。合成解释→取消0增量→批准1固定Main mock→4实体/3边→人到项目到依赖项目2路径→重启→另一会话同名2identity/0path→明确选择1identity/2path→删除原会话后仅剩1identity/2path。查询/选择/删除不增模型调用|

最终JUnit按(classname,name)去重 **72个不同后端用例通过，未解决失败/跳过0**（43核心＋5协议＋24相关回归），verification-final.json列归属；9桌面契约＋1不同Electron流程。首次e2e-before-boundary-fix.json保留，不将重复执行计新流程。two-hop.png/after-delete.png（electron-IlHCMr）已实际查看，中文实体、1/2跳、有向箭头、来源详情和结果均可读，无横向溢出。最终截图目录可从e2e.json/证据目录核对。未真实调用Main、未人工原生/独立Windows/安装包验证；没有新工具、依赖或模型。

L4评估：图谱是新派生服务，无新文件执行、网络服务或发布变更；已跑24项相关Application/资料移除/会话删除/003/004接口回归，加核心实际SQLite和真实Electron，复用003/004仍有效证据，不扩展无关全量或重建包。有限模板及名字匹配不能提供通用自然语言抽取/语义推理，人物前缀过滤可能保守误拒特殊姓名；只处理前2KiB片段/指定发现范围，truncated或空结果不说明全文完整理解。跨来源身份不自动归并，冲突撤一方后仍保守conflict，须新来源版本批准；图谱为资料内证据关系，不保证现实真伪。敏感规则有限，准确正文必须用户审查。保留LangGraph原弃用提示。

所有权已由两个子Agent交回；另一个只读审查发现模型遗漏矛盾负责人问题，主Agent整合修复与复验，不曾并发改同文件。根/backend/desktop README、graph README、架构、开发清单/V4/本进度已更新。提交前git status/diff/cached、敏感/禁入审计真实回执hygiene-working.json/hygiene-staged.json及commit-receipt.json在忽略目录；显式选择005文件，排除预存两个文件、密钥、DB、日志/测试产物/模型和用户文件。独立正常本地commit标题 `feat(V4-005): add source-verified entities and bounded relationship queries`，实际hash见Git历史/回执；不amend、不push、不Release或重建安装包。

试用npm start→发送合成明确关系原文→设置→实体关系与知识图谱→选会话→准备准确预览→原生批准；查询姓名/项目，歧义时选身份，最多两跳查看原文。当前模块实际交付后自动进入006，后续未完成不将完整Goal标完成。


## V4-006：Query Rewrite / Memory Context Skill（2026-10-07开始，10-08交付）

005已完成实际验证/审计/独立本地commit **acd22ee**（72个不同后端、9桌面、1Electron）；工作树保留预存.zcodeignore/docs/INTERVIEW.md，未读取或暂存。按原Goal连续顺序进入006，不开始007。rewrite_core独占新rewrite目录/核心测试及现有Skills backend service/README，rewrite_desktop独占4个新rewrite桌面文件；主Agent拥有Application、现有IPC与Skills桌面接入、删除/文档/集成和提交。

设计：保留原问题，最多3个经过程序校验的检索表达，来源仅明确选择的本地记忆和当前cid ready资料片段，准确scope冻结；Main生成另经准确原生批次批准，候选不能改变动作/新增条件/扩大资料权限。有限明确代词消解和固定同义字典拒绝无来源的新约束，多主题歧义需减小选择。取消/缺Key/超时/结构失败清楚使用原查询，original始终参与精确同scope检索；检索回查支持/版本并按来源去重。SQLite保留批准预览、无正文尝试、校验的改写/历史，缓存不授权重发。

Skills改为真实声明式本地适配，不以enabled占位冒充完成。Memory Context仅本地投影，Query Rewrite只消费已校验改写事实/本地检索；ImportedWorkflow不暗中调用Main。只有全部leaf为本地业务才允许无文件grant，涉及文件的计划和逐叶执行仍受原ComputerGateway/目录/正文权限；不会创建fakegrant。原生工作流计划确认与改写上云确认分别保留。复用003/004能力与依赖，无新增安装或模型下载。

- [x] √ 实际候选/审批/fallback/原查询保留/scope/来源校验与真实声明式组合。
- [x] √ L0类型/契约、L1边界/同义/代词/歧义、L2实际SQLite检索/Skills/删除/相关回归及固定合成集原查询对照，L3真实Electron；mock/真实组件分别记录，L4评估。
- [x] √ 模块/根/架构/开发清单/V4/进度、敏感审计及独立正常本地commit标题/回执见下文和Git；不提前007。

报告只放artifacts/test-results/V4-006/并Git忽略，完成证据不成立前不标完成。


006实际实现与设计：固定RewriteService.preview/generate/search/history；SQLite三表记录准确批准包、无正文128次尝试及最近32成功/失败记录（历史展示20）。预览20份、实际input＋instructions24KiB/完整32KiB，原问题1～200字、选有效记忆最多3、ready资料最多3/150source/512片段。资料/记忆原文及范围签名在预览保存、网络前、最终提交事务和检索回查重核，跨会话支持先核source cid删除墓碑；被删会话晚到不得再写正文。固定Main仅30秒/1024token一次，没有Key/超时/错误JSON/引用或候选校验失败用原问题和明确原因，同revision不重发，缓存淘汰不恢复许可。纯本地search/clarification不是已批准模型改写，不进入调用历史。

程序有限白名单：费用→成本/经费、计划→方案、预算→经费、进度→进展；明确问题前缀的项目/人物代词由唯一选中有效来源替换，复杂/多主题消歧而不猜测。修复“其他费用/吉他费用”子串误替换，明确指代外保留原文。新操作、数值、否定、URL/路径/自由新增条件不接纳。search原问题永远queries[0]，最多再3候选、最多5命中/32KiB，按source/定位/hash去重；超过5、正文超预算均truncated。独立检索180秒含最多4表达/源回查/撤回原查询回退，沿用004单嵌入预算及关键词降级，不额外加载或下载模型。

Memory Context/Query Rewrite现为内置1.1.0真实LangGraph组合，固定memory_context/query_rewrite本地闭包分发；旧内置迁移保留禁用并失效旧计划。Query Rewrite required revision空串明确只用原问题，sha64只消费另行准确原生批准的同问题事实，不自动调用Main。只有展开后全部本地leaf可grant_id=None；含文件leaf必须真实grant且原Gateway逐叶检查。每叶data8KiB投影，超限明确limited并停止后续，原10秒组合预算保留。真实会话选择及独立计划原生确认不等于云生成批准。会话purge三表＋skills_executions，所有grant计划核删除墓碑，任一本地leaf再核chat存活；真实目录grant也不能恢复被删除会话正文。两个删除竞态由只读审查发现、主Agent修复与实际SQLite复验，没有并发编辑。

实际验证命令（项目根；全部Main mock/缺Key，零真实云；产物前缀artifacts/test-results/V4-006/）：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_rewrite.py -q --basetemp=artifacts/test-results/V4-006/rewrite-final-data --junitxml=artifacts/test-results/V4-006/rewrite-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_rewrite.py backend/tests/test_v4_rewrite_protocol.py backend/tests/test_v4_skills.py backend/tests/test_v4_skills_protocol.py backend/tests/test_v3_management.py backend/tests/test_application.py backend/tests/test_v4_memory_protocol.py backend/tests/test_v4_graph_protocol.py backend/tests/test_v4_retrieval_protocol.py -q --basetemp=artifacts/test-results/V4-006/accept-data --junitxml=artifacts/test-results/V4-006/accept.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_rewrite_protocol.py -k cross_session_memory_pending -q --basetemp=artifacts/test-results/V4-006/cross-purge-data --junitxml=artifacts/test-results/V4-006/cross-purge.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_rewrite_protocol.py backend/tests/test_v4_skills.py backend/tests/test_v4_skills_protocol.py -q --basetemp=artifacts/test-results/V4-006/final-boundary-data --junitxml=artifacts/test-results/V4-006/final-boundary.xml
backend/.venv/Scripts/python.exe -X utf8 -m compileall -q backend/src/orvia_backend/rewrite backend/src/orvia_backend/skills backend/src/orvia_backend/application.py backend/src/orvia_backend/chat/management.py
npx vitest run apps/desktop/tests/v4-rewrite.test.ts apps/desktop/tests/v4-local-skills.test.ts apps/desktop/tests/v4-skills.test.ts apps/desktop/tests/v4-memory.test.ts apps/desktop/tests/v4-graph.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V4-006/desktop-final.json
npm run check
npm run build
$env:ORVIA_TEST_MODULE='V4-006'
npx playwright test tests/e2e/v4-rewrite.spec.ts
```

|级别|结果与证据|真实性/修复记录|
|---|---|---|
|L0|check/build、compileall/diffcheck通过|无新工具/依赖/模型；build不是安装包|
|L1/L2核心|21不同rewrite目标通过（rewrite-final.xml15、skills-approved新增1、rewrite-races新增4、skills-purge新增1）|真实SQLite/FTS/LangGraph，Main mock；最初13setuperror为basetemp父目录缺失，随后12pass1fixturefail已修，历史保留|
|L2协议/相关|accept.xml104pass1skip；删除来源/非空grant修复后final-boundary.xml57pass1skip包含8rewrite协议＋49旧Skills通过项|真实Application/SQLite/ComputerGateway合成目录；符号链接因本机普通权限不可创建skip，实际Windows目录联接拒绝用例通过。旧available占位期望1改实际3后通过|
|L1桌面|desktop-final.json31通过（改写9＋本地Skills3＋旧Skills2＋memory8＋graph9）|严格输入/Unicode/实际字节/完整scope变更/取消0/窗口异常/unknown单次许可、local无目录grant/文件拒绝、相关投影接口回归，dialog模拟|
|L3|e2e.json1通过/11.3秒测试（总12.1秒），electron-pIqbRN/acceptance.json|实际Electron–Python/SQLite、原生显式合成DOCX本地解析→产品记忆批准保存→准确改写取消0/批准1mock→原问题＋候选FTS命中120万元→重启历史→资料撤回仅原query空hits→真实本地QueryRewrite两叶无folder/无额外云。Main HTTP/native dialogs模拟|

最终JUnit(classname,name)去重 **106个不同后端通过、未解决失败0、权限skip1**，verification-final.json列归属；31桌面＋1不同Electron流程。固定3合成主题真实FTS原/改写Recall@5都1.0（rewrite-recall.json），不宣称召回提升或通用语义质量；复用004真实固定嵌入模型结论，没有重新加载资源回归或下载。

Electron第一次设置页本地投影并发互拒导致记忆未显示，修为memory-list/context、graph-list、rewrite-history有界本地读取允许并发，其余审批/执行仍串行；第二/三次输入可访问名称含选项/正文导致精确locator失败，补显式aria-label后整个真实流程通过，三个失败报告保留。approved-search.png与local-skills-after-withdrawal.png已实际查看：中文原问题/候选/片段及只读两步事实清晰，无横向溢出；技术字段在详情。没有人工原生、真实Main/费用、独立Windows或安装包验收。

L4评估：新增只读派生服务/本地Skills会话归属，无新文件执行/外部服务/发布；已跑77项通过相关后端及1权限skip、相关19桌面回归和实际Electron，复用003～005仍有效结果，不重复无关全量或打包。限制：有限同义词与明确前缀代词，任意文件名指代当前澄清；三主题评估太小且持平，不承诺提高召回。敏感检测有限，准确发送仍须用户审查；scope/字节/片段超限拒绝或可见截断，组合10秒可能早于独立检索完成并保留unknown，不自动重试。

已更新模块/Skills/root/backend/desktop README、架构、开发清单/V4/进度；提交前git status、diff、cached及敏感/禁入检查，回执hygiene-working.json/hygiene-staged.json/commit-receipt.json在忽略目录。显式选择006文件，不读取或暂存预存.zcodeignore/docs/INTERVIEW.md，不收Key、数据库、日志/产物/模型/用户文件；独立正常本地commit标题`feat(V4-006): approve bounded query rewrites and run local context skills`，hash见Git历史/回执，不amend、不push、不Release/重建包。006提交完成后按最新继续目标自动进入007。

试用npm start→添加合成资料→记忆入口保存“我的项目是合成航线”有效记忆→查询改写选会话/原问题“它的费用”/勾当前项目→预览全部正文→原生批准→本地原问题＋候选；或直接原问题。Skills选Query Rewrite→本机会话→inputs包含query和revision空串→原生计划确认；没有暗中生成模型请求。


## V4-007：MCP只读工具扩展（2026-10-08交付）

006已实际交付独立commit **c9e3074**：106不同后端通过/1Windows符号链接权限skip、31桌面、1Electron，working/staged36文件敏感审计0，仍保留预存两个文件。按继续目标进入007，不开始008。rewrite_core独占新mcp transport/protocol/schema及transport目标测试/合成服务fixtures；graph_core独占mcp service/__init__/README及服务目标测试；rewrite_desktop独占新mcp桌面contracts/ipc/credentials/Panel/test；主Agent负责现有接入/生命周期/删除/集成与E2E/审查/文档提交，不共享文件编辑。

锁定方案引用的MCP2025-06-18有限只读子集，现有httpx0.28.1/psutil7.2.2/ctypes/SQLite足够，暂不装SDK或第三方服务器。原生选择准确配置json→准确程序/参数/HTTPSendpoint连接确认→固定initialize+工具分页→工具schema/用户逐项允许清单原生审查→每调用准确参数/body版本原生确认。允许清单/名称读取前缀与危险名称规则是客户端限制，服务器readOnlyHint不证明无副作用；本地普通账户程序非LPAC。程序及已有fileargs身份hash变化拒旧许可，不能保证所有隐式依赖。stdio挂起先入Windows Job再resume，真实子进程回收验证；HTTPS TLS验证、无env代理/redirect/OAuth/URI跟随，POST JSON/SSE和session/version处理，不断线重试或恢复旧许可。

独立MCP凭据只主进程safeStorage加密与当前后端内存，系统加密不可用则拒保存，无开发明文回退，不复用角色Key或在配置/env声明。匿名服务无需凭据。最多5服务/16允许工具/32发现工具/8页；配置16KiB、args8KiB、wire64KiB/result32KiB、connect30秒/call20秒、每cid128尝试/32记录展示16，具体最终接口预算以实现和验证修正。服务器主动sampling/roots/elicitation/执行请求拒绝，输出不成为授权或完成依据。

官方核对：https://modelcontextprotocol.io/specification/2025-06-18/basic/transports 、basic/lifecycle及server/tools；明确支持冻结版本，不声称2026新版任意服务兼容。真实stdio/TLS合成服务（既有OpenSSL合成测试证书，TestCA只构造注入）与HTTPmock/defaultzero云分别记录。仅artifacts/test-results/V4-007/，Git忽略。

- [x] √ 实际两种传输、配置/工具审查、固定参数/结果校验、调用事实、取消/断线/身份变化/关闭回收与凭据隔离。
- [x] √ L0～L3实际证据/中文README和清单/PROGRESS、敏感审计及独立正常本地commit标题/回执见下文与Git，不提前008。

007实现：固定MCP2025-06-18，原生单选JSON/准确配置登记、准确程序或endpoint连接、完整工具清单和每次JSON参数四种确认相互独立。生产httpx TLS=True、trust_env=False、无redirect/OAuth；准确canonical ASCII HTTPS无userinfo/query/#，session/version绑定POST JSON/SSE，DELETE有限3秒，405明确closed=false而本地client实际关闭。stdio普通账户CreateProcess挂起先入kill-on-close Job后resume，继承pipe句柄白名单、干净env不继承角色Key/token/个人变量；普通CreateProcess后代和breakaway flag用例均实际随Job回收。服务器sampling/roots/elicitation等主动请求拒绝，URI/指令/代码只显示文本，不安装或执行。

配置5/允许工具16/发现32工具8页/预览20份；配置16KiB、参数8KiB、wire64KiB/depth24/每对象数组128、结果完整事实32KiB。schema depth6/字段32/数组64/字符串8000、有限安全数字/enum/default/范围，未知约束/$ref/regex/组合拒绝并显示被阻止，不忽略后调用。每次发现重核全部元数据（含schema/hint）与session，名单不能证明无副作用。程序/已有fileargs单256MiB/合512MiB SHA/目录10秒，隐式依赖未覆盖。连接30秒、单请求20秒、完整call60秒包括前后发现；无重连/重试/GET流恢复。不可取消的原生CreateProcess清理须等同步调用返回并回收后到Job，极端迟滞可超协议预算，不能假称已回收。

SQLite四表：全局mcp_servers/mcp_tool_reviews（最多20/服务）保存配置和审查事实；会话mcp_attempts128次不淘汰无正文尝试、mcp_executions最近32完整结果/历史16或32KiB。网络前running，收到有效响应与isError/failed/limited/unknown区别；超时/取消/断线未知清连接许可且不重发。每次最终事务检查cid存在及删除墓碑，purge同事务清会话两表，全局配置保留，迟到不重建。启动工具批准expired、running→unknown但不自动连接。主进程一次性许可缓存清理不能恢复调用资格。

专用HTTPS Bearer只独立safeStorage加密文件及私有Initialize.mcp_credentials/credential_replace后端内存；没有开发明文fallback，不读.env或复用模型Key。加密不可用拒保存，损坏文件锁定保留；无凭据匿名可用。更新先断连并撤销旧epoch、连接进行中也不能发布旧凭据会话。程序metadata/原始str/key递归检测当前令牌回显（引号/反斜杠转义不能绕过），异常不保留远端正文/凭据。初始化同样限制5UUID及单行ASCII4096字节，不把无效私有输入回显。

实际命令（根目录，报告均artifacts/test-results/V4-007/；默认零模型，全部合成）：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp_transport.py -q --basetemp=artifacts/test-results/V4-007/transport-accept-data --junitxml=artifacts/test-results/V4-007/transport-accept.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp_transport.py::test_stdio_job_breakaway_is_denied backend/tests/test_v4_mcp_transport.py::test_stdio_stderr_budget_closes_and_reaps backend/tests/test_v4_mcp_transport.py::test_endpoint_exact_identity_no_normalization backend/tests/test_v4_mcp_transport.py::test_stdio_real_initialization_pages_call_and_clean_environment backend/tests/test_v4_mcp_transport.py::test_real_tls_json_sse_version_headers_pages_and_delete -q --basetemp=artifacts/test-results/V4-007/transport-extra-data --junitxml=artifacts/test-results/V4-007/transport-extra.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp_transport.py -k 'schema or json or endpoint or open_object' -q --basetemp=artifacts/test-results/V4-007/transport-schema-data --junitxml=artifacts/test-results/V4-007/transport-schema.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp_transport.py::test_tls_verification_cannot_be_disabled backend/tests/test_v4_mcp_transport.py::test_stdio_isolated_python_mode_state_and_utf8 -q --basetemp=artifacts/test-results/V4-007/transport-final-fixture-data --junitxml=artifacts/test-results/V4-007/transport-final-fixture.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp_transport.py::test_cancelled_native_spawn_retains_and_reaps_real_late_job backend/tests/test_v4_mcp_transport.py::test_stdio_real_initialization_pages_call_and_clean_environment backend/tests/test_v4_mcp_transport.py::test_stdio_malicious_or_disconnected_closes_tree -q --basetemp=artifacts/test-results/V4-007/spawn-final-data --junitxml=artifacts/test-results/V4-007/spawn-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp.py -q --basetemp=artifacts/test-results/V4-007/service-accept-data --junitxml=artifacts/test-results/V4-007/service-accept.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp.py::test_remote_echo_of_private_credential_never_saved_or_returned -q --basetemp=artifacts/test-results/V4-007/service-echo-data --junitxml=artifacts/test-results/V4-007/service-echo.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp.py::test_discovery_budget_rejects_cursor_cycles_and_incomplete_catalogues backend/tests/test_v4_mcp.py::test_invalid_mcp_content_metadata_does_not_become_completed_evidence backend/tests/test_v4_mcp.py::test_actual_sqlite_single_approved_call_and_no_implicit_calls_on_open backend/tests/test_v4_mcp.py::test_real_service_stdio_pages_schema_call_and_child_reaping backend/tests/test_v4_mcp.py::test_real_service_tls_discovery_approval_call_and_private_bearer -q --basetemp=artifacts/test-results/V4-007/service-content-data --junitxml=artifacts/test-results/V4-007/service-content.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp_protocol.py -q --basetemp=artifacts/test-results/V4-007/protocol-data --junitxml=artifacts/test-results/V4-007/protocol.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_application.py backend/tests/test_v4_mcp_protocol.py backend/tests/test_v3_management.py backend/tests/test_v4_memory_protocol.py backend/tests/test_v4_skills_protocol.py -q --basetemp=artifacts/test-results/V4-007/related-data --junitxml=artifacts/test-results/V4-007/related.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp_protocol.py -k invalid_mcp_secret -q --basetemp=artifacts/test-results/V4-007/private-init-ids-data --junitxml=artifacts/test-results/V4-007/private-init-ids.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp_transport.py -k refuses_delete -q --basetemp=artifacts/test-results/V4-007/close-refused-data --junitxml=artifacts/test-results/V4-007/close-refused.xml
backend/.venv/Scripts/python.exe -X utf8 -m compileall -q backend/src/orvia_backend/mcp backend/src/orvia_backend/application.py backend/src/orvia_backend/chat/management.py
npx vitest run apps/desktop/tests/v4-mcp.test.ts apps/desktop/tests/backend.test.ts apps/desktop/tests/credentials.test.ts apps/desktop/tests/v3-management.test.ts apps/desktop/tests/m20-transport.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V4-007/desktop-related.json
npm run check
npm run build
$env:ORVIA_TEST_MODULE='V4-007'
npx playwright test tests/e2e/v4-mcp.spec.ts
```

|级别|实际结果/证据|真实性与闭合|
|---|---|---|
|L0|compileall、check/build、diffcheck通过|构建非安装包，无新工具/依赖/模型|
|L1/L2传输|62不同用例通过：transport-accept47、extra新增6、schema新增4、final-fixture新增2、spawn-final新增2、close-refused新增1；重复不累加|真实Windows Job/stdio、实际本机TLS JSON/SSE、TestCA仅测试SSLContext注入；verifyFalse被拒、生产True拒自签、server主动请求/超预算/Unicode/状态与PID实际检查。早期OpenSSL配置缺失16setupErrors/1超长pytestID失误，修fixture后32pass5fail；SSE event与超时EOF覆盖修复47通过。breakaway子进程可创建但仍在内层Job，改错误期望并实际关闭通过。spawn取消first4pass1因短暂terminated PID仍存在，等待真实exit后8相关通过；失败报告全保留|
|L1/L2服务|57不同通过：service-accept46、echo新增6、content新增5|实际SQLite+合成Session；另真实stdio两页/一次call/父子回收、真实TLS+私有合成Bearer/DELETE。服务初轮31pass1因fixture复用closedSession，最小修正复验通过。60秒budget缩时测试unknown保存/关闭、credentialepoch竞态、转义回显、schema/预算/只读和未知不可重发实际验证|
|L2协议与相关|8MCP协议＋21相关通过，related.xml25及private-init-ids4|真实Application/SQLite/stdio；固定接口拒私有权限/SQL/模型注入，删除两表及迟到保护、私有Initialize重启零连接。复用前模块仍有效结果|
|L1桌面|desktop-related.json59通过：18MCP＋41相关|原生dialogs/加密adapter模拟；准确批准、取消零工具、字段/有限JSON、离线撤回/令牌、safeStorage不可用/损坏保留、unknown一次性许可|
|L3|e2e.json1通过/6.2秒测试/总7秒，electron-VTBwE3/acceptance.json|真实Electron/Python/SQLite/stdio/Job、合成配置/工具/结果。原生单选与确认模拟；取消连接无进程、取消调用0、批准1真实toolcall、写阻止、父子PID消失、重启历史且旧call拒绝。云0|

最终按当前收集名称匹配JUnit并去重 **148不同后端通过、未解决失败/skip0**（62传输＋57服务＋8协议＋21相关），verification-final.json列归属；旧参数ID更名的历史失败单列，不当新用例计数。L3 first失败为chatCreate缺client_request_id测试fixture，second失败为Playwright主进程eval不支持动态import测试fixture，均修测试并最终完整通过；历史失败报告不覆盖。mcp-local-completed.png已实际查看：中文状态、JSON结果、只读/URI限制和会话历史可读，无横向溢出。桌面first1路径转义断言fixture已最小修复，18目标全有通过证据。

L4评估：外部普通用户进程与网络是新增边界，已跑真实双传输/TLS/Job和审批E2E，覆盖身份/超时/取消/凭据/删除，21后端＋41桌面相关回归；复用此前Skills/存储/安全链仍有效结论，不重复无关全量/打包。known限制：stdio非LPAC，children_reaped只证明ownedJob成员，不保证WMI/外部broker派生进程入Job；普通权限恶意程序可副作用，允许清单及hash无法担保隐式依赖。HTTPS关闭是协议接受或不确定，无法验证远端所有资源；不支持任意新版MCP/OAuth/外部schema/压缩/SSE恢复/多媒体。未知不重试，同revision读请求也需新审批上下文。凭据回显保护只检测当前本服务令牌，不保证任意其他秘密检测。未用户真实第三方服务/人工原生/真实模型/独立Windows/安装包验收。

现有httpx0.28.1/psutil7.2.2和OpenSSL3.0.13（仅生成合成本机TLS证书）沿用，无安装依赖/模型。合成测试CA/key.pem在忽略目录不是用户私钥，不入Git。所有权已完整交回，模块/root/backend/desktop README、ARCHITECTURE、DEVELOPMENT_PLAN、V4与PROGRESS更新。提交前git status/diff/cached与真实敏感/禁入审计，working/staged/commit-receipt均在忽略目录；显式选择当前模块，不读取/暂存预存.zcodeignore、docs/INTERVIEW.md，不收DB、Key、日志/测试产物/模型/用户文件。独立正常本地commit标题`feat(V4-007): add approved bounded MCP clients and isolated credentials`，hash见Git/回执，不amend、不push、不Release/重建包。

试用npm start→设置→MCP→原生选择符合模块README的服务JSON→准确配置/连接/工具清单确认→选会话与准确tool/JSON→预览/每次原生批准；关闭或另行确认撤回服务。007独立提交后自动进入008，完整Goal仍未完成。

## V4-008：逐次批准的通用Shell（2026-10-08交付）

007已实际提交 **aacab8d**（148后端/59桌面/1真实Electron；working/staged33文件审计0），工作树只有预存.zcodeignore与docs/INTERVIEW.md，保留不读/暂存。008当前唯一模块，尚未开始009。rewrite_core独占新shell/runtime.py及运行时目标tests/fixtures，graph_core独占shell/service.py/__init__/README及service测试，rewrite_desktop独占shell桌面contracts/ipc/Panel/test；主Agent拥有现有接入、集成/E2E、文档/审查/提交。

环境实际探测：Windows PowerShell5.1.26100.9444、既有用户私有PowerShell7.6.5、Git Bash5.2.26（C:/Program Files/Git/bin/bash.exe，GPLv3+既有工具）；wsl --list --quiet仅docker-desktop，排除Docker系统管理发行版，不替用户改Docker或安装Linux系统。各Shell独立准确路径/version/hash，没有静默切换；需要普通WSL的bash/setsid/kill等能力且Linux进程组回收独立验证，当前无可用普通distro将明确不可用。无需新工具安装。

设计预算：脚本16KiB、完整审批包48KiB、每流stdout/stderr16KiB、timeout1～60秒默认20；显式输入最多3/单10MiB合30MiB，启动前普通文件/hash核验及私有副本；默认独立任务目录，可另原生选准确cwd。产物仅指定最多10个普通leaf名字、单1MiB合2MiB、版本/hash/大小回查，逐文件另原生新保存批准。普通账户非LPAC，不承诺路径/网络隔离、字符串安全或回滚；当前token已提权则拒普通执行。exit0只记录exited，核验条件/截断/产物/回收另记，不能据此完成全任务。未知/超时/取消不重试，Windows Job只证明owned成员，WSL不能仅杀Windows启动器称Linux全回收。

- [x] √ 实际检测、版本批准、运行/有界输出、取消超时/回收、产物核验与独立原生回传。
- [x] √ L0～L3真实已安装环境证据、模块及相关文档/清单，敏感审计及独立正常本地commit回执见下文/Git；随后才进入009。
- [ ] 普通WSL真实执行/独立Linux回收验收，本机缺环境，不以mock或GitBash语法验证冒充。

008实现固定九个私有Shell方法与七个preload入口，主进程才可选择cwd/输入/新保存路径；准确完整审批包括版本/hash/script/inputs/预算/核验，执行前重核同包、普通Token与实际exe。WindowsPowerShell5.1使用私有UTF8 BOM脚本和进程级ExecutionPolicy Bypass，不修改系统策略；PS7/Bash无profile加载，不继承角色Key/proxy/个人env。挂起先入既有kill-on-close Job再resume，原生线程前复核Token/SHA，持续有限排空两流；实际exit259可退出，不误当STILL_ACTIVE。WSL仅明确非root用户，冻结bash/setsid/kill/ps工具身份，nonce/starttime/PGID/SID/gate校验后才释放脚本、独立Linux组回查；拒Docker管理发行版。不增加模型调用/依赖/环境安装。

SQLite shell_attempts先记running/每会话128次不淘汰；shell_executions最近32完整正文、历史10/48KiB。每次最终alive/删除墓碑检查，迟到不重建。restart running→unknown、批准失效、不重放；无账本规范UUID准备目录安全清理，已尝试及非规范未知目录保留。运行/unknown独立账本阻止永久删除，私有正文清理服务先于chat删除journal启动恢复；purge仅私有树无reparse，同事务清两表，原输入/cwd/已回传成品保持。产物SHA/普通文件/nlink/大小复核后逐项新位置另原生确认，独占x+b、fsync读回，旧许可拒重放/覆盖。

审批及输出预算/限制如上；检测单次总25秒、私有IPC95秒用于检测+运行+正常收尾，非硬系统deadline。核验明确stdout包含批准文本和指定产物哈希/大小；未声明条件为not_requested，非零/超时/取消/截断/回收未确认为unknown，exit0只说明进程退出。检测版本64MiB exe hash预算；产物预算不是实际磁盘配额，输入副本也不是权限隔离。

实际命令（根目录；所有报告在artifacts/test-results/V4-008/，仅合成数据；云模型0）：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell_runtime.py -q --basetemp=artifacts/test-results/V4-008/runtime-accept-temp --junitxml=artifacts/test-results/V4-008/runtime-accept.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell_runtime.py -q -k wsl --basetemp=artifacts/test-results/V4-008/runtime-wsl-temp --junitxml=artifacts/test-results/V4-008/runtime-wsl.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell_runtime.py::test_actual_git_bash_wsl_host_syntax_and_control_escaping -q --basetemp=artifacts/test-results/V4-008/runtime-escaping-final-temp --junitxml=artifacts/test-results/V4-008/runtime-escaping-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell.py -k 'not real_service' -q --basetemp=artifacts/test-results/V4-008/service-final-data --junitxml=artifacts/test-results/V4-008/service-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell.py -k real_service -q --basetemp=artifacts/test-results/V4-008/service-real-data --junitxml=artifacts/test-results/V4-008/service-real.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell.py::test_preparation_rejects_invalid_limits_without_start -q --basetemp=artifacts/test-results/V4-008/service-limits-data --junitxml=artifacts/test-results/V4-008/service-limits.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_application.py backend/tests/test_v3_management.py backend/tests/test_v4_shell_protocol.py -k 'not actual_shell' -q --basetemp=artifacts/test-results/V4-008/lifecycle-data --junitxml=artifacts/test-results/V4-008/lifecycle.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell_protocol.py -k pending_delete -q --basetemp=artifacts/test-results/V4-008/purge-restart-data --junitxml=artifacts/test-results/V4-008/purge-restart.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell_protocol.py backend/tests/test_server.py backend/tests/test_m20_transport.py -k 'not actual_shell' -q --basetemp=artifacts/test-results/V4-008/transport-related-data --junitxml=artifacts/test-results/V4-008/transport-related.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell_protocol.py -k actual_shell -q --basetemp=artifacts/test-results/V4-008/protocol-launch-guard-data --junitxml=artifacts/test-results/V4-008/protocol-launch-guard.xml
backend/.venv/Scripts/python.exe -X utf8 -m compileall -q backend/src/orvia_backend/shell backend/src/orvia_backend/application.py backend/src/orvia_backend/chat/management.py backend/src/orvia_backend/server.py
npx vitest run apps/desktop/tests/v4-shell.test.ts apps/desktop/tests/backend.test.ts apps/desktop/tests/v3-management.test.ts apps/desktop/tests/m20-transport.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V4-008/desktop-related.json
npm run check
npm run build
$env:ORVIA_TEST_MODULE='V4-008'
npx playwright test tests/e2e/v4-shell.spec.ts
```

|级别|实际结果/证据|真实性与结论|
|---|---|---|
|L0|compileall、check/build、diffcheck通过|66模块开发构建，未重建安装包|
|L1/L2 runtime|38不同通过：runtime-accept35、wsl新增2、escaping新增1|实际三解释器中文/空格/单引号路径、env无secret/proxy、UTF8持续排空/截断、exit7/259、超时/取消及owned子进程和后到Job实际回收。WSL先决条件/未知/预算为mock，真实Bash仅无害控制格式与三host语法验证|
|L1/L2 service|43不同通过：service-final38 mock/SQLite＋service-real5真实|三环境完整输入副本/中文cwd/产物核验/新回传及保留原件，真实PS超时/marker出现后取消、已回收/unknown核验/重复拒绝；实际5目标18.86秒。最后无效参数15最小复验通过，不重复计数|
|L2协议/相关|10协议＋28相关通过|真实Application/SQLite三环境/回传/删除3、严格权限参数/运行取消/重启未知/journal清理4、实际serve控制调度3；application4、v3管理13、server4、M20stdio7。transport-related18通过，launch-guard后真实3重新通过12.03秒|
|L1桌面|desktop-related.json37通过：12目标＋25相关|dialogs模拟，原生取消零执行/完整版本/输出预算/一次许可/新文件保存取消/严格入口验证|
|L3|e2e.json1通过，26.3秒测试/27.0秒总；electron-WtK4ZF/acceptance.json|真实Electron/preload/main/Python/SQLite/PS7/GitBash，原生cwd/input和审批dialogs仅替换；取消批准0、真实运行/核验/new-file读回，子PID先活后因用户取消消失，3事实重启保持/无自动执行；模型0|

按JUnit最新证据去重 **119个不同后端通过、未解决失败/skip0**（38runtime＋43服务＋10协议＋28相关），verification-final.json保存归属/历史失败；不把重复复验或早期failure累加。服务初轮33个setup因fixture旧app.gateway，修为computer后32pass/1SQLite Row对tuple断言fixture，最小修复并38全通过。runtime首轮29pass/2因Job已空与WindowsPID对象短暂存留，改2秒有限真实回查并35通过。生成WSL无害转义片段首次fixture误取早期tr，修取最后NUL段，最终真实Bash通过；无真实distro。L3首轮实际暴露stdio普通锁使Shell状态/取消阻塞：server新增shell.cancel/status/history固定旁路仍全参数验证，后续写仍串行，新增3调度case＋7真实M20相关与L3通过；晚期native launchguard后再最小复验三环境和完整取消L3通过。旧失败报告全部保留。

已实际查看最终流程同样结果截图shell-verified-output.png（先通过electron-beYLcT），中文exit0/回收/仅具体核验提示、原文/哈希/逐文件回传均可读，无横向溢出。L4评估：新增普通权限执行边界，已有三环境真实exec/Job取消/输入回传、协议/删除恢复/相关stdio及Electron验证，覆盖当前重大变化，复用前模块未变权限/模型/存储结论，不跑无关全量或安装包。

限制：Shell普通权限可读写/联网且副作用不回滚；WindowsJob只owned成员，WSL组只当前ownedPGID，WMI/外部broker/新session逃离不能保证全后代。WSL工具hash不覆盖动态库或所有隐式依赖，exe在核验与OS打开之间仍存在普通账户并发替换窗口，不能当系统安全沙箱。原生创建不可硬取消、极端系统阻塞收尾可能超预算；CPU/实际磁盘无强配额。缺普通WSL、人工原生dialogs、独立Windows、真实用户脚本/第三方环境和真实模型未覆盖。敏感样式过滤有限，准确脚本需用户审查。不声明所有Shell或任意安装路径兼容。

现有PowerShell7.6.5（MIT）、WindowsPowerShell5.1.26100.9444（系统已有）、GitBash5.2.26（GPLv3+）、Python3.12/psutil7.2.2/ctypes沿用，无新工具/依赖/模型安装。模块/root/backend/desktop/Computer README、架构/清单/V4/进度已更新。提交前git status/diff/cached及working/staged敏感/禁入审计，报告和commit-receipt在忽略目录；仅显式008文件，预存.zcodeignore/docs/INTERVIEW.md保留不读取/暂存，不收Key/数据库/用户文件/测试产物。独立正常本地commit标题`feat(V4-008): execute approved shell scripts with verified process and artifact evidence`，hash见Git/回执；不amend、不push、不发布/重建包。008提交后按继续目标进入009，完整Goal仍未完成。

试用npm start→设置→Shell检测→选择准确解释器→输入模块README的合成脚本/核验文本及产物名→可选原生cwd/input→准备→核对完整script/version/预算后原生批准→查看退出/回收/具体核验→产物单独原生新位置批准；正在运行可取消，结果未知不重试。缺环境只能显示不可用，不自动切换。

## V4-009：普通用户Windows进程管理（2026-10-08交付）

008已独立正常commit **0ef9b0a**，119不同后端/37桌面/1真实Electron通过，working/staged30文件禁入与敏感检查0；只有预存两个未跟踪文件，保留不读/暂存。009当前唯一模块，不提前010。rewrite_core拥有processes/native.py及native测试/新合成fixtures；graph_core拥有processes/service.py/__init__/README及service测试；rewrite_desktop拥有process-contracts/process-ipc/ProcessPanel/桌面目标测试；主Agent现有接入、E2E、整合审查、文档/提交。所有权无并发编辑。

常规设计：沿用现有Python3.12/psutil7.2.2/Windows ctypes，不新增依赖。有限查看只同用户普通目标PID/name/exe/creation身份，不读取现存cmdline/env/window正文，不记录真实账户SID；不可核验用户/提权/critical/protection拒绝。自己的PID/祖先/Orvia关键进程拒绝。原生准确.exe/完整args/cwd新启动每次确认，挂起创建后同handle核实身份/Token再释放；启动后等待超时不能自动结束用户程序。wait/温和WM_CLOSE/强制terminate均独立审批，close未退出只能still_running，绝不自动升级kill。已有目标动作绑定PID/creation/exeSHA，核验与动作使用同Windows handle，防PID复用误终止，不递归/batch/模糊名字终止、不提权/自动安装/重试。WSL任意内部进程不含此模块。

预定预算：args最多16/合8KiB，完整packet/结果48KiB，wait1～15秒默认3，内存预览20；SQLite单会话128单次尝试不淘汰、正文32/历史10，restart running→unknown且不自动启动/重新发动作。最终预算与接口以实际核验修正。真实仅合成自有程序，native取消0/close不退/另批terminate/实际exit与mock权限边界分开记录，报告只忽略artifacts/test-results/V4-009/。

- [x] √ 实际Windows身份/权限/程序启动、等待、温和关闭与独立终止及SQLite/桌面审批事实。
- [x] √ L0～L3、中文文档清单、敏感审计及独立正常本地commit，回执/标题见下文和Git；随后才进入010。

009整合阶段已跑9协议/28相关共37目标，36pass/1旧server.test假设hello/health严格FIFO失败；health早已控制旁路，修为真实运输ID匹配、两非法帧与有效响应完整性，最小复验通过（server-fifo.xml），未更改业务为满足顺序断言。基础Electron真实launch/wait/noGUIclose/另批terminate4次/重启历史通过18秒（e2e-basic-passed.json）。加测Orvia关闭后目标继续活实际通过，但重新打开后原目标Job来源内存失效，准备动作被保守拒，补测暂失败报告保留，不宣称当前最终L3完成。

已确定窄技术修复：仅用户在当前会话明确选目标准备动作时，从SQLite当前仍保留的action=launch、verified=true、status=still_running准确target，读取PID/create_time/原始creation_ticks完全匹配的来源；native restore_launched同handle freshSHA/ticks/用户/普通Token/关键/保护核验后重建owned来源登记。此登记不是动作许可，仍完整新预览/原生批准/最终samehandle；generic外部Job、unknown/取消、跨会话来源及已淘汰正文不恢复，不自动启动/关闭/终止。来源或exe变化拒绝；32条正文被淘汰或会话删除后无法恢复Job来源是明确限制，不从无正文128尝试反推权限。runtime/service Agent独占实现与新测试，主复验完整重启L3，最终审查与提交仍未完成。

最终009实现/恢复已完成：六个固定preload、七个process私有方法，executable/cwd原生单选、完整16参数/每1000字/合8KiB，wait1～15默认3，preview48KiB/20缓存。原生同SID普通Token、非High/AppContainer/UIAccess、critical/protection全部可读、精确ticks字符串/wholeexeSHA（64MiB）与同HANDLE最终核验；自身/祖先/Orvia/electron/未登记backendworker拒，普通进程列50/48KiB/2000扫描/2秒，不读cmdline/env/window正文或输出SID。未知保护/权限/进程身份failclosed。启动shell=False cleanenv，无Key/proxy/自由env，挂起新handle再核验才resume；未释放失败只回收确切自有新目标，回收未确认unknown。已释放程序不因wait/服务关闭/删除事实自动kill。close仅准确PID顶层WM_CLOSE，不广播/递归，close_sent准确记录，拒关闭或无窗口still_running，不自动Terminate；终止仅另批同句柄准确目标，exit259也可是真实退出。

SQLite process_attempts128不淘汰singleuse、process_executions32正文/历史10/48KiB，先running、最终alive/删除墓碑、不迟到重建、running→unknown无重放。消费前再次核验review未被撤销，原生线程不可硬取消，重复通信取消仍等待实际收尾并持久unknown/后到target；close服务只收尾。unknown/running阻永久删除，已知still_running删除会话只清账本/caches不结束用户应用。初始化在chat.open前建立process账本供删除journal恢复，同事务purge两表。重启来源修复只在用户preview_action/review遇PROCESS_JOB/KEY后，从当前cid一条launch/still_running/JSON真布尔verified及准确PID/time/ticks源facts恢复；freshsamehandle全部身份和普通Token核对、登记内部owned（256最多）后再次inspect，不open/list批量恢复。外部Job/未知/跨cid/淘汰/source改变拒绝；新动作仍新原生批准。

实际命令（项目根目录，合成数据；报告全部artifacts/test-results/V4-009/，模型0）：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_process_native.py -q --basetemp=artifacts/test-results/V4-009/native-restoration-temp --junitxml=artifacts/test-results/V4-009/native-restoration.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_process_native.py -q -k 'restore or unregistered or appcontainer or uiaccess' --basetemp=artifacts/test-results/V4-009/native-restoration-extra-temp --junitxml=artifacts/test-results/V4-009/native-restoration-extra.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_processes.py -q --basetemp=artifacts/test-results/V4-009/service-data --junitxml=artifacts/test-results/V4-009/service.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_processes.py -k real_service -q --basetemp=artifacts/test-results/V4-009/service-real-data --junitxml=artifacts/test-results/V4-009/service-real.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_processes.py::test_revocation_during_review_to_consume_prevents_native_action backend/tests/test_v4_processes.py::test_sqlite_launch_freezes_exact_args_cwd_consumes_before_native_no_replay -q --basetemp=artifacts/test-results/V4-009/service-revocation-data --junitxml=artifacts/test-results/V4-009/service-revocation.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_processes.py -k 'restor' -q --basetemp=artifacts/test-results/V4-009/service-restore-final-data --junitxml=artifacts/test-results/V4-009/service-restore-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_process_protocol.py backend/tests/test_application.py backend/tests/test_v3_management.py backend/tests/test_server.py backend/tests/test_m20_transport.py -q --basetemp=artifacts/test-results/V4-009/related-data --junitxml=artifacts/test-results/V4-009/related.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_server.py::test_recovery_after_bad_frames_and_eof -q --basetemp=artifacts/test-results/V4-009/server-fifo-data --junitxml=artifacts/test-results/V4-009/server-fifo.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_process_protocol.py -k real_process -q --basetemp=artifacts/test-results/V4-009/protocol-recovery-data --junitxml=artifacts/test-results/V4-009/protocol-recovery.xml
backend/.venv/Scripts/python.exe -X utf8 -m compileall -q backend/src/orvia_backend/processes backend/src/orvia_backend/application.py backend/src/orvia_backend/chat/management.py backend/src/orvia_backend/server.py
npx vitest run apps/desktop/tests/v4-processes.test.ts apps/desktop/tests/backend.test.ts apps/desktop/tests/v3-management.test.ts apps/desktop/tests/m20-transport.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V4-009/desktop-related.json
npm run check
npm run build
$env:ORVIA_TEST_MODULE='V4-009'
npx playwright test tests/e2e/v4-processes.spec.ts
```

|级别|实际结果/证据|真实性与结论|
|---|---|---|
|L0|compileall/py_compile、check/build、diffcheck通过|67模块开发构建，无安装包|
|L1/L2 native|42不同通过：native-restoration39＋extra新增3（8通过含5重复）|真实合成私有basePython+DLL/普通程序0/7/259退出、wait still活/noGUI close不杀、隐藏原生GUI接受WM_CLOSE实际退与拒绝后still活→独立Terminate、Unicode argv/cwd/env无secret/proxy；精确来源恢复无动作/权限变动/未释放回收/预算。SID/elevated/High/AppContainer/UIAccess/critical/protection/关键/未知Job拒及PID复用samehandle为mock。无真实敏感target破坏性操作|
|L1/L2 service|38不同通过：34mock/SQLite＋4真实|初始24、revocation新增1、real3（8.49秒）、restore新增10含1真实（final集合11通过3.66秒/1重复），关窗拒绝后仍活/close_sent真/另operationTerminate/旧批准拒。restored仅真布尔来源、未知/假PID/ticks变化/跨cid/淘汰/程序变化0恢复；实际clearowned→inspect拒→源fresh登记→新Terminate|
|L2协议/相关|9协议＋28相关通过|actualApplication/SQLite准确baseexe argv/cwd marker、close未退/另terminate、exit7、Orvia关闭/删除事实目标保持活、新会话新批准终止，重启unknown阻删/无replay/journal两表清理及3stdio事实旁路。related37最初36pass/1FIFO测试假设，按ID最小复验pass；最新原生改变后2real_process最小复验pass4.27秒|
|L1桌面|desktop-related.json40通过：15目标＋25相关|只mock dialogs/backend，用例准确PID/ticks/SHA/动作/返回事实范围、cancel0、私有路径/参数预算/unknown无重放；实际业务另验|
|L3|e2e.json1通过23.4秒测试/24.1秒总，electron-iTHPqu/acceptance.json|实际Electron/preload/main/Python/SQLite/Windows普通baseexe；native selectors/确认仅mock。cancel批准0、实际launch marker/targetalive、Orvia关闭后target仍活、新后端源恢复且新批准wait/close无GUI仍活、另nativeTerminate实际退、4facts/再次重启旧批准拒/无自动启动；云0|

按当前pytest --collect-only的117个名字和最新JUnit匹配，**117个不同后端通过、未解决失败/skip0**（42native＋38service＋9协议＋28相关），缺失/多余0，verification-final.json保存归属/历史失败。旧server FIFO1失败已明确修fixture而非改控制调度；没有其他后端历史fail。L3基础18.0秒通过后，新加关闭/重启后再次管理暴露Job内存来源丢失、补测19.6秒失败，保留e2e-known-owned-first-failed.json；窄可信SQLite来源修复、新negative与真实恢复、完整23.4秒最终通过，不把之前失败或基础4步骤当最终。真实basePython属于已装环境，venv redirector不能当脚本最终进程；测试fixture副本/DLL仅忽略目录，不新增运行时安装。

已实际查看process-terminated.png：准确进程退出、动作/事实不等业务完成、PID/精确FILETIME/路径/SHA/真实exit0xE009及四步历史可读，无横向溢出。L4评估：新增普通进程副作用边界，已用实际Windows同handle/窗体WM_CLOSE与另Terminate/释放后存活/Electron重启及相关删除/stdio27+1回归覆盖变化，复用未变模型/Skills/SQLite原有结论，不跑无关全量或打包。

限制：仅Windows普通可核验目标；名称否决含Explorer/DWM/系统关键、Orvia/electron，非全部同用户普通程序都可操作，一般已有Job/隔离令牌/身份不可读拒绝。无提权/LPAC/path/network/CPU/disk隔离，普通程序本身或外部Job可能影响存活，已释放目标不主动回收/不承诺永远活。关闭未保存窗口须用户处理，Terminate无法通用撤销，不递归/结束后代或外部broker，不保证一般业务成功。来源32正文淘汰/删除会话后不能重建lostJob归属；256owned缓存可失效须仍有效来源再核验。内核/磁盘原生阻塞无法硬deadline，线程收尾可超15秒预算；exeSHA不覆盖所有隐式依赖/文件竞态。未真人工dialogs、用户程序/第三方未保存行为、真实其他用户/管理员/保护目标破坏性试验、独立Windows/模型/发布验收。

沿用Python3.12.6/psutil7.2.2/ctypes/aiosqlite，无新工具/依赖/模型安装；原生常量参照Microsoft WinBase.h及TokenInformationClass（native README链接），不修改系统策略。模块/root/backend/desktop/Computer README、架构/清单/V4/进度已更新。提交前status/diff/cached/working与staged敏感和禁入检查，回执在忽略目录；仅显式009文件，预存两个文件保持不读/暂存，不收密钥/DB/测试产物/DLL/用户文件。独立正常本地commit标题`feat(V4-009): manage approved ordinary Windows processes with exact identity evidence`，hash见Git/commit-receipt；不amend、不push、不Release/重建包。009提交后自动进入010，Goal仍未完成。

试用npm start→设置→普通用户进程→刷新/明确准确PID或原生选.exe、JSON完整参数、可选cwd→准备→原生逐项批准→看exited/still_running/unknown及close_sent；close未退需另选terminate并新批准，不能用旧按钮或聊天授权。历史可选已核验准确target再现查，不恢复旧执行资格；新启动程序要自行关闭或单独批准终止。

## V4-010：有界多来源调研与简报 Skills（2026-10-08交付）

009已交付独立本地commit **6c2472a**；117不同后端、40桌面、1真实Electron通过。按已恢复“继续目标”自动进入010，未开始011；预检main、origin/main与历史，工作树仅预存.zcodeignore/docs/INTERVIEW.md，不读或暂存，不push/发布/重建安装包。

目标：每任务最多10公共网页、2检索轮；独立采集与每批固定Main正文发送审批、不可变来源引用回查、比较/冲突/缺口/覆盖、已核验回答三格式新文件保存。复用Browser安全HTTP/Playwright、SQLite证据、M15引用校验、M16真实成品服务，不把摘要或搜索片段替代原文事实。Tavily缺失明确不可用，显式公共URLs可用；模型默认mock，真实读取/SQLite/三格式文件分开记录。

文件所有权：graph_core仅新research服务/README/test_v4_research；rewrite_core仅Skills服务/README及对应测试；rewrite_desktop仅新research contracts/ipc/Panel/unit；主Agent仅现有Application/生命周期/删除/preload/API/Settings与协议/E2E、审查文档提交。禁止并发同文件/后续开发/传递凭据。沿用依赖，不提前安装资源。L0类型/构建与文档，L1边界，L2实际接口/原文/SQLite/成品，L3 Electron取消/审批/成品/重启；L4按最终跨模块改动评估。完成条件为实际实现、必要验证、文档/敏感审计及独立正常本地commit，当前未完成。证据只放忽略artifacts/test-results/V4-010/。

### V4-010 当前交付事实、验证与限制

- [x] √ Research实际保存/单次采集/精确来源检索/逐批准确Main/原文引用/实际成品事件关联。SQLite研究三表、120秒采集/十个规范URL尝试（失败也计）/两轮（失败计）/每轮5候选/五准确host；URL输入8KiB、候选URL标题8KiB、URL元数据16KiB，单会话20任务/128单次阶段尝试，历史10/完整48KiB。空范围拒绝；source-only可用。
- [x] √ 调研独立关联不扩M20三资料。Browser安全策略保留，当前Tavily缺失准确unavailable，站点仅本机过滤不发送搜索服务。FTS复用Context；研究代理仅当前任务准确标签、最多150定位、前后版本/撤回复核；Store最终事务墓碑阻迟到索引，独立目录Mission保持兼容。
- [x] √ 最多四批，每批三源、每源最多3×600字符；最终十源各一个原片段。13→10明确排除三源和scope计数，全文/抽样/OCR/截断覆盖保留。实际system/input合42KiB、完整可见包48KiB（含重复片段），固定Main30秒4096tokens单调用，不请求工具/重试；最终四项比较/冲突/缺口/覆盖，引用只回查原文、同源冲突/不存在引用拒绝。批摘要不替代原文或新权限；ready仅回答保存，不等完整业务。
- [x] √ Web Research/Report Build真实1.1.0注册与三窄工具，可与同cid准确目录/文本/检索组合。Skill只准备计划或版式；pending/采集失败/搜索不可用/遗漏/计数不一致即limited停止，不能以complete自述推进。UI原生选择准确目录及文本范围，随后实际逐叶网关检查并撤销；研究计划在历史点击重新核对后仍新原生采集批准。七后端/八preload固定入口，无自由转发；控制status/history/cancel旁路已实测。
- [x] √ 同cid活性、初始资料撤回/全文变化的采集前复核、生成前后准确原文版本、取消等待实际协程结束、重启running→interrupted且无重放、永久删除三表及正文/索引、晚到响应拒绝。三格式独占新文件/读回复用M16，实际publication事件和源回答版本才记最多三格式回执；回调传准确request_id事件，避免并发其它消息被误作最近成品。

L0：npm run check/build（69 renderer modules）及py_compile/compileall当前服务/契约、git diff --check通过。L1/L2 **197不同目标通过，1符号链接权限skip**：当前收集198项；34研究服务、35Skills、8协议/实际HTTP/成品/取消/调度、121相关（120pass/1skip）。最新JUnit去重verification-final.json无missing/failed。桌面 **38通过**（18调研含历史重核新批准+取消窗口许可/返回身份，3本地Skill，2框架，3M15，2M16，10backend）。L3 **1真实Electron流程11.2秒/总12.0秒通过**：WebResearch实际准备→重新核对→批准TCP原文采集；模型批次取消0→分别batch/final；引用原文回查→ReportBuild实际三格式版式→新文件取消0/逐格式写入读回→恢复同三receipt且未网络/云重播。实际Electron/preload/main/Python/HTTP TCP/SafeHTTP正文预算/Browser解析/SQLite/原文/DOCX/PPTX/PDF均执行；dialogs、合成DNS socket映射和两次固定Main输出为明确mock，真实云模型0，不假称生产Internet/Tavily成功。人工原生dialogs/独立机器/真实Main语义未覆盖。L4评估：涉及共享索引/删除/传输/成品边界，已做针对跨模块回归及真实流程；复用未改变模块结论，不重复全量发布/安装包验收。

实际命令（项目根；证据统一忽略artifacts/test-results/V4-010/）：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research.py -q --basetemp=artifacts/test-results/V4-010/service-data --junitxml=artifacts/test-results/V4-010/service.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research.py -q --basetemp=artifacts/test-results/V4-010/service-final-data --junitxml=artifacts/test-results/V4-010/service-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research.py::test_collect_rechecks_explicit_source_scope_before_any_web_request -q --basetemp=artifacts/test-results/V4-010/service-collect-guard-data --junitxml=artifacts/test-results/V4-010/service-collect-guard.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research.py::test_empty_scope_rejected_and_source_only_scope_valid backend/tests/test_v4_research.py::test_cancelled_search_has_terminal_step_and_missing_main_does_not_retry backend/tests/test_v4_research.py::test_final_explicit_subset_records_real_coverage_omission_and_batch_processed_fact -q --basetemp=artifacts/test-results/V4-010/service-scope-data --junitxml=artifacts/test-results/V4-010/service-scope.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research.py::test_thirteen_original_sources_default_final_sends_ten_and_approves_exact_omission -q --basetemp=artifacts/test-results/V4-010/service-thirteen-data --junitxml=artifacts/test-results/V4-010/service-thirteen.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research.py::test_task_and_independent_attempt_caps_reject_before_requests backend/tests/test_v4_research.py::test_full_preview_budget_includes_duplicate_fragments_and_url_metadata -q --basetemp=artifacts/test-results/V4-010/service-budget-data --junitxml=artifacts/test-results/V4-010/service-budget.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research_skills.py -q --basetemp artifacts/test-results/V4-010/skills-final-temp --junitxml artifacts/test-results/V4-010/skills-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research_skills.py -q -k 'status or pending_envelope' --basetemp artifacts/test-results/V4-010/skills-status-temp --junitxml artifacts/test-results/V4-010/skills-status.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research_skills.py -q -k 'status or pending_envelope or source_only' --basetemp artifacts/test-results/V4-010/skills-coverage-temp --junitxml artifacts/test-results/V4-010/skills-coverage.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research_protocol.py -q --basetemp=artifacts/test-results/V4-010/protocol-data --junitxml=artifacts/test-results/V4-010/protocol.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research_protocol.py -k 'inflight or stdio' -q --basetemp=artifacts/test-results/V4-010/cancel-data --junitxml=artifacts/test-results/V4-010/cancel.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research_protocol.py::test_actual_http_citations_publication_three_formats_restart_and_purge -q --basetemp=artifacts/test-results/V4-010/receipt-final-data --junitxml=artifacts/test-results/V4-010/receipt-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research_protocol.py::test_publication_callback_uses_exact_receipt_despite_later_message -q --basetemp=artifacts/test-results/V4-010/receipt-race-data --junitxml=artifacts/test-results/V4-010/receipt-race.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_skills.py backend/tests/test_v4_skills_protocol.py backend/tests/test_m15_synthesis.py backend/tests/test_m16_publication.py backend/tests/test_m12_browser_chat.py backend/tests/test_browser.py backend/tests/test_context.py backend/tests/test_storage.py backend/tests/test_v3_management.py -q --basetemp=artifacts/test-results/V4-010/related-data --junitxml=artifacts/test-results/V4-010/related.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_skills.py::test_builtins_versions_and_invalid_inputs_not_empty_success -q --basetemp=artifacts/test-results/V4-010/skills-migration-temp --junitxml=artifacts/test-results/V4-010/skills-migration.xml
npm run check
npm run build
npx vitest run apps/desktop/tests/v4-research.test.ts apps/desktop/tests/v4-skills.test.ts apps/desktop/tests/v4-local-skills.test.ts apps/desktop/tests/m15-contracts.test.ts apps/desktop/tests/m16-contracts.test.ts apps/desktop/tests/backend.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V4-010/desktop-final.json
npx vitest run apps/desktop/tests/v4-research.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V4-010/desktop-ipc-final.json
$env:ORVIA_TEST_MODULE='V4-010'
npx playwright test tests/e2e/v4-research.spec.ts
```

历史失败均保留：Skills初4项fixture误读(messages,count)，修后最小/最终pass；related旧断言只3builtin available失败，010新增真实两Skill故应5，修正目标通过；Electron首轮中文selector错、第二轮误认默认filename为标题、第三轮复用旧成功提示过早查文件，均测试修正，最终真实11.2秒通过。原文成品回调去掉最近消息竞态时未带持久事件继承的request_id，receipt.xml复验发现实际事件严格匹配拒绝；补准确rid后receipt-final及并发后来消息race目标均pass。不是隐去失败或仅构建通过。已实际查看electron-lhbFTS/research-three-formats.png（中文/成品界面可读）；acceptance.json记录TCP两请求、mock/真实边界、三个实际filename/格式/版本与0真实云。既有LangChain弃用/pdfium读文本warning保留，Windows普通账户符号链接skip不提权。

沿用现有Python3.12.6、aiosqlite/pydantic/httpx/trafilatura/jieba、LangGraph、DOCX/PPTX/PDF字体与生成库，无新增工具/依赖/模型安装或锁文件变化。已更新模块/Skills/root/backend/desktop/Browser/Publication/Storage README、架构、清单与V4。working敏感/禁入检查42文件为0，实际凭据只核存在、不输出值；cached最终检查/commit回执在忽略目录。显式仅010文件、不收Key/DB/用户文件/测试产物、不读或暂存预存两文件；独立正常本地commit标题feat(V4-010): compose approved bounded web research and cited briefs，实际hash见Git及commit-receipt，未push/发布/重建包，不amend。010完成提交后自动进入011，Goal此时仍未完成。

试用：npm start→设置→调研与报告→明确合成问题与公共URLs/最多两查询/最多五host/资料→创建或重新核对保存计划→核对完整计划并原生批准→查看逐页状态/来源与搜索不可用/限额→可选批摘要和最终原文发送各另批→引用回查→制作Word/PPT/PDF，预览版式后原生新文件保存。Skills选所属会话，web-research输入query/urls换行字符串；report-build输入message_id/format/title；同cid需要文件读取时原生选择只读目录与文本范围，pending保存后转调研/简报入口新批准。不是完整行业报告、云语义事实保证或自动业务结束；静态公开读取可用，登录/写入/下载不在010范围，原成品与用户文件删除会话后保留。


## V4-011 实施开始（2026-10-08）

V4-010 已独立提交3e9234d，197 backend通过/1skip、38 desktop通过、1真实Electron流程；不重复旧模型下载或打包。最后011实现程序白名单安全读最多三次、原deadline预算、取消/终态账本及逐目标事实闭环。普通静态公开网页与纯FTS SELECT可用；Tavily收费POST、动态Browser外发/未知结果、模型、Shell、进程及文件变更均不自动重试。退避0.2/0.5秒，Retry-After超过剩余时间或0.5秒即拒再次发送。上下文纯SELECT新增总3秒有限预算，向量推理/索引清理不包入。

独立文件所有权：rewrite_core仅retry新服务/README/目标测试与Browser两生产文件；graph_core仅task_progress/coordinator/verification及闭环tests；rewrite_desktop先新retry契约/IPC/面板/unit（12通过），再仅新011 fixture/launch/E2E；主Agent现有应用/生命周期/删除/Context/preload/main/API/Settings/协议tests与docs/整合验证提交。只当前模块、无并发同文件、无Key。L0类型/build/语法；L1预算与分类/事实seal；L2真实SQLite/HTTP/协议/永久删除及历史；L3真实Electron重试/记录/重启；L4因完成判定共享改动做V3/M20流程目标回归，不执行发布全量。实际实现和验证后才标完成。


### V4-011 最终实现、验证与交付（2026-10-08）

- [x] √ 程序固定browser.static_read/context.sqlite_read两资格，发送前连接失败/准确429或503/原SQLite BUSY或LOCKED三attempt同业务ID，独立连续sequence；退避0.2/0.5秒、原deadline/服务器Retry-After/取消。单页20秒、原重定向3跳与合计4网络请求；纯SELECT3秒稳定SEARCH_TIMEOUT；向量推理/失效写入/模型/Shell/进程/文件变更/MCP/动态资源与外发/收费Tavily POST不重试。unknown/NETWORK_UNKNOWN保留发送后未知，不记成功。
- [x] √ RetryService私有scope由可信cid和传输请求摘要绑定，调用序号+tool+参数sha派生每子读取UUID5，三attempt共享身份；同业务再次拒绝不调用、不缓存返回值。SQLite两个无正文表存时间/原因/固定码/hash，history只读32run/32KiB，跨cid拒，32会话并发/内存128，磁盘身份事实保留到会话删除而不自动清配额。
- [x] √ 关闭等pending initial/terminal账本收尾，原deadline后/取消抵抗的晚callback/存储等待超时均不返回值；终态/墓碑拒旧记录。迁移先于删除journal，重启running只interrupted，独立Mission兼容；运行安全读阻删除，purge同事务清两表并清内存。存储锁可延迟收尾，不承诺任意线程强终止；账本写本身不自动重试。
- [x] √ 原step_states封印本目标规范sha、准确result_id、实际消息/扫描/动作账本/全文版本。set完成不能伪造跨cid/他步骤/自述/缺证明，审批类只能准确continuation；review+token+position+推进/请求状态同事务，整体逐项复核并CAS终态。部分扫描/截断/空引用/部分隔离为limited；M18exit0/M17未精确原需求应用不能等用户业务实现，明确accept产生用户回执，保留accepted未执行说明。正确固定简报保存仅证明所选引用范围及真实回执/读回，非完整行业覆盖或语义保证。
- [x] √ pause/resume/finish取消竞态、重复/迟到通知/失败误发completed事件修复；主进程控制入口与stdio均允许当前运行时retry.history和research状态/历史/取消旁路，写/审批仍串行。只读Settings安全重试面板，无安全分类/重放入口，切换会话忽略晚response、同cid重复选择不使busy永久true；task_acceptance/task_summary两真实消息跨IPC契约接通。

L0：npm run check、npm run build（70 modules，开发版）、Python compileall/py_compile、node --check launcher、git diff --check通过。L1/L2按当前17个backend文件collect-only与最新JUnit去重，**231项=227通过/4显式未启用Chromiumskip，missing0/failed0**：61重试目标、30新闭环、5真实协议以及相关M20/V3/Browser/Context/Storage/Research/删除；重叠只计一次，verification-final.json逐项指向实际XML。desktop-final.json **54通过**：14重试、4M20契约、8V3视图、18调研、10Backend。

L3 **1真实Electron最终整段14.3秒/总15.1秒通过**，electron-2Cy7uA/acceptance.json：实际TCP503×2→200，同business三attempt退避0.2/0.5；运行中retry.history2.8ms旁路、research status/history/retry三控制4.9ms；原生确认mock后的真实collect挂起→cancel→ledger cancelled/迟到正文不存，只有一次研究HTTP；两目标[completed,running]→各自原文保存后[completed,completed]；未实现目标明确接受+本地摘要，[accepted,completed]真实task_acceptance/task_summary跨IPC；重启history精确相等、accepted仍未实际执行、网络零重放，重复同cid选择刷新正常。实际TCP共6请求。已实际查看最终两目标/接受非执行/重启账本三张PNG，subagent也核五图中文可读。原生dialogs/公共DNS socket路由为明确测试替身，固定Main adapter虽安装但此流程Main调用0；真实云0，不假称生产Internet/Tavily成功。其他backend普通回答/生成和M18准确账本使用合成mock，与真实SQLite/改名/隔离/DOCX区分。L4评估共享完成/取消/删除/传输边界重大，已做针对V3/M20及相关跨模块回归和真实Electron流程，复用没变的云/隔离/发布结论，不重复全量安装/生产验收。

实际root命令（项目根、统一忽略artifacts/test-results/V4-011/）：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry_protocol.py -q --basetemp=artifacts/test-results/V4-011/protocol-data --junitxml=artifacts/test-results/V4-011/protocol.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry_protocol.py::test_independent_mission_read_keeps_original_capability -q --basetemp=artifacts/test-results/V4-011/protocol-mission-data --junitxml=artifacts/test-results/V4-011/protocol-mission.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry_protocol.py -q --basetemp=artifacts/test-results/V4-011/protocol-final-data --junitxml=artifacts/test-results/V4-011/protocol-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m20_natural.py backend/tests/test_m20_stream_persistence.py backend/tests/test_m20_generation_errors.py backend/tests/test_v3_workspace.py backend/tests/test_v3_document_presentation.py backend/tests/test_context.py backend/tests/test_storage.py backend/tests/test_browser.py backend/tests/test_m12_browser_chat.py backend/tests/test_v4_research_protocol.py backend/tests/test_v3_management.py -q --basetemp=artifacts/test-results/V4-011/related-data --junitxml=artifacts/test-results/V4-011/related.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest --collect-only -q backend/tests/test_v4_retry.py backend/tests/test_v4_retry_browser.py backend/tests/test_v4_retry_protocol.py backend/tests/test_v4_task_closure.py backend/tests/test_browser.py backend/tests/test_browser_engine.py backend/tests/test_m20_natural.py backend/tests/test_m20_stream_persistence.py backend/tests/test_m20_generation_errors.py backend/tests/test_v3_workspace.py backend/tests/test_v3_document_presentation.py backend/tests/test_context.py backend/tests/test_storage.py backend/tests/test_m12_browser_chat.py backend/tests/test_v4_research_protocol.py backend/tests/test_v3_management.py backend/tests/test_v3_compound.py > artifacts/test-results/V4-011/collected.txt
npm run check
npm run build
npx vitest run apps/desktop/tests/v4-retry.test.ts apps/desktop/tests/m20-contracts.test.ts apps/desktop/tests/v3-workspace.test.tsx apps/desktop/tests/v4-research.test.ts apps/desktop/tests/backend.test.ts --reporter=default --reporter=json --outputFile=artifacts/test-results/V4-011/desktop-final.json
$env:ORVIA_TEST_MODULE='V4-011'
npx playwright test tests/e2e/v4-retry.spec.ts
backend/.venv/Scripts/python.exe -X utf8 -m compileall -q backend/src/orvia_backend/retry backend/src/orvia_backend/browser backend/src/orvia_backend/chat/coordinator.py backend/src/orvia_backend/chat/task_progress.py backend/src/orvia_backend/chat/verification.py backend/src/orvia_backend/chat/management.py backend/src/orvia_backend/context/service.py backend/src/orvia_backend/application.py backend/src/orvia_backend/server.py backend/tests/test_v4_retry_protocol.py backend/tests/v4_retry_fixture.py
```

重试owner实际验证命令（Python前缀同上，不覆盖历史失败）：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry.py backend/tests/test_v4_retry_browser.py -q --basetemp artifacts/test-results/V4-011/retry-temp --junitxml artifacts/test-results/V4-011/retry.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry.py backend/tests/test_v4_retry_browser.py -q -k 'total_deadline or close_waits or forget or duplicate_concurrent or actual_tcp or three_transient or format_rejection or tavily' --basetemp artifacts/test-results/V4-011/retry-extra-temp --junitxml artifacts/test-results/V4-011/retry-extra.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry.py -q --basetemp artifacts/test-results/V4-011/retry-lifecycle-temp --junitxml artifacts/test-results/V4-011/retry-lifecycle.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry.py -q -k 'late_success' --basetemp artifacts/test-results/V4-011/retry-lifecycle-recovery-temp --junitxml artifacts/test-results/V4-011/retry-lifecycle-recovery.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry.py backend/tests/test_v4_retry_browser.py -q --basetemp artifacts/test-results/V4-011/retry-final-temp --junitxml artifacts/test-results/V4-011/retry-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry.py backend/tests/test_v4_retry_browser.py -q -k 'unknown or disconnect' --basetemp artifacts/test-results/V4-011/retry-unknown-temp --junitxml artifacts/test-results/V4-011/retry-unknown.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry_browser.py::test_html_extraction_elapsed_original_deadline_does_not_complete_read -q --basetemp artifacts/test-results/V4-011/retry-extraction-temp --junitxml artifacts/test-results/V4-011/retry-extraction.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_browser.py backend/tests/test_browser_engine.py -q --basetemp artifacts/test-results/V4-011/browser-regression-temp --junitxml artifacts/test-results/V4-011/browser-regression.xml
```

闭环owner各次实际完整命令（已同时归档closure-commands.json，含结果/失败修复）：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v3_compound.py -q --basetemp=artifacts/test-results/V4-011/closure-v3-data --junitxml=artifacts/test-results/V4-011/closure-v3.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v3_compound.py::test_full_request_keeps_every_goal_and_waits_for_explicit_acceptance -q --basetemp=artifacts/test-results/V4-011/closure-v3-fix-data --junitxml=artifacts/test-results/V4-011/closure-v3-fix.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_task_closure.py -q --basetemp=artifacts/test-results/V4-011/closure-data --junitxml=artifacts/test-results/V4-011/closure.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_task_closure.py -q --last-failed --basetemp=artifacts/test-results/V4-011/closure-fix-data --junitxml=artifacts/test-results/V4-011/closure-fix.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest 'backend/tests/test_m20_natural.py::test_real_batch_cancellation_or_revoke_keeps_only_discovered_prefix[cancel]' backend/tests/test_m20_natural.py::test_material_wait_native_stream_citations_single_continue_and_removal backend/tests/test_m20_natural.py::test_browser_fill_cannot_complete_send_without_approved_receipt_and_new_verification -q --basetemp=artifacts/test-results/V4-011/closure-related-fix-data --junitxml=artifacts/test-results/V4-011/closure-related-fix.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_task_closure.py::test_explicit_acceptance_consumes_exact_token_step_and_not_a_success_result backend/tests/test_v4_task_closure.py::test_exit_zero_or_generated_draft_only_limited_and_explicit_accept_closes backend/tests/test_m20_natural.py::test_material_wait_native_stream_citations_single_continue_and_removal backend/tests/test_m20_natural.py::test_browser_fill_cannot_complete_send_without_approved_receipt_and_new_verification -q --basetemp=artifacts/test-results/V4-011/closure-review-data --junitxml=artifacts/test-results/V4-011/closure-review.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_task_closure.py::test_native_continuation_exact_review_bound_not_swappable backend/tests/test_v4_task_closure.py::test_zero_entry_complete_scan_valid_but_partial_scan_never_sealed backend/tests/test_v4_task_closure.py::test_truncated_web_read_limited_and_direct_sealing_cannot_bypass backend/tests/test_v4_task_closure.py::test_goal_summary_cannot_complete_remaining_action_and_duplicate_result_not_reused backend/tests/test_v4_task_closure.py::test_source_full_version_or_withdrawal_invalidates_prior_step_before_whole_completion -q --basetemp=artifacts/test-results/V4-011/closure-boundaries-data --junitxml=artifacts/test-results/V4-011/closure-boundaries.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_task_closure.py::test_real_file_change_requires_exact_operation_and_each_verified_entry backend/tests/test_v4_task_closure.py::test_real_cleanup_subset_not_full_goal_and_all_entries_evidenced backend/tests/test_v4_task_closure.py::test_real_publication_saved_bytes_exact_preview_and_source_versions_close_goal backend/tests/test_v4_task_closure.py::test_local_read_errors_close_failed_without_model_fallback_or_late_completion -q --basetemp=artifacts/test-results/V4-011/closure-actions-data --junitxml=artifacts/test-results/V4-011/closure-actions.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m20_natural.py::test_desktop_compound_requires_each_new_matching_uia_operation backend/tests/test_m20_natural.py::test_desktop_completed_ledger_precedes_any_summary_message backend/tests/test_m20_natural.py::test_same_model_explicit_nonstream_fallback_is_single_use backend/tests/test_m20_natural.py::test_m15_partial_stream_fallback_native_confirm_is_once_and_bound backend/tests/test_v3_compound.py::test_full_request_keeps_every_goal_and_waits_for_explicit_acceptance -q --basetemp=artifacts/test-results/V4-011/closure-desktop-fallback-data --junitxml=artifacts/test-results/V4-011/closure-desktop-fallback.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m20_natural.py::test_wait_cancel_restart_and_cross_conversation_never_resume backend/tests/test_m20_natural.py::test_material_wait_native_stream_citations_single_continue_and_removal backend/tests/test_m20_natural.py::test_same_model_explicit_nonstream_fallback_is_single_use backend/tests/test_v3_compound.py::test_clarification_keeps_tail_and_verified_completion_gate backend/tests/test_v3_compound.py::test_confirmed_answer_fallback_continues_remaining_goals -q --basetemp=artifacts/test-results/V4-011/closure-resume-data --junitxml=artifacts/test-results/V4-011/closure-resume.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_task_closure.py::test_late_result_repeat_notify_and_old_update_never_overwrite_terminal -q --basetemp=artifacts/test-results/V4-011/closure-terminal-data --junitxml=artifacts/test-results/V4-011/closure-terminal.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_task_closure.py::test_late_result_repeat_notify_and_old_update_never_overwrite_terminal -q --basetemp=artifacts/test-results/V4-011/closure-terminal-fix-data --junitxml=artifacts/test-results/V4-011/closure-terminal-fix.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_task_closure.py::test_cancel_immediately_after_review_commit_never_overwrites_request_status backend/tests/test_m20_natural.py::test_same_model_explicit_nonstream_fallback_is_single_use backend/tests/test_v4_task_closure.py::test_explicit_acceptance_consumes_exact_token_step_and_not_a_success_result -q --basetemp=artifacts/test-results/V4-011/closure-pause-race-data --junitxml=artifacts/test-results/V4-011/closure-pause-race.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_task_closure.py::test_exit_zero_or_generated_draft_only_limited_and_explicit_accept_closes backend/tests/test_v4_task_closure.py::test_real_file_change_requires_exact_operation_and_each_verified_entry backend/tests/test_v4_task_closure.py::test_real_publication_saved_bytes_exact_preview_and_source_versions_close_goal -q --basetemp=artifacts/test-results/V4-011/closure-gate-data --junitxml=artifacts/test-results/V4-011/closure-gate.xml
```

历史失败保留：retry-lifecycle两fixture未等待callback实际启动，补entered事件后最小三目标恢复；closure初七失败涉及绑定缺文档review/终态处理/fixture原文片段，修后最小七通过；V3 accepted消息被当作最近synthesis、M20取消partial验证抢先failed、浏览器摘要缺operation_id过滤修复，空引用旧误判完成断言按新有限状态更正。root独立Mission初fixture误用name，按原title/client_request_id修后通过。Electron历史selector/进行中尚无finalreply的task_progress需正常读取投影、reload耗预算/误期待自动summary为测试修正；同cid选择busy和main漏control是真生产缺陷已修并最终实测。e2e-validation-notes.json保各轮失败与当前成功，不隐去失败。LangChain弃用warning保留，4Chromium真实引擎测试显式门未启用（其生产动态路径未加重试，010/M07既有结论复用），不假称完整真实动态浏览器回归。

未覆盖：人工原生dialogs、生产公网/Tavily/真实Main语义、独立Windows/签名/安装包、普通WSL无发行版；普通Job非全系统进程/网络沙盒，MCP声明不保证服务只读；有界调研/引用结构不是事实真实性或完整行业分析。SQLite外部写锁若连账本也不可写则拒读，不绕事实链；只读未知终态保留，不重试。没有新增工具/依赖/模型安装或锁变化，001/004已安装事实沿用：redis7.0.0、项目CPUtorch2.8.0+cpu/transformers4.57.6/safetensors0.7.0与锁定配套库，固定官方Qwen六文件已批准、校验并真实合成推理，测试Redis7.2.4镜像仅既有隔离夹具。

已更新retry/chat/browser/context/storage模块README、root/backend/desktop、AGENTS停止点、架构/清单/V4。working敏感及禁入检查44文件为0，实际Key只核存在、不输出值；随后cached内容与敏感审计、commit回执在忽略目录。显式仅011文件，预存.zcodeignore/docs/INTERVIEW.md原样保留未读/暂存，不收凭据/DB/日志/模型/用户文件/测试产物，不amend、push、发布或重建包。独立正常本地commit标题feat(V4-011): bound safe read retries and verify every task goal，实际hash交付回执与后续本地文档记录；011后停止原Goal，不启动其它业务。

试用：根npm start→当前会话明确公共静态URL读取或已有来源检索→允许瞬态故障自动最多3attempt→设置/安全读取重试记录/明确会话/刷新查看固定原因、budget与终态。自然输入两个有支持的目标观察每项证据；截断/空引用/受限脚本/草稿必须明确接受或取消，accepted说明保留；调研的取消入口在采集中可及时用。关闭重开仅读持久账本与进度，不网络/模型/写动作重放。Redis不开仍原能力可用，固定Qwen只离线已批准目录。全部各模块本地提交等待用户手动push。


### 全部V4授权模块本地交付回执（2026-10-08）

- [x] √ 用户恢复的Goal顺序已全部实际实现、必要验证、文档与逐模块独立正常本地commit；001为已完成基线、未重复实施。最后011实际提交 **aa7d30f7e8c2f95e8bbeed75fcd18454c3c5be12**，44文件2409增加/71删除；227backend通过/4显式Chromiumskip、54desktop、1真实Electron（14.3秒）；working/cached敏感和禁入44文件全部为0，完整暂存差异与回执在忽略011目录。最终仅去除测试文件额外EOF空行，cached diff --check通过，功能证据复用不重跑。

| 模块 | 实际正常本地commit | 当前交付 | 证据目录 |
|---|---|---|---|
|V4-001|a6c9d300e76814dc1a4f809c29b406a865062be9|可选本地Redis辅助；SQLite事实保留|artifacts/test-results/V4-001/|
|V4-002|c1ca871a79a8753b96c34ef912fde1974729f5da|声明式Skills注册与有界组合|artifacts/test-results/V4-002/|
|V4-004|757fefc1d12c9b7a28e5e5c368db85ae61faac8d|固定本地Qwen与混合检索|artifacts/test-results/V4-004/|
|V4-003|9bd88644ffa50d2cb2e1fdf46c654d32ebfbf33e|五轮上下文及批准长期记忆|artifacts/test-results/V4-003/|
|V4-005|acd22eee67e5a523c28f4076af259c68a569a54d|来源绑定实体关系与有界图查询|artifacts/test-results/V4-005/|
|V4-006|c9e3074590823aba58121d27e466eb1e9eea43c3|批准查询改写与本地Context Skills|artifacts/test-results/V4-006/|
|V4-007|aacab8dde34c781f664ea159aaade9dc767b1f4d|审批MCP只读客户端及专用凭据|artifacts/test-results/V4-007/|
|V4-008|0ef9b0a8ed14baf8cd91b1414908c9f72caaa185|批准Shell/实际Windows解释器与产物核验|artifacts/test-results/V4-008/|
|V4-009|6c2472a9e31b6d6d840be9a8833e7f3e5e0c9287|准确身份普通用户Windows进程管理|artifacts/test-results/V4-009/|
|V4-010|3e9234d7d575b678e7bbeaaa827658c037e58ee4|有界调研、原文综合与独立三格式保存|artifacts/test-results/V4-010/|
|V4-011|aa7d30f7e8c2f95e8bbeed75fcd18454c3c5be12|安全读取重试与逐目标事实闭环|artifacts/test-results/V4-011/|

V4-001真实隔离Redis、V4-004已批准固定Qwen真实合成推理，与其余默认mock/真实本机组件分别记录；各模块具体命令/模型计数/历史失败/未覆盖风险在对应段和目录，不重复旧有效验证。Redis默认可选、断连不影响事实业务，三个角色各固定模型与审批/证据/权限链保留。工具依赖安装仅001/004：redis7.0.0、CPUtorch2.8.0+cpu/transformers4.57.6/safetensors0.7.0及项目锁定配套库、官方Qwen六工件；Redis7.2.4镜像仅隔离验收夹具保留，后续模块无新安装。本地模型约1.12GiB，配套库文件约3.02GiB；实际来源/版本/校验/测量见004段。

为了把真实已创建commit号写入本PROGRESS，另建纯文档正常提交docs(V4-011): record completed goal and local commit receipts；不amend任何模块、不混入后续业务，文档only不重跑代码测试。提交前同样核status/diff/cached，显式只本文件，预存两未跟踪文件不读取/暂存。011完成后停止，Goal所有授权开发要求已满足；不自动启动其它任务。所有这些提交仍仅本地，未push、Release或重建安装包，手动推送由用户决定。已知限制（普通WSL未覆盖、真实供应商语义/生产Internet/Tavily、人工原生dialogs、独立Windows/签名安装验收等）保留，不能把mock和本机结果替代它们。

## 自学指南交付（2026-10-08，纯文档）

用户要求基于当前源码编写统一中文学习路径与概念地图，新增 `docs/LEARNING_GUIDE.md`，基线 `892d5b8`。不实施新业务模块，不改变代码、配置或依赖。预检 `git ls-remote --symref origin HEAD` 确认远端默认 main，当时远端 HEAD 与本地基线一致；此只读核对不表示 Agent 执行过推送，也不改写上文历史交付状态。

- [x] √ 覆盖产品定位、进程/模型/权限、核心数据流、3–5天路线、M01–M20/V3/V4学习清单、易混点、14道题及答案；包含两张 Mermaid 图，正文约3900汉字（不含英文路径等）。
- [x] √ L0：PowerShell 内联 Python（`backend/.venv/Scripts/python.exe -X utf8 -`）核对61处完整/缩写路径均存在、题数14、图数2、代码围栏闭合及常见凭据/私钥模式零命中；人工核对关键源码与两图节点/边。结果 `artifacts/test-results/LEARNING_GUIDE/l0-review.json`，已确认 Git 忽略。未做浏览器图形渲染验收。
- [x] √ `git diff --check` 通过；按纯文档规则不运行 L1–L4，不调用模型，不读取凭据文件；无 mock 或真实模型测试。原有 `.zcodeignore`、`docs/INTERVIEW.md` 保留未读取、未暂存。

交付仅正常本地文档提交，具体 hash 以本节 Git 历史及交付回复为准；Agent 不 push、Release 或重建安装包，后续推送由用户决定。指南反映上述基线，不承诺后续源码变动后自动同步；业务验证限制沿用对应模块记录。
