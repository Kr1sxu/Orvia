# Electron 桌面模块（M13）

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

根目录运行 `npm run build` 后 `npm start`。示例：选择只含合成 `a.txt` 的目录 → 查看列表 → 发送“把 a.txt 重命名为 b.txt” → 核对源/目标与版本 → 独立批准 → 查看程序核验 → 必要时撤销最近变更。重新打开会话后必须重新授权原根。未授权的消息不会在选择目录后自动重放，请再次提交目标。

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

最新未签名候选版为0.2.0-rc.1，包含对话及文档能力；上文“安装包未重建”描述保留为历史模块状态。PDF/OCR冻结资源、安装包流程、升级/卸载的命令与边界见根目录 packaging/README.md、docs/PROGRESS.md。测试产物统一为 artifacts/test-results/M14/。真实本地组件测试不等于云模型/Tavily验证；生产签名和独立Windows验收经用户确认暂缓。
