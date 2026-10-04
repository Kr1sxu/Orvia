# Electron 桌面模块（M20 源码）

## M20 统一自然语言与真实结果流

默认输入为“你想做些什么”，不再预选文件／网页／检索模式。`chatNatural`只发送会话、请求UUID和用户文字；后端决定有界步骤，必要对象不唯一时只澄清对象。目录查看直接按真实条目和扩展名分类回答，注明未读正文；`chatScanPage`读取同一已保存扫描快照，每批至多100项，按返回的实际offset继续，长路径字节预算可减少单页条目数。完整入口只表示本次实际发现条目，不冒充所有层级或全盘扫描。

单一“＋”菜单支持键盘与Escape，分别打开主进程原生文件／文件夹选择器。一次最多3个文档／图片，每个10 MiB、合计30 MiB；逐文件显示等待、解析、失败或取消。选择附件不授予父目录或云端正文发送权限。移除只解除有效资料关联，保留原文件、提取历史与引用；目录另有撤销授权。资料变更使待发送预览失效。先发需求再添加必要资料时，当前请求通过一次性continuation接续；取消选择、切换会话、重启或重连不会自动重放。历史请求可在核对现状后明确继续。

M15总结自动预览本次确切片段，用户仍须点击并原生批准；M16预填成品格式并经过内容预览和新文件保存确认。M17预填代码／原型需求、明确上下文并先计算预览，生成草稿、逐文件写入或旧临时文件隔离仍独立批准。M18从自然请求预览粘贴／原生单选.py／固定Computer草稿，桌面与浏览器分别提示准确目标和必要核验信息；实际LPAC、UIA或专用Chromium步骤完成后，后端依据保存事实推进原请求，renderer不提交成功布尔字段。打开工作区或预填内容本身不是任务完成。

结构：`m20-contracts.ts`定义strict自然输入、接续、资料、分页与事件；`main.ts`保持串行业务并允许历史快照／分页／取消／流消费只读旁路；`preload.ts`只提供固定方法。`AddMaterialMenu.tsx`负责资料菜单，`M20Results.tsx`负责直接目录回答和暂态文本，`m20-state.ts`负责会话／请求／流／序号核对。原M19字体、图标、颜色和原生窗口规范继续复用。创建会话按视图epoch拒绝过时回包；paused允许同请求后续顺序事件，不复活真正终态或协议错误。流队列最多20项，paused仅拉取主进程缓存，不自动重放业务。

事件由真实扫描批次或供应商SSE产生，含会话、业务请求、传输请求、流身份和递增序号；每帧含换行最多12 KiB。main有界缓冲最多80事件／128 KiB，每次pull最多40事件／48 KiB，ACK仅释放运输内存，不授予权限。renderer每50ms单次消费轮询，跨会话也排空所属请求，父请求暂停和模型子请求分别保留身份。模型文本暂时标为“引用待校验”；完整JSON和引用未核验时没有成品入口。取消、超时、断线或格式失败的部分内容只供核对，不自动重试。固定Main流式不兼容时，明确原生确认同模型非流式新请求及可能重复费用；不切换供应商或模型。

逐会话草稿可在任务中编辑；历史和新对话可切换。后台更新不focus输入，不覆盖草稿；历史首次打开从顶部阅读，随后恢复该会话已记录的scrollTop，增量和终态不强制滚底。用户明确发送新需求或点“查看最新消息”才重新跟随。中文IME候选确认和Shift+Enter继续受保护。重载只读取持久事实与主进程活动状态，不恢复自动接续或业务发送。

M18新需求清除上次工作区的展示事实和原生目标，但历史账本保留。脚本结果必须匹配本次预览绑定的operation_id，浏览器结果必须匹配本次原生授权session_id；旧异步轮询不能覆盖新脚本事实。发送类网页需求还要求实际另批请求、2xx回执和新页面文字核验，填写控件的局部verified不能代表消息已发。生成草稿和真实结果在workflow推进后仍展开，方便继续审查、逐文件批准或回传。清理原生取消消耗旧预览授权，需重新读取同一计划后再明确批准。

无相关步骤或当前已读回事实时，“脚本、桌面与浏览器执行详情”默认收起，可显式展开使用既有入口；自然语言M18步骤、审批与真实结果自动展开。M15手工资料版本选择同样作为可展开详情，确切发送预览仍直接呈现。用户跟随最新消息时优先看到真实回答／成品或当前增量，待批准的后续步骤保持可见；这些更新不抢焦点或改变历史阅读位置。

综合回答的引用／成品入口在本地任务忙碌或离线时禁用，避免已展示结果的点击被串行保护静默丢弃。主动点击引用后，仅在同会话成功回包时将证据详情一次滚入阅读区并停止自动跟随；不focus输入，其他会话旧回包不改变当前视图。

用户显式原生批准成品保存成功后，仅将该会话本次新核验结果一次滚入阅读区；即使刚阅读引用详情也可立即核对成品。此动作不恢复后台自动跟随，后台完成或另一会话回包不改变阅读位置。

模型流中断、失败或取消后的真实有界前缀作为`model_partial`历史读取，明确标注未核验／不可成品。同一流只保存一条，不当成功回答或M16来源，也不会在重启后自动重发。桌面执行原生批准返回的`running`只表示实际任务已启动；必须等待绑定本次预览operation_id的真实账本completed与核验证据，再接续原需求。

主要固定接口新增：`chatNatural`、`chatContinue`、`chatFallbackConfirm`、`chatAddFiles`、`chatMaterialRemove`、`chatRevoke`、`chatScanPage`、`chatStreamPull`、`chatStreamAck`。均拒绝renderer提供路径、方法名、模型覆盖或批准字段；原生审批和后端再校验继续使用既有M15–M18入口。旧固定`chatSend/Browser*/Document*`保留兼容，不能作为默认技术模式。

开发试用：根目录`npm run build`、`npm start`；发送“看看这里有哪些文件”→“＋”选择授权文件夹→查看直接条目／完整清单；发送“总结这份文档”→添加合成附件→核对发送片段→原生确认→查看增量和最终引用；再说“把刚才回答制作Word简报”→预览→保存新文件。写操作、执行、外发仍有各自原生批准。日常测试仅合成资料、mock SSE／网络；供应商真实流、原生选择框外观、人工IME和安装版证据分别记录，不把目标单元或构建通过称完整验收。

目标L0：`npm run check`。L1：`npx vitest run apps/desktop/tests/m20-contracts.test.ts apps/desktop/tests/m20-stream.test.ts apps/desktop/tests/m20-ui.test.tsx`。L2/L3与安装对照在`tests/integration/`、`tests/e2e/`整合；`m20.spec.ts`覆盖基础对话，`m20-business.spec.ts`覆盖自然文件计划、代码／原型、隔离清理、脚本和网页写任务。测试启动器仅替换合成凭据、模型／网页网络和原生选择／批准，真实Electron、stdio、SQLite、文件核验、LPAC与专用Chromium仍运行；runtime-parity独立验证实际安装资源，不替换冻结后端。日志和报告在被忽略的`artifacts/test-results/M20/`，准确命令、实际通过／失败和限制以PROGRESS为准。

M20功能、完整安装包对照与暂缓生产签名／独立Windows分别验收；M19定向包使用旧冻结后端，不能作为本轮全功能证据。旧M14包保持原状。本模块不会开放通用IPC、个人浏览器复用、任意路径／命令、管理员权限或后续业务。

## M19视觉升级（已完成）

用户已确认B雾蓝、B原创折帆、其余A：内置字体/Windows11 x64/原生圆角控制。`style.css`、`Visual.tsx`及原生窗口呈现模块已接入；复用所有React业务卡片、事件、IPC与原生审批。资源来源/许可、接口、生成、测试及限制见[资源README](resources/README.md)，设计取舍见[设计说明](../../docs/M19_DESIGN.md)。13项受影响产品流程、4档渲染倍率、实际组件状态、M18最小真实LPAC/UIA/Chromium闭环通过；用户授权桌面验收后，产品普通/还原/最小窗四角原生像素、最大化/全屏/贴靠和全部窗口控制通过。实际定向安装/升级/卸载、快捷方式及新任务栏分组已核验；失败修复、旧分组图标差异及证据见PROGRESS。上述M19验收产物保存在`artifacts/test-results/M19/`，当时零真实模型且M20尚未实施；本轮M20范围和验证独立见上文。

## M18 脚本、桌面与浏览器写操作

`M18Cards.tsx`在会话提供三项独立权限、完整计划、原生审批、执行事实/取消、产物回传和实际外发字段预览。`m18-contracts.ts`严格参数与预算，`m18-ipc.ts`只记录后端实际计划并核对会话/版本/有效期，绝对路径仅来自原生选择器；审批或源码不能由renderer伪造。preload静态21方法，没有方法名转发器或批准布尔字段。Application后端再次校验并持久化一次性状态；重连清空main授权，未知结果不重放。

脚本支持粘贴/.py/固定Computer草稿；桌面原生选普通应用再UIA单步，保存副本另选新路径；Browser原生确认准确站点/类别与专用内存登录，每个实际请求另批（动态GET/自动保存也暂停）。源码/页面只用React转义，敏感与截断预览明确标注。实例、后端结构、依赖与权限见[automation README](../../backend/src/orvia_backend/automation/README.md)。历史M19仅改变呈现与窗口资源；本轮M20复用这些权限接口并统一自然语言入口，验证分别记录。

验证：`npm run build`；`npx vitest run apps/desktop/tests/m18-ipc.test.ts apps/desktop/tests/m18-ui.test.ts`；设置`ORVIA_TEST_MODULE=M18`后`npx playwright test tests/e2e/m18.spec.ts`。实际LPAC/UIA/Chromium与替身模型/HTTP/原生确认分别记录在PROGRESS，不能当真实站点或原生系统确认视觉验收。

## M17 代码、网页原型与临时文件隔离

`M17Cards.tsx` 在会话内提供选定上下文预览、代码草稿完整差异、逐文件写入、React 受限原型预览、旧 Temp 文件逐项选择和受限恢复。preload 仅暴露固定 M17 方法，main 严格校验参数并在云端发送、逐文件写入、隔离和恢复前弹原生确认；renderer 不能指定清理路径或调用任意 IPC。模型和网页内容在 UI 中均为文本，预览不执行生成源码。示例与边界见根 README 和 `backend/src/orvia_backend/development/README.md`、`backend/src/orvia_backend/cleanup/README.md`。

验证：`npm run build`；`npx vitest run apps/desktop/tests/m17-contracts.test.ts apps/desktop/tests/chat-contracts.test.ts`；设置 `ORVIA_TEST_MODULE=M17`、`ORVIA_TEST_RESULTS=artifacts/test-results/M17` 后运行 `npx playwright test tests/e2e/m17.spec.ts`。E2E 真实运行 Electron、Python、SQLite 和合成文件写入；Computer 及原生确认由测试启动器 mock。

## M16 简报成品制作

在当前会话一条 M15 回答卡片点“制作 Word／PPT／PDF 简报”，编辑标题、摘要、结论文字并选择格式；后端返回内容与页面安排、完整引用。主进程保存最近一次预览输入和 revision；保存前复取版本，原生保存框只批准新建单文件。固定 preload `chatPublicationPreview/Save` 不接收模板、路径、来源或模型覆写字段。取消无写入；成功卡片显示文件名和读回核验，不展示绝对路径。Word/PPT 可继续编辑；PDF 内嵌离线中文字体。此流程不调用模型或改变 M15 正文上云确认，也不并入 M04 文件整理撤销。格式和限制见 `backend/src/orvia_backend/publication/README.md`；M14 安装包尚不包含 M15/M16。

验证：`npm run build`；`npx vitest run apps/desktop/tests/m16-contracts.test.ts apps/desktop/tests/m15-contracts.test.ts`；设置 `ORVIA_TEST_MODULE=M16` 和 `ORVIA_TEST_RESULTS=artifacts/test-results/M16` 后运行 `npx playwright test tests/e2e/m16.spec.ts`。E2E 的模型回答与原生对话框为测试 mock，Electron/Python/生成库/SQLite/文件写入真实运行。

## M15 证据选择与正文上云确认

当前源码新增“模型理解已保存资料”面板：只列本会话文档和有正文的网页证据，最多选3个版本；选择摘要或回答并填写最多300字的问题后，先预览后端决定的全部发送片段和覆盖。主进程保留最近一次预览身份，生成前重新向后端核对 revision，再弹原生确认框；取消不调用模型。新固定 preload 方法 `chatSynthesisPreview/Generate` 拒绝 renderer 提供路径、正文、模型或审批字段；后端仍复核会话归属。生成中复用忙碌状态和仅模型等待期取消，结果以纯文本卡片展示结构化引用并可回查原证据。例：添加合成DOCX → 勾选其版本 → 预览 → 原生确认 → 查看摘要与引用。M14安装器尚不包含此界面。

验证：`npm run build`，`npx vitest run apps/desktop/tests/m15-contracts.test.ts tests/integration/m15.test.ts`，设置`ORVIA_TEST_MODULE=M15`、`ORVIA_TEST_RESULTS=artifacts/test-results/M15`后运行`npx playwright test tests/e2e/m15.spec.ts`。E2E仅在测试启动器替换模型与原生对话框；产品保持固定 Main 调用与真实确认。正文上传有费用，片段式覆盖不能当全文核验；结构引用不能保证模型事实正确。上述M15阶段关键词检索为独立入口；本轮M20统一意图、检索与流式结果见上文。

用途：以对话完成授权目录观察、计划审批、执行核验与受限撤销。新建/历史会话在侧栏，中央消息流展示事实卡片，底部输入框持续提问，设置保留固定模型与凭据管理。不提供自动任务、技能广场、团队管理等入口。

## 结构

- `src/main/main.ts`：窗口、来源校验、系统目录选择及串行业务 IPC。
- `src/main/backend.ts`：私有 Python stdio 客户端；`chat-contracts.ts` 校验会话输入/快照，`chat-errors.ts` 提供固定中文错误。
- `src/main/credentials/`：开发凭据加载、发布 safeStorage 与后端同步，详见该目录 README。
- `src/main/preload.ts`：固定 contextBridge 函数；`src/shared/api.ts` 定义类型。
- `src/renderer/main.tsx`：欢迎页、会话、输入与异步状态；`ChatCards.tsx` 展示工具与计划证据，`SourceCards.tsx` 展示纯文本网页来源、引用与长文详情；`SettingsPanel.tsx` 管理凭据。

## 输入输出与公共接口

所有函数返回 `{ok:true,result}` 或 `{ok:false,message}`，错误不回显原始请求/供应商正文。

| preload 函数 | 输入与结果 |
|---|---|
| `chatList()` | 最多100条 `{id,title,status}` 历史会话 |
| `chatCreate({client_request_id,title})` | 幂等创建会话与固定 Mission |
| `chatGet({id})` | 读取会话事实快照 |
| `chatSend({id,request_id,text})` | 最多2000字，固定 Main 规划，返回新快照 |
| `chatCancel({id,request_id})` | 仅取消匹配的模型等待；返回 cancelled，不能取消写操作 |
| `connectionStatus()` | 主进程连接/忙碌状态及活动发送标识，无正文和路径；1秒轮询 |
| `reconnect()` | 空闲时明确重连，旧后端确认退出后才新建，不重放业务请求 |
| `chatChooseDirectory({id})` | 主进程系统选择器；取消无授权变化，成功返回会话 |
| `chatInspect({id,tool,arguments})` | 只允许列表、文件名搜索、属性和空间统计 |
| `chatApprove/Resume/Undo({id,operation_id,revision})` | 当前会话、根授权、最新计划及版本都有效才执行 |
| `health/settings/saveCredential/removeCredential` | 连接与固定模型设置，发布模式保存/移除加密凭据 |

旧 `missions/createMission` 与 M09 只读窄接口保留兼容；界面不再以草稿面板作为任务入口。没有通用方法转发、绝对根输入或任意命令接口。目录授权不包含文本读取/系统权限。M09 的开发测试目录环境变量入口已移除；E2E 只在测试启动器中替换模型与目录对话框。

## 配置与运行

依赖沿用根锁文件：Electron、React、TypeScript、Vite、Zod，无新增运行依赖。开发 Python 固定为 `backend/.venv/Scripts/python.exe`；发布使用安装资源，不回退系统 Python。开发数据默认 `.orvia/`，测试用 `ORVIA_DEV_DATA_DIR` 隔离；发布忽略该变量。

根目录运行 `npm run build` 后 `npm start`。示例：选择只含合成 `a.txt` 的目录 → 查看列表 → 发送“把 a.txt 重命名为 b.txt” → 核对源/目标与版本 → 独立批准 → 查看程序核验 → 必要时撤销最近变更。重新打开会话后必须重新授权原根。M10旧接口未授权时要求重新提交；M20默认自然入口保留原请求，当前视图成功授权后一次性接续。取消/切换/重启/断线不自动重放。

主动发送会把必要对话与文件元数据发送给固定 Main 云服务；不自动发送文件正文。开发主进程读根 `.env.local`，发布只用 safeStorage，不回退明文。输入的 API Key 提交即清空，不进入消息。

## 验证

L0：`npm run check`、`npm run build`。L1：`npx vitest run apps/desktop/tests/chat.test.ts apps/desktop/tests/backend.test.ts apps/desktop/tests/m11-contracts.test.ts apps/desktop/tests/m11-ui.test.ts`。L2：`npx vitest run tests/integration/m10.test.ts`。L3：先构建，设置 `ORVIA_TEST_MODULE=M11`、`ORVIA_TEST_RESULTS=artifacts/test-results/M11` 后运行 `npx playwright test tests/e2e/m11.spec.ts tests/e2e/m11-ui.spec.ts tests/e2e/m10.spec.ts tests/e2e/m09.spec.ts`。

报告、数据库和截图均在忽略的 `artifacts/test-results/M11/`；准确命令与结果见根 PROGRESS。E2E 保留真实 Electron/Python/SQLite/文件网关，以测试专用启动器替换模型和凭据来源，系统选择器用测试侧 mock；不触发真实模型。M10 已有的真实 Main 合成验证未重复执行；M11 不改变供应商配置。

## M11 稳定性试用

- 模型等待时点击“取消规划”，只有收到取消并落盘后才为取消终态。计划入库、审批执行、撤销不可取消，已完成的只读观察保留。再次发送同一请求标识不会重复调用模型。
- 后端退出或超时显示明确提示；“重新连接”先等待旧进程退出，失败时不启动第二个后端，不删除数据库。连接恢复后原目录权限失效，请重新选择并核对状态。正在处理时禁止重连，窗口关闭先发 EOF，1.5秒未退出则终止自有后端；4秒仍未确认退出时停止等待并拒绝重连。
- renderer 重载后读取主进程的活动请求事实，显示处理中及可用取消入口；不会再发送需求。侧栏状态随快照更新，最近10项操作历史仅供查阅。
- “重新尝试规划”只针对模型/消息中断错误，由用户发起新请求，可能产生新模型费用；审批、恢复和撤销没有自动重试。数据库忙/空间不足/权限错误显示固定中文证据，不展示内部路径、SQL 或供应商回显。
- 历史阅读不强制滚动；长消息及超过10项的文件列表默认折叠。Enter发送、Shift+Enter换行，中文候选确认不会误发；设置支持 Tab 焦点循环与 Escape，最小窗口760×560仍保留输入区。

## 权限与限制

sandbox/contextIsolation 开启，Node/webview 禁用，拒绝联网、导航、新窗口和权限申请。所有入口检查主窗口、顶层 frame、精确 URL、参数个数与结构；UI 单操作锁及后端会话锁避免重复提交。原始错误不显示，模型文本标为建议，程序卡片才代表执行事实。

私有 UTF-8 JSON Lines 每行64 KiB；会话请求65秒客户端超时，对应模型50秒总预算，最多三次请求，每次1024输出token；其他开发请求仍5秒，发布20秒。当前展示请求阶段，无伪造百分比或token流式输出。关闭中断不自动重放；历史快照不是执行恢复。

历史只显示最近30条并按46 KiB裁剪，较早记录仍保存，当前无分页。只读卡片8 KiB，截断明确提示。没有托盘、自动重连、通用取消或自动任务。M08安装包未随本轮重建。旧无身份快照计划拒绝审批；部分撤销/不确定中断需人工核对，不承诺任意回滚。外部进程并发文件竞态不能由路径检查完全消除。

## M12 会话来源

输入框的“需求类型”选择文件任务、搜索网页、读取网页或询问已有来源；新会话可直接搜索/读取，无需选择目录。搜索提示是否配置 Tavily，设置同步展示状态。来源卡片可展开、查看持久化证据或显式读取搜索结果网页；会话来源目录支持重开证据，长正文按需展开。URL/HTML/标题都是纯文本，没有远程导航或 HTML 渲染。

新增固定接口：
- `chatBrowserSearch({id,request_id,query,max_results?})`，最多500字/5条。
- `chatBrowserRead({id,request_id,url,mode?})`，最多2048字 URL，默认 auto。
- `chatBrowserAsk({id,request_id,query})`，最多200字关键词，本地 M06 检索，不调用模型或联网。
- `chatBrowserSource({id,evidence_id})`，仅返回该会话保存的一个证据；其余新增接口返回会话快照。

主进程仍校验调用者、frame、参数数量及 strict 契约，所有操作共享串行忙碌锁。源详情最多8000个 Unicode 码点，TS 与 Python 不以不同的 UTF-16 长度误拒 emoji。Browser 请求不设模型取消按钮；网络本身有10/20秒预算，无自动重放。renderer 不能选择网络请求方法、Cookie、Header、脚本、主机策略或绝对文件根。

试用：`npm run build` 后 `npm start`，选择“搜索网页”提交关键词，展开摘要并显式读取，点击“查看证据”；选择“询问已有来源”输入正文关键词。已知 URL 读取不需要 Tavily；无 Key 的搜索会返回可见错误。真实请求会把本次查询发到 Tavily 或访问所填网站，不自动发送目录元数据。

测试：`npx vitest run apps/desktop/tests/m12-contracts.test.ts tests/integration/m12.test.ts`；构建后设置 `ORVIA_TEST_MODULE=M12` 运行 `npx playwright test tests/e2e/m12.spec.ts`。报告、截图、合成数据位于忽略的 `artifacts/test-results/M12/`。测试启动器只在 tests/e2e 替换 DNS/HTTP 与凭据，不调用模型。历史 M10 整理流程回归通过。

限制：来源追问仅关键词检索、无生成式网页总结；来源目录最近20项/12 KiB，消息仍最近30条/46 KiB，无分页、附件、导出或引用事实自动核验。不重新打包，不加入自动任务和技能广场。


## M13 文档内容、引用与导出

输入框“添加附件”通过主进程原生选择器读取单个 PDF、DOCX、PPTX、PNG/JPG/JPEG（最多10 MiB）；不授予其父目录访问权。`DocumentCards.tsx` 展示格式、读取时间、文件/内容版本、页或段定位、OCR 方法/置信度、缺失和截断。正文始终是纯文本，不解释其中的指令、HTML 或链接。

固定 preload 接口：`chatDocumentAttach({id,request_id})` 返回取消标识或新快照；`chatDocumentAsk({id,request_id,query})` 按最多200字关键词在当前会话本地检索；`chatDocumentSource({id,evidence_id})` 读取最多50单元/8000码点证据（总页数可更大，缺失清单最多50项，其余通过截断标志说明）；`chatDocumentPreview({id,evidence_id,format})` 返回 Markdown/JSON 原文摘录、引用覆盖和不可变版本；`chatDocumentExport({id,evidence_id,format,revision,request_id})` 必须经主进程保存确认后写入。主进程仅允许最近一次实际返回的预览身份继续导出，尝试保存后或重连即清除；取消后再次导出需要重新预览。renderer 从不提供或获得附件绝对路径。后端继续通过 Computer gateway 执行路径检查与受限新建，拒绝已有目标，不把保存确认为覆盖或目录权限。

试用：构建启动 → 添加合成附件 → 展开文档卡片 → 查看文档证据 → 选择“询问文档”输入原文关键词 → 预览 Markdown/JSON → 核对引用、缺失/截断 → 选择新文件路径并确认导出。取消选择器不读取/写入；重新打开历史会话可查阅已保存证据。异步文档和预览按会话身份隔离，切换会话不会显示旧结果。

本轮不调用模型、Tavily 或上传正文；文档追问是关键词检索，导出是一个已保存证据的原文摘录，不是生成式总结或排版文档。解析失败、OCR 不可用和缺页必须显式显示；不承诺无损版式或完整 OCR。快照文档目录最多20项/8 KiB，内容上限与解析细节以 backend 文档模块 README 为准。安装包未重建。

验证：L0 `npm run check`、`npm run build`；L1 `npx vitest run apps/desktop/tests/m13-contracts.test.ts apps/desktop/tests/m12-contracts.test.ts apps/desktop/tests/chat.test.ts`。L2/L3 集成命令及结果见 `docs/PROGRESS.md`。仅合成数据/mock，所有结果产物位于忽略的 `artifacts/test-results/M13/`。

## M14 本机打包验证

历史M14未签名0.2.0-rc.1候选包包含M10–M13对话及文档能力，不含M15–M20；上文“安装包未重建”描述保留为历史模块状态。本轮完整0.3候选、冻结资源、安装／升级／卸载与开发对照的实际状态以根目录 packaging/README.md、docs/PROGRESS.md为准，不能以构建或M19定向视觉包冒充完成。M14历史产物仍在artifacts/test-results/M14/，本轮产物在M20/。真实本地组件测试不等于云模型/Tavily验证；生产签名和独立Windows验收经用户确认暂缓。

## V3-001 按需工作区与历史入口

用途：普通聊天聚焦消息，只有当前工作流或当前会话已保存事实才显示对应代码/清理/脚本/桌面/浏览器区域。`renderer/workspace-state.ts`由快照计算可见性；`M17Cards`/`M18Cards`接收明确的`visible`属性。主页面按会话ID挂载，未挂载M18时不发账本IPC。工作流预览在局部忙碌解除后重新核对未消费身份，每个token只准备一次。

现有`chat.get`等快照增加可选`workspace_history`：`development=null|{draft_id,kind}`、`cleanup=null|{plan_id}`、`automation=[]|[script,desktop,browser]`（至多3类）。后端在既有SQLite锁内按会话查询，最多返回最近一个草稿/清理计划身份；输出无根路径、源码、权限。消息裁剪不影响这些入口，旧快照仍可根据程序消息身份显示。读取历史由既有身份校验接口处理，不改变审批和跨会话限制。

简单寒暄仅完整匹配固定集合后本地回答，例如“你好”“谢谢”“好的”“继续”；带任务的句子仍走原路由，等待授权/审批的任务不会被肯定语推进。没有新增依赖、凭据、网络或模型配置。启动`npm run build`、`npm start`；新会话问候后无工作区，再明确提出“生成 React 页面”并授权项目后显示代码区；“清理旧临时文件”显示清理计划；历史脚本只读账本不能代替批准。

验证入口：`apps/desktop/tests/v3-workspace.test.tsx`、`backend/tests/test_v3_workspace.py`、`tests/e2e/v3-workspace.spec.ts`；原M20业务E2E复用真实Electron/stdio/SQLite/LPAC/UIA/Chromium及合成模型和原生框。结果在`artifacts/test-results/V3-001/`，精确命令与结论见`docs/PROGRESS.md`。

限制：M17较早历史仍依赖现有消息可见范围，新增投影只保留最近草稿/清理计划；M18账本仍最多最近20条。内存预览不承诺跨重启恢复，权限不恢复、不自动重试或执行。旧M17/M18手工入口E2E已被M20自然入口业务验收取代；安装包未重建，本修复仅源码开发版。
