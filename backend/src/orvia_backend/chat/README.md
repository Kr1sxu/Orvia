# M10–M17 会话与桌面任务应用服务

## M17 代码草稿、原型和清理接口

新增固定 `chat.development.context/generate/draft/apply` 与 `chat.cleanup.scan/plan/execute/restore`，共用会话身份、SQLite 串行锁和消息历史。代码上下文可显式选择当前授权根内文件、M12/M13 不可变来源片段及一条 M15/M16 已保存结果；需求与选择绑定 revision，固定 Computer 只产出待审批草稿。写入由 main 原生确认每个文件，后端再次核对草稿和现场。清理扫描不要求项目目录授权，但只由当前 Windows 账户已知 Temp 根确定，执行前按扫描版本和逐项身份复核，同卷隔离后可在 30 天内受限恢复。生成代码不进入 Main 文件规划，不执行；外部资料不授予权限。完整契约、预算、运行、测试及限制见 `../development/README.md` 和 `../cleanup/README.md`。

## M16 已保存回答的成品接口

`chat.publication.preview/save` 只接受当前会话一条 M15 `synthesis` 消息 ID、固定格式、用户编辑的标题/摘要/结论文字；来源类型与引用由历史结果确定，renderer 不能改写。预览返回结构页面及来源 revision，保存重新计算并匹配版本，经主进程原生框取单文件新路径、M13 Computer gateway 独占写入与读回核验。请求复用 100 次会话预算、幂等和中断事实；成品记录只含文件名/格式/版本，不保留绝对保存路径。M16 本身无云模型调用，文字修改后引用仍需人工语义复核。格式、排版与测试见 `../publication/README.md`。

## M15 生成式证据回答

`synthesis.py` 从当前会话显式选定的 1–3 个 `document/browser` 不可变版本组装有界证据包；文档按页/段/幻灯片单元切块，网页按正文切块，问答复用 M06 FTS 命中。`chat.synthesis.preview({id,mode,question,sources})` 只读返回确切拟发送片段、覆盖与 SHA256 revision，不调用模型。`chat.synthesis.generate` 另需 request_id/revision；主进程只接受最近实际预览的同一输入，重算版本并弹原生正文发送确认。后端再核对版本，调用该 Mission 固定 Main 一次，不提供工具。会话生成消息持久化回答、结论类别、引用版本与定位、覆盖、模型及用量；同一请求不重复调用，中断/取消不重放。资料中的指令不会进入文件任务的 `text` 历史或取得授权。

每源最多3个600字片段，最多5400字正文；模型20秒网络超时、30秒本轮等待、1024输出token、0自动重试。输出必须是 `answer` 与 `claims` 的 JSON；`fact/inference` 需有本轮引用，`conflict` 需两个，`unknown` 不带引用。结构校验不等于事实核实。原文截断、缺失与 OCR 风险通过 coverage 返回。输入与输出无绝对路径、密钥和任意写操作；每会话100次请求预算沿用。示例：在当前会话保存文档和网页 → 选版本与问题 → 预览片段 → 主进程确认 → 查生成卡片及证据详情。源码试用需 `npm run build`、`npm start`；M14安装包未更新。

测试：`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m15_synthesis.py -q`、`npx vitest run apps/desktop/tests/m15-contracts.test.ts tests/integration/m15.test.ts`、构建后 `ORVIA_TEST_MODULE=M15` 与 `ORVIA_TEST_RESULTS=artifacts/test-results/M15` 下运行 `npx playwright test tests/e2e/m15.spec.ts`。以上均用合成数据及模型 mock；显式 `backend/tests/live_m15_synthesis.py --run-live` 才在当前测试进程读取根开发 Key 并调用真实固定 Main，输出仅状态和用量。结果目录 Git 忽略。长文采样不是全文摘要，旧 M06 AND 关键词检索可漏召回，模型可产生语义错误；没有流式输出和自动检索全部资料。

## M13 文档请求

新增 `chat.document.attach/source/ask/preview/export`，完整契约、预算和示例见 `../documents/README.md`。ChatService持有DocumentStore，复用会话锁、100次请求预算、幂等占位和重启中断记录。新消息种类document_request/document/export均不会进入Main的text指令历史；附件正文与网页一样不能授权、审批或成为模型文件规划指令。

attach的单文件path与export的目标path只来自可信主进程原生选择器，请求摘要用于幂等且不将绝对路径写入数据库。目录授权不变，附件读取不自动创建文件计划。导出先预览、主进程一次性匹配、再保存框确认，后端重新核对revision并独占新建，不覆盖、不重放；成功/拒绝都记录在同会话。snapshot.documents最多20个短摘要/8 KiB，整体仍46 KiB，完整有界文本按来源详情获取。

本模块把对话、Computer 只读观察、LangGraph 计划、独立审批和动作账本连接起来。M12 增加只读 Browser 来源流程；没有自动任务、技能广场、插件或任意执行入口。

## 结构与公共接口

- `contracts.py`：私有 IPC 请求和模型提案白名单；未知字段拒绝。
- `repository.py`：在应用 `app.sqlite` 中维护会话、消息及请求去重表，复用 Store 的串行数据库锁。
- `__init__.py`：`ChatService.handle(method, params)`；由 Application 初始化并调用，不单独监听端口。

`chat.create({client_request_id,title})` 幂等创建一对一 Mission 会话；`chat.list({})` 返回最多 100 个会话；`chat.get({id})` 返回快照。`chat.send({id,request_id,text})` 接收最多 2000 字消息。`chat.grant({id,root})` 的绝对根只允许可信主进程从系统选择器提供。`chat.inspect({id,tool,arguments})` 仅允许列表、文件名搜索、属性、空间统计。`chat.approve/resume/undo({id,operation_id,revision})` 必须来自独立用户按钮，绑定最新计划摘要和当前根授权。

快照含 `id/title/mission_id/messages/grant/operation/messages_truncated`。消息有角色、文本、种类、数据和时间。授权输出只含目录名和 token，不输出绝对根；每次快照重新核对根身份，已替换目录的授权显示失效。操作输出相对源/目标、状态及 SHA256 revision；历史计划消息保留该安全投影，执行结果保留逐项核验布尔证据，不包含内部根和身份数据。最近 30 条消息再按 46 KiB 裁切；较早记录仍存于数据库，`messages_truncated=true` 明示省略，当前不提供历史分页接口。只读消息递归裁剪 `data` 内列表至 8 KiB，保留错误并明确标记不完整。

## 模型与权限

会话 Mission 固化三个角色配置；M10 规划只调用该 Mission 的固定 Main 模型。Computer 是受限程序工具执行器，本轮不调用其模型，Browser 在 M12 提供只读网络工具，来源追问使用本地检索，不调用 Browser 模型。缺失 Main 凭据时给出明确错误，禁止回退供应商。凭据由既有 Electron 私有初始化传入内存，本模块不读取环境文件。

模型收到用户最近有界对话和当前授权的必要文件元数据，不读取文件正文。`propose` 提案允许 `answer/inspect/plan`：只读由 M03 契约与 gateway 执行；计划由 M04/ LangGraph 生成并暂停，聊天文字不能批准。模型文本统一标成建议，不作为完成证据。实际完成由程序核验结果卡片表示。

每次发送最多 3 次模型请求、模型等待合计预算 50 秒、每次 1024 token；单会话最多 100 个发送请求，网关另限制 200 次只读调用。请求标识及 `pending/completed/failed/cancelled/interrupted` 状态先持久化去重，正常回复落盘后才标记完成；重启为未完成请求追加明确中断消息，不自动重放。相同标识重试未完成请求返回 `REQUEST_INTERRUPTED`，用户检查现有结果后用新消息继续。会话锁串行化计划与审批；新计划使旧审批失效。重启丢失目录授权，恢复与撤销都需重新授权原根并通过动作身份检查。

## 运行与测试

随桌面应用启动，或由既有 stdio Application 协议调用。示例：创建会话 → 选择合成目录 → 发送“把 a.txt 重命名为 b.txt” → 查看只读观察与逐项计划 → 独立批准 → 程序核验 → 最近任务受限撤销。

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_chat.py -q --basetemp=artifacts/test-results/M10/chat-temp --junitxml=artifacts/test-results/M10/chat.xml
```

日常测试全部使用临时数据库、合成文件与模型 mock，不读取用户文件、不读取开发凭据、不调用真实模型或 Tavily。覆盖幂等、缺钥、路径越界、模型提案拒绝、会话隔离、审批版本、重启授权、恢复、撤销、结果体积和请求预算。真实模型的自然语言质量仍需单独显式合成验收；本模块不实现目录外操作、删除、任意脚本或浏览器写操作。


## M11 取消、历史和故障边界

`chat.cancel({id,request_id})` 返回 `{cancelled:boolean}`。仅会话及请求标识都匹配、且当前正在等待模型时接受取消。取消模型等待后写入取消消息和 `cancelled` 请求终态；相同请求重试返回已有结果，不重新付费调用。计划入库、审批、文件执行和撤销没有取消入口，按钮收到 `false` 时应刷新当前事实。总超时也只包围模型等待，不中断 SQLite 或 LangGraph 的事务步骤。

会话列表和快照增加 `status`：`draft/running/awaiting_approval/completed/failed/interrupted/cancelled/undone/partially_undone`。快照 `operations` 返回最近 10 个任务的 `operation_id/revision/status/created_at/updated_at/can_undo` 摘要，`operations_truncated` 表示还有更早记录；不返回根路径和身份信息。当前 `operation` 增加 `can_undo`，只有最近已完成任务且仍授权原根才显示入口，实际撤销继续由 M04 做身份核验。审批详情保留在当前计划及有限消息中，历史摘要不是可执行的旧审批入口。

stdio 普通请求继续串行，最多积压 32 项；只有经过完整参数校验的健康检查与取消旁路，响应按请求 ID 配对。后端退出后 pending 标为 interrupted，授权失效，绝不重放发送、审批或文件变更。SQLite busy/locked/full 和磁盘权限/空间故障只返回固定 `STORAGE_BUSY/STORAGE_FULL/PERMISSION_DENIED/STORAGE_UNAVAILABLE`，不输出异常路径、SQL、网络地址或凭据。用户需要显式重试，程序不自动重复写操作。

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m11_stability.py backend/tests/test_server.py backend/tests/test_chat.py -q --basetemp=artifacts/test-results/M11/stability-temp --junitxml=artifacts/test-results/M11/backend-stability.xml
```

M11 故障测试注入网络不可用、超时、数据库忙/空间不足、磁盘满及权限错误，取消测试使用等待事件的模型 mock；无真实模型、Tavily 或用户文件访问。阶段状态不是逐 token 流式响应；原生文件操作与外部进程的路径替换仍受原有系统竞态限制。

## M12 来源请求与恢复

`chat.browser.search/read/ask` 分别校验 BrowserSearch/BrowserRead/BrowserAsk，均绑定会话 UUID 和 request_id；source 详情接口校验会话 UUID 和64位十六进制 evidence_id。它们复用同一会话锁和100次请求预算，创建 pending 占位后再联网，终态 completed/failed。相同请求不能改变方法或参数；中断请求需新标识，重启不重放网络请求。

消息新增 source_request 与 source，两者均不作为 Main 文件规划的指令历史。source 只携带最多5个证据短摘录，正文独立持久化并通过 `chat.browser.source` 获取；snapshot.sources 是最近20个证据版本且预算12 KiB，sources_truncated 明示省略。仍先保留当前事实，整份快照46 KiB。网页不能扩大目录授权、生成文件动作或审批。

`browser/evidence.py` 保存不可变版本和 M06 索引，details 按会话重新检查归属。ask 只返回当前会话命中的最多5个原文片段，包含引用 ID、URL、标题、访问时间及块号；不会把搜索摘要说成已读取全文，也不将检索命中说成模型结论。无命中明确提示，无模型/搜索凭据也可本地检索。

来源保存和 FTS 写入是分别提交的事务；存储异常会保留 pending/中断事实和已保存证据，不伪造索引成功。用户可从来源目录读取证据，明确重新读取相同来源会修复该版本的索引；没有自动网络重试或数据库恢复式联网。

运行/测试沿用服务入口；`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m12_browser_chat.py -q` 使用合成网络、临时 DB，覆盖去重/版本、隔离、重启、请求幂等、错误、预算和中断；报告路径须指定 M12。模块不含全文导出、文档附件或 Browser 生成式问答。
