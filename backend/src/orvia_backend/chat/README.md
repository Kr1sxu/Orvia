# M10–M20 会话与桌面任务应用服务

## M20 统一自然交互与真实结果流

`coordinator.py`接收固定`chat.natural({id,request_id,text})`，无需用户先选文件/网页/文档模式。明显目录枚举、文件名搜索、空间和原文检索由程序直接呈现；歧义或其他自然语言由该Mission固定Main返回有界类型化步骤，不自动上传证据正文。只发送用户指令、同会话有界用户上下文和有效资料元数据。复合请求最多4步，依赖已有/已计划的综合回答，不重复生成；超额须澄清拆分，不截掉目标。裸网址或仅提及链接不构成访问意图。普通概念解释不强制要求附件。文件名、资料、网页和模型结果均不能授予权限。

`chat.continue({id,request_id,continuation_id,answer?})`一次性接续已保存原请求：目录或资料原生选择成功后无需重发文字。暂停先落库并释放会话锁；接续在同一会话锁中检查token和当前事实，内部直接调用业务方法，不重入`handle`。歧义只补必要信息，资料候选可用当前有效证据ID或准确名称；同名版本须选ID。取消、切换会话、重启/重连使旧接续失效，不能串任务或自动重放。每个实际工作阶段50秒总预算，单模型30秒等待、20秒网络、0重试；意图理解/普通回答1024输出token，M15结构化证据回答保持原有4096输出token（流式与另行确认非流式相同）。用户等待资料/审批不计工作时间，已审批文件写事务不被外层计时器取消。

独立`m20_materials`有效集合最多3份、单附件10MiB/合计30MiB；单文件本地解析继续M13的45秒/50单元/8000字边界，父请求在一批全部返回后才显式接续。解析可取消，失败状态明确，原文件不修改。`chat.material.remove({id,kind,evidence_id})`仅解绑有效集合，保留原文件、历史证据和引用；当前检索、正文生成都排除已移除版本。旧会话一次性映射最近3份已保存版本作为有效资料，不重新读取原路径或访问网页；历史20项目录与按ID回查保留，移除后不会重新激活。原文引用或旧文件名不恢复父目录权限。`chat.revoke({id})`撤销后续目录读取，已发现清单可继续离线回查。

M15正文发送仍必须准确预览和原生确认；M16简报只从真实已保存的带引用回答预览/保存；M17草稿与清理、M18脚本/UIA/浏览器分别暂停在原有独立原生权限/审批入口。workflow中只有有界业务输入，无自由方法、批准字段、绝对用户路径或执行器。子业务用独立幂等请求，接续父请求只核对基线之后同会话、同来源/消息/操作ID的真实已保存结果和M18核验账本，不接收renderer自述成功。未知副作用不自动重试。

网页步骤的`input.success_rule`固定有限的控件动作、外发类别、准确origin及本轮创建时间。“填写并发送消息”需要本轮fill读回和message实际外发，不会在填写局部核验后声称发送完成。后端按真实M18操作账本验证，外发还需同类别/站点的原生批准摘要、对应正文SHA256、2xx回执、响应/页面/期待文本SHA256与新期待文本匹配；仅HTTP成功、旧会话事实、错站点或未批准请求均不能接续。核验仍不证明远端业务语义或交易结算，未知结果需人工核对，不重放。

桌面“输入…然后点击…”编译为两个步骤，同原请求分别建立一次性token和新消息/操作创建基线、分别原生选择与批准；每步只核对本轮新M18账本的准确action、local类别、真实verification及明确输入SHA/点击目标名。M18后台先提交终态账本再追加会话摘要，接续直接核验账本，不依赖较晚出现的摘要消息；不因此重试动作。填写成功不能完成后续点击，旧步骤事实和错误值/按钮均不能推进。程序识别连接词和动词时屏蔽代码围栏和字符串数据；Python正文或待输入文字内的“然后点击”等不会添加任务步骤。意图理解与普通回答实际显式输出预算均为1024token，适配器256默认值不是业务上限。

`scans.py`复用Computer授权和PathPolicy：默认所选根第一层，明确递归默认3层、最多8层；每次最多5000已访问项、10秒扫描墙钟总耗时（包含SQLite保存与流式背压等待）、4MiB已发现清单。批次输出后到限即停止访问下一条；外层50秒工作阶段仅给取消/落盘/退出留裕度，不扩扫描范围。真实批次最多40条/12KiB，先保存SQLite再发布；分类仅依据扩展名/目录属性，不冒充正文理解。最终`directory_result`消息直接给条目、范围/深度、已访问/发现/展示数量、分类、不可访问与截断；`chat.scan.page({id,scan_id,offset=0})`最多100项/48KiB，用实际返回数接next_offset，覆盖全部已发现条目。分页读取不可变已发现快照，不重扫磁盘、不把尚未扫描范围称全部。

扫描批次提交、事件seq提交和历史回答插入是不同事务，存在“已保存条目尚未发布/写入历史”窗口。重启或失败后`chat.get`按scan_id幂等补一条已发现前缀的`directory_result`历史入口（partial/recovered标记、完整已发现分页），并明确中断/截断；不重扫、不重发旧事件、不恢复授权或接续原请求。并发读取与再次重启不会重复补消息；仍执行中的请求不提前补终态历史。输出管道失败立即停止扫描，不能当作不可访问目录跳过后继续。

`streaming.py`生成固定`chat.stream`事件（会话/request/stream UUID、递增seq、kind、受限payload），stdio只补运输请求身份。类型为started/tool_status/scan_batch/model_delta/paused/completed/failed/cancelled。seq与状态先持久化，暂停接续复用同一stream_id；快照返回最后实际状态。M15子请求的事件只使用子运输身份，更新父等待信息只落库并经返回快照呈现，禁止混用父子事件破坏严格协议。`chat.get`和分页读取不等待长模型锁。

模型增量来自固定Main真实SSE，仅解码顶层answer为临时文字；每次真实前缀和seq在同一UPDATE中先落SQLite，再等待事件输出，完整结束后才校验JSON/引用并保存成功回答，无定时伪打字。前缀最多16000字且JSON编码24KiB，超限前拒绝继续追加/显示，已显示部分完整保留；适配器SSE的64KiB输出限制独立。失败、取消、暂停或重启只恢复一个幂等`model_partial`历史记录，data含request_id/stream_id/last_seq/state/text/provisional，明确为未核验事实且不能作为synthesis或制作成品；公开stream metadata不重复返回内部model_text。不重放旧事件、模型或目录权限。固定模型断流/不支持可另行原生确认一次同模型非流式请求，可能再次计费；routing/普通回答使用固定`chat.fallback.confirm`，M15只能重新确切片段预览/原生生成审批并显式`confirmed_nonstream`。批准在调用前一次消费，失败也不能重复使用；取消/未知浏览器或桌面结果不走此降级。

成功答案保存时关联request_id和已校验stream_prefix_chars。若完整结果/请求终态已落库但completed事件尚未输出，重启按已保存请求成功事实修正流metadata，seq不增长、不补发事件；已保存答案不会再误报为“未核验”partial。复合请求尚有后续步骤时，只保留已校验边界之后的新未完成文字，父workflow仍中断且不能自动接续。

收到合法SSE结束后，先核对真实finish_reason/tool_calls，再完成JSON/引用校验。length明确记为GENERATION_TRUNCATED及实际业务输出预算截断（M15为4096，普通回答为1024）；stop但JSON未闭合/结构非法明确记为INVALID_GENERATION，不把格式失败说成供应商超时或不可用。两者只保留未核验前缀，不保存成功回答、不自动降级或重试。

运行：`npm run build`、`npm start`，输入“列出目录”→＋原生选目录→原请求接续→批次与完整清单；输入“总结这份附件”→＋选资料→本地解析→确切正文预览/原生确认→临时真实增量→带引用保存结果。设置中的固定三角色与safeStorage保持。

测试代码在`backend/tests/test_m20_natural.py`、`test_m20_model_stream.py`，stdio/Electron由集成和E2E目录提供。`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m20_natural.py backend/tests/test_m20_model_stream.py -q --basetemp=artifacts/test-results/M20/backend-final-temp --junitxml=artifacts/test-results/M20/backend-final.xml`。全部日常验证使用合成目录、真实SQLite、异步模型/网络替身；实际命令、最终结果、真实供应商流与安装版证据须分别查PROGRESS，mock通过不等于模块完成。

已知限制：有界浅层/递归扫描和扩展名分类不保证全盘或语义理解；源文本/M06关键词检索仍有提取与召回限制，结构化引用不证明语义真值。通用聊天由模型生成，明确与工具事实分开。M18只支持既有受限任务，目标/控件/业务核验仍需原生明确选择，不能由意图开放通用执行或个人浏览器。历史列表裁剪不会删除账本；暂停和部分结果不等于恢复授权或继续执行。

M18新增`ChatService.automation`，固定`chat.automation.*`由Application分发，open初始化单独SQLite状态账本，close先回收自有脚本/UIA/浏览器资源再关数据库。长动作立即返回步骤身份；控制/状态/待外发审批可旁路普通串行请求，避免执行等待未来审批死锁。消息kind=automation只放身份/hash/核验摘要，排除在Main text规划上下文。脚本、桌面与站点分别原生授权，不继承目录或旧文件审批；结构、输入输出、固定模型、示例和限制见[automation README](../automation/README.md)。

## M17 代码草稿、原型和清理接口

新增固定 `chat.development.context/generate/draft/apply` 与 `chat.cleanup.scan/plan/execute/restore`，共用会话身份、SQLite 串行锁和消息历史。代码上下文可显式选择当前授权根内文件、M12/M13 不可变来源片段及一条 M15/M16 已保存结果；需求与选择绑定 revision，固定 Computer 只产出待审批草稿。写入由 main 原生确认每个文件，后端再次核对草稿和现场。清理扫描不要求项目目录授权，但只由当前 Windows 账户已知 Temp 根确定，执行前按扫描版本和逐项身份复核，同卷隔离后可在 30 天内受限恢复。生成代码不进入 Main 文件规划，不执行；外部资料不授予权限。完整契约、预算、运行、测试及限制见 `../development/README.md` 和 `../cleanup/README.md`。

## M16 已保存回答的成品接口

`chat.publication.preview/save` 只接受当前会话一条 M15 `synthesis` 消息 ID、固定格式、用户编辑的标题/摘要/结论文字；来源类型与引用由历史结果确定，renderer 不能改写。预览返回结构页面及来源 revision，保存重新计算并匹配版本，经主进程原生框取单文件新路径、M13 Computer gateway 独占写入与读回核验。请求复用 100 次会话预算、幂等和中断事实；成品记录只含文件名/格式/版本，不保留绝对保存路径。M16 本身无云模型调用，文字修改后引用仍需人工语义复核。格式、排版与测试见 `../publication/README.md`。

## M15 生成式证据回答

`synthesis.py` 从当前会话显式选定的 1–3 个 `document/browser` 不可变版本组装有界证据包；文档按页/段/幻灯片单元切块，网页按正文切块，问答复用 M06 FTS 命中。`chat.synthesis.preview({id,mode,question,sources})` 只读返回确切拟发送片段、覆盖与 SHA256 revision，不调用模型。`chat.synthesis.generate` 另需 request_id/revision；主进程只接受最近实际预览的同一输入，重算版本并弹原生正文发送确认。后端再核对版本，调用该 Mission 固定 Main 一次，不提供工具。会话生成消息持久化回答、结论类别、引用版本与定位、覆盖、模型及用量；同一请求不重复调用，中断/取消不重放。资料中的指令不会进入文件任务的 `text` 历史或取得授权。

每源最多3个600字片段，最多5400字正文；模型20秒网络超时、30秒本轮等待、4096输出token、0自动重试，M20流式与另行确认非流式均保留M15既有预算。输出必须是 `answer` 与 `claims` 的 JSON；`fact/inference` 需有本轮引用，`conflict` 需两个，`unknown` 不带引用。结构校验不等于事实核实。原文截断、缺失与 OCR 风险通过 coverage 返回。输入与输出无绝对路径、密钥和任意写操作；每会话100次请求预算沿用。示例：在当前会话保存文档和网页 → 选版本与问题 → 预览片段 → 主进程确认 → 查生成卡片及证据详情。源码试用需 `npm run build`、`npm start`；旧M14安装包不含M15后续能力，M20完整候选包版本和验收事实以PROGRESS为准。

测试：`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m15_synthesis.py -q`、`npx vitest run apps/desktop/tests/m15-contracts.test.ts tests/integration/m15.test.ts`、构建后 `ORVIA_TEST_MODULE=M15` 与 `ORVIA_TEST_RESULTS=artifacts/test-results/M15` 下运行 `npx playwright test tests/e2e/m15.spec.ts`。以上均用合成数据及模型 mock；显式 `backend/tests/live_m15_synthesis.py --run-live` 才在当前测试进程读取根开发 Key 并调用真实固定 Main，输出仅状态和用量。结果目录 Git 忽略。长文采样不是全文摘要，旧 M06 AND 关键词检索可漏召回，模型可产生语义错误；M15初版没有流式输出，M20已增加真实SSE临时答案和最终完整引用校验，仍不自动检索全部资料。

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

## V3-001 按需工作区与历史入口

用途：普通聊天聚焦消息，只有当前工作流或当前会话已保存事实才显示对应代码/清理/脚本/桌面/浏览器区域。`renderer/workspace-state.ts`由快照计算可见性；`M17Cards`/`M18Cards`接收明确的`visible`属性。主页面按会话ID挂载，未挂载M18时不发账本IPC。工作流预览在局部忙碌解除后重新核对未消费身份，每个token只准备一次。

现有`chat.get`等快照增加可选`workspace_history`：`development=null|{draft_id,kind}`、`cleanup=null|{plan_id}`、`automation=[]|[script,desktop,browser]`（至多3类）。后端在既有SQLite锁内按会话查询，最多返回最近一个草稿/清理计划身份；输出无根路径、源码、权限。消息裁剪不影响这些入口，旧快照仍可根据程序消息身份显示。读取历史由既有身份校验接口处理，不改变审批和跨会话限制。

简单寒暄仅完整匹配固定集合后本地回答，例如“你好”“谢谢”“好的”“继续”；带任务的句子仍走原路由，等待授权/审批的任务不会被肯定语推进。没有新增依赖、凭据、网络或模型配置。启动`npm run build`、`npm start`；新会话问候后无工作区，再明确提出“生成 React 页面”并授权项目后显示代码区；“清理旧临时文件”显示清理计划；历史脚本只读账本不能代替批准。

验证入口：`apps/desktop/tests/v3-workspace.test.tsx`、`backend/tests/test_v3_workspace.py`、`tests/e2e/v3-workspace.spec.ts`；原M20业务E2E复用真实Electron/stdio/SQLite/LPAC/UIA/Chromium及合成模型和原生框。结果在`artifacts/test-results/V3-001/`，精确命令与结论见`docs/PROGRESS.md`。

限制：M17较早历史仍依赖现有消息可见范围，新增投影只保留最近草稿/清理计划；M18账本仍最多最近20条。内存预览不承诺跨重启恢复，权限不恢复、不自动重试或执行。旧M17/M18手工入口E2E已被M20自然入口业务验收取代；安装包未重建，本修复仅源码开发版。

## V3-003 会话管理
用途与结构：`repository.py`追加置顶/更新时间、原位迁移与改名；`management.py`负责删除阻塞检查、永久清理及中断收尾；`agents/graph.py`清除属于会话的全部历史checkpoint。无新依赖、环境变量或模型调用。

公共接口：`chat.pin({id,pinned})`、`chat.rename({id,title})`返回正常快照；`chat.delete_check({id})`返回`{id,title,blocked}`，`chat.delete({id})`返回`{id,deleted:true}`。后者只由Electron原生确认后的私有管道调用，检查全部任务历史和后台收尾任务，不使用最近20项投影代替权限检查。未知状态、待审批（包括未批准代码草稿）、仍开的Browser会话、未恢复隔离文件均阻止删除。私有脚本目录仅允许UUID直接子目录，拒绝祖先及内容中的重解析点；不触碰用户原件、导出成品或执行回滚。

清理覆盖会话消息/请求、浏览器与文档证据、检索索引/偏好/摘要、任务及条目、草稿、流和扫描资料、checkpoint以及脚本输入输出私有副本。先落删除进度标记，旧ID随即不可访问；跨库或文件中断会在重启后幂等继续清理，失败不报告成功。仅保留ID与进度，无正文审计。不是磁盘取证擦除，不清除外部备份；文件系统预检不能消除外部进程恶意替换路径的全部竞态。无法安全清理时关闭能力，不自动重放任务。

运行沿用应用入口`npm start`；例如对无未完任务的历史会话在更多菜单确认删除。测试：`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v3_management.py backend/tests/test_chat.py backend/tests/test_v3_workspace.py -q --junitxml=artifacts/test-results/V3-003/backend-final.xml`。真实临时SQLite和checkpoint、合成文件及故障注入，真实模型0；不使用用户资料。界面与IPC测试见desktop README。
