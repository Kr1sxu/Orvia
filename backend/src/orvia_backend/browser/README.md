# Browser 搜索与公开网页读取（M07 / M12）

M20当前从自然语言访问/搜索/检索已有来源意图调用这些固定接口，无需先选技术模式；下述M12按钮描述保留为历史入口。只有明确访问指令的公共URL进入SafeHTTP，代码/正文内URL或任意提及不授权联网；证据版本和可回查引用保持。缺Tavily直接不可用，已有来源检索不冒充新搜索；需要综合正文时复用M15片段预览/固定Main原生批准。写操作仍只能进入独立M18专用可见浏览器和每步/实际外发审批，M20识别不授予站点或发送权限。

M18另增`../automation/browser.py`与`write_network.py`专用写会话。它需要main原生逐任务准确站点/类别授权、专用可见内存登录、控件逐步审批及真实外发请求独立确认，不能从本只读接口得到写许可；详见[automation README](../automation/README.md)。原BrowserService/SafeHTTP与M12证据存储仍保持只读。

M15 可在用户选择当前会话已保存的网页版本并确认发送范围后，将有界正文片段交给固定 Main 生成回答；Browser 网络读取本身仍是只读，不自动上传正文给模型，也不开放浏览器写操作。生成入口与引用验证见 `../chat/README.md`。

## 用途、结构与接口

`network.py` 是唯一网页网络出口：URL/DNS 校验、固定 IP 连接、流式字节预算。
`service.py` 提供 `ReadRequest` / `SearchRequest`、`BrowserService.read(url, mode=...)` 和 `web_search(query, max_results=5)`；`agents/roles.py` 的 BrowserAgent 只委派这两个窄接口。

Application 私有 stdio 增加：

- `browser.read({mission_id, url, mode: "auto" | "http" | "playwright"})`。
- `browser.search({mission_id, query, max_results: 1..5})`。

任务必须存在，未知字段一律拒绝。显式 URL 来自可信主进程，授权范围是该 URL 的单页、同源重定向与动态资源；不接受网页内容自行扩权。M12 提供固定会话搜索/读取按钮，不提供 renderer 直接联网、任意脚本、选择器、点击、表单、上传、Cookie 或请求头参数。当前 LangGraph 仍是 M05 的合成文件流程，不会自行搜索。

读取结果包含 `title`（缺失为空）、`source_url`、UTC `accessed_at`、`mode`、`content`、`truncated`、`error`。错误为固定 `code/message`，不返回底层异常或失败响应正文；`accessed_at` 是本次读取/尝试的记录时间，只有 `error=null` 且有正文才构成成功读取证据。策略拒绝尚未接受的 URL 时 `source_url=null`。
搜索额外返回 `available` 和 `results`，各项标记 `mode=search_snippet`，摘要不冒充页面全文。`available` 仅表示已配置搜索 Key，不代表服务已通过联网探测；缺失返回 `SEARCH_UNAVAILABLE`，结果为空且不联网。

## 依赖与配置

Python 3.12、httpx、trafilatura、Playwright，版本锁在 `backend/uv.lock`。
开发 `TAVILY_API_KEY` 只由 Electron 读取根 `.env.local`；以独立 `tavily` 字段经 initialize / credentials.replace 注入 SecretStr 内存。发布通过现有 safeStorage 加密保存/删除，无明文回退。它不是第四个模型角色，不改变三个固定模型快照。已知 URL 的读取不需要任何模型或搜索 Key。

```powershell
.\.venv\Scripts\uv.exe sync --project backend --locked
.\backend\.venv\Scripts\python.exe -m playwright install chromium --only-shell
npm run build
npm start
```

2026-09-28 重试后，Playwright 配套 Chromium Headless Shell 153.0.8010.12（revision 1243）已安装，默认引擎 4 项合成测试通过，无需 Edge 测试覆盖。此前下载超时的记录保留于 PROGRESS；其它机器缺失运行时仍会返回 `PLAYWRIGHT_FAILED`，产品无自动回退。M08 分发仍需验收。

## 只读边界与预算

| 范围 | 限制 |
|---|---|
| URL | 最长 2048 字符；仅 HTTP/HTTPS 标准 80/443；拒绝凭据、片段、反斜线、控制符、本机/内网/保留地址 |
| DNS / TLS | 解析全部地址并拒绝混合内外网；固定已验证 IP 连接，保留 Host、TLS SNI 与证书验证；不使用环境代理 |
| HTTP | 每跳重新校验；最多 3 次同源重定向；仅 HTML/XHTML/纯文本；拒绝附件与压缩响应 |
| 响应 | 每个响应最多 512000 字节，超限丢弃正文并标记错误/截断；正文最多 8000 字符 |
| 时间 | 单连接操作 5 秒；读取整体 20 秒（资源清理另计）；动态页面等待 networkidle 最多 10 秒；无自动重试 |
| 动态页 | 每次全新非持久 context；仅一个主框架页面；同源 GET 的 document/script/stylesheet/xhr/fetch，按资源类型检查 MIME |
| 动态预算 | 最多 30 次网络请求（含重定向），合计 2000000 字节；并发请求串行扣减预算 |
| 封闭能力 | CSP sandbox 禁止表单/弹窗/子页面；阻止图片、媒体、字体、Worker、WebSocket、下载、POST 等写请求与二次导航 |
| 搜索 | 固定 Tavily API 的专用 POST；query 最长 500 字符，basic 最多 5 条；10 秒总限时、128000 字节响应；无自动读取结果页 |

浏览器资源全部由 Python 网关取得后 fulfill，不使用 `route.continue_` / 浏览器直连；浏览器底层配不可用代理并禁用非代理 WebRTC。网络端不透传 Cookie、Authorization、Referer、Set-Cookie、Refresh。页面脚本产生的会话数据不持久化、不跨读取复用。权限规则是程序策略，不是任意不可信代码的 OS 沙箱，也无法保证公开 GET 在网站服务器上绝无副作用。

## 路由与已知限制

`auto` 先 HTTP + trafilatura；只有成功得到无正文的 HTML 才尝试动态渲染。HTTP 权限拒绝、下载、超限、网络失败不会触发绕过式回退。可由可信调用方明确选择 `playwright`。

默认不跨源、不加载 CDN 脚本，不支持登录、验证码、点击后内容、PDF/OCR、附件、持久 Cookie、任意网页操作。HTTP 正文按 UTF-8 解码；其他编码可能不完整。带加载提示的空壳可能被正文提取器认作静态文本，需显式动态模式。动态页受 CSP、同源和预算限制，部分资源失败会返回 `RESOURCE_RESTRICTED` 与截断标记。脚本二次导航被拒绝后可能使读取失败，这是封闭策略的预期结果。

网页和搜索片段是不可信证据，不改系统规则、授权或偏好；M07 直接接口不会写入 M06 索引；M12 用户显式会话请求会将返回证据保存并按版本加入当前任务索引。M07 未调用真实模型、未实际调用 Tavily，也未在真实互联网网页上验证兼容性。

## 测试和合成试用

默认测试只使用 HTTP/DNS mock、合成凭据和临时 SQLite：

```powershell
.\backend\.venv\Scripts\python.exe -X utf8 -m pytest backend/tests/test_browser.py --basetemp=artifacts/test-results/M07/demo-temp --junitxml=artifacts/test-results/M07/demo.xml -q
```

可显式运行真实浏览器引擎，但页面/资源仍来自合成 mock，无真实站点访问：

```powershell
$env:ORVIA_BROWSER_TEST='1'
# 使用默认配套 Chromium，清除此前可能设置的测试浏览器选择。
Remove-Item Env:ORVIA_BROWSER_TEST_CHANNEL -ErrorAction SilentlyContinue
.\backend\.venv\Scripts\python.exe -X utf8 -m pytest backend/tests/test_browser_engine.py --junitxml=artifacts/test-results/M07/engine-demo.xml -q
Remove-Item Env:ORVIA_BROWSER_TEST
```

私有协议示例（先 hello、initialize 并通过 missions.create 创建合成草稿，将返回的 id 代入）：

```json
{"v":1,"id":"search-1","method":"browser.search","params":{"mission_id":"返回的草稿ID","query":"合成测试查询"}}
{"v":1,"id":"read-1","method":"browser.read","params":{"mission_id":"返回的草稿ID","url":"https://example.com/","mode":"http"}}
```

第二条会实际访问公开站点，只应在明确需要联网时发送。模块实际命令、失败记录、验证范围见根 `docs/PROGRESS.md`，本轮所有新报告在 Git 忽略的 `artifacts/test-results/M07/`。

## M12 来源版本与会话入口

`evidence.py` 新增 EvidenceStore，复用 Store 的锁/连接，在 app.sqlite 幂等创建 browser_evidence，不增加数据库文件或运行依赖。每个证据保存 mission_id、URL、标题、读取模式、访问时间、正文、截断、错误、content_hash 和 evidence_id。同任务、URL、模式、正文哈希、标题、截断和错误决定版本 ID；重复内容保留首次记录，变化内容创建新版本。索引源为 browser:<证据ID>，摘要和 HTTP/动态正文不会覆盖彼此。证据 hash 用于版本定位，不代表网络来源可信。

当前对话通过 `chat.browser.search({id,request_id,query,max_results?})`、`chat.browser.read({id,request_id,url,mode?})` 调用原 BrowserService。返回的每个来源均保留类型和错误；重复摘要在同一次消息中去重。没有 Key 时保存 SEARCH_UNAVAILABLE；空结果不虚构条目。错误网页不进入成功正文索引；动态读取带正文但资源受限的证据会索引正文且保留错误/截断，检索引用同样携带限制。

`chat.browser.ask({id,request_id,query})` 复用 M06，返回最多5项关键词匹配原文及引用，不联网、不生成模型结论。原文片段600字符、卡片短预览180字符；`chat.browser.source({id,evidence_id})` 获取最多8000码点的完整已保存文本，归属错误拒绝。会话消息与来源目录分别受30条/46 KiB、20条/12 KiB限制。每会话包括文件提问在内最多100次请求；超额在网络调用前拒绝。

例：输入框选搜索网页→“合成许可”→摘要卡片→显式“读取此网页”→“查看证据”→选询问已有来源并输入“许可”。仅已知 URL 读取不需要 Tavily 或任何模型凭据。搜索/读取不会把网页返回的指令交给文件规划模型，固定三角色配置保持不变。

新增验证：`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m12_browser_chat.py backend/tests/test_browser.py -q`。真实 Chromium 合成验证设置 ORVIA_BROWSER_TEST=1 后运行 test_browser_engine.py；全部 DNS/HTTP 为替身，无真实网络/模型调用。Electron 流程见 tests/e2e/m12.spec.ts，产物仅保存 artifacts/test-results/M12/。

边界沿用 M07：只允许公开 URL、同源重定向、标准端口、固定 DNS IP、安全资源类型和有界正文；无 Cookie 复用、登录、表单、上传或网页写操作。标题作为转义文本展示。检索为词匹配而非语义问答，旧版本会参与检索，引用时间需用户核对；来源保存/索引间失败可保留已保存证据，显式重读才能重建对应索引。M12 不重新打包、不增加附件/导出或定时任务。
# M13 复用说明

`EvidenceStore` 增加程序内部限定的browser/document存储类型及 `save_version`，供M13文档共用不可变版本、首次时间和会话归属检查；默认browser表、哈希标识及已有证据格式保持兼容。文档不伪装为网页，不改变Browser网络权限或M12只读流程；M13回归已覆盖原来源版本/隔离/重启。文档接口见 `../documents/README.md`。

## V4-010 复用

研究采集复用既有公开HTTP/Playwright校验和20秒单页预算，不开登录/下载/写入权限。缺Tavily仍明确不可用，查询最多两轮，每轮五个候选；站点限制仅在本机过滤结果/最终URL。十页失败也占额度；研究原文及关联在同一SQLite墓碑事务保存，已有不可变身份保持。真实HTTP测试使用自有合成站点及测试专用DNS路由，不冒充生产Internet搜索验收。


## V4-011 静态安全读取重试

`BrowserService(retry=RetryService)`仅对真实SafeHTTP匿名静态读取开放最多三次同业务尝试。程序确认无Cookie/认证/脚本；发送前ConnectError/ConnectTimeout、准确429/503可重试，读超时/发送后断连/认证/权限/格式/未知结果不重试。全部退避和读取沿用单页20秒deadline，重定向与重试合计最多4次网络请求、重定向仍最多3跳。Retry-After超剩余时间或0.5秒最大单次等待则直接停止，不提前忽略远端等待。

Playwright动态文档/资源、有用户外发的专用Browser、收费Tavily POST均不符合此白名单，不因GET或只读声明获得资格；Tavily缺Key依旧准确unavailable。静态返回成功只表示取得读取值；正文解析/范围/截断/事实完成另由原业务验证。`read`可信私有kwargs cid/business_id/cancel_event用于准确归属和取消，renderer没有安全分类入口。`retry.history`只显示无正文SQLite尝试事实。真实TCP连接拒绝/429/503/断连/认证/取消/请求限额等验证见`test_v4_retry_browser.py`、`test_v4_retry_protocol.py`和PROGRESS。
