# Browser 搜索与公开网页读取（M07）

## 用途、结构与接口

`network.py` 是唯一网页网络出口：URL/DNS 校验、固定 IP 连接、流式字节预算。
`service.py` 提供 `ReadRequest` / `SearchRequest`、`BrowserService.read(url, mode=...)` 和 `web_search(query, max_results=5)`；`agents/roles.py` 的 BrowserAgent 只委派这两个窄接口。

Application 私有 stdio 增加：

- `browser.read({mission_id, url, mode: "auto" | "http" | "playwright"})`。
- `browser.search({mission_id, query, max_results: 1..5})`。

任务必须存在，未知字段一律拒绝。显式 URL 来自可信主进程，授权范围是该 URL 的单页、同源重定向与动态资源；不接受网页内容自行扩权。不提供 renderer 网络按钮、任意脚本、选择器、点击、表单、上传、Cookie 或请求头参数。当前 LangGraph 仍是 M05 的合成文件流程，不会自行搜索。

读取结果包含 `source_url`、UTC `accessed_at`、`mode`、`content`、`truncated`、`error`。错误为固定 `code/message`，不返回底层异常或失败响应正文；`accessed_at` 是本次读取/尝试的记录时间，只有 `error=null` 且有正文才构成成功读取证据。策略拒绝尚未接受的 URL 时 `source_url=null`。
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

网页和搜索片段是不可信证据，不改系统规则、授权或偏好；不会自动写入 M06 索引。若需要索引，由可信调用方显式提交文本与来源。M07 未调用真实模型、未实际调用 Tavily，也未在真实互联网网页上验证兼容性。

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
