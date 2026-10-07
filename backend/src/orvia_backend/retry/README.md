# V4-011 安全只读重试

用途：把程序确认可重复的读取放进同一原始总预算，记录无正文尝试事实。成功返回只表示该读取取得响应/SELECT结果，不能替代引用、产物读回或所有业务目标完成核验。模型自述、工具声明、某个步骤成功均不构成整个任务完成。

## 结构与固定策略

- `policy.py`：程序固定工具清单、错误分类和Retry-After解析。
- `service.py`：deadline/取消控制、独立尝试序号、ContextVar会话归属及SQLite账本。
- `__init__.py`：导出`RetryService`、`RetryError`和仅可信静态HTTP适配器可构造的`HTTPTransient`。

只有两个允许入口：

| 固定工具 | 实际适配 | 可以重试的准确错误 |
|---|---|---|
| `browser.static_read` | Browser `_fetch_page(budget=None)` 且网络是SafeHTTP；无Cookie/认证/脚本的公开静态页面 | `httpx.ConnectError`/`ConnectTimeout`发送前连接失败；已收到HTTP429/503响应 |
| `context.sqlite_read` | ContextService最终纯SQLite FTS SELECT | 原生`sqlite3.OperationalError.sqlite_errorcode`确定为BUSY/LOCKED（含扩展码） |

不根据错误字符串中的“locked”、GET方法、模型结果或MCP `readOnlyHint`授权。模型、Shell、进程、文件变更、动态浏览器GET/外发、MCP及含嵌入/清理索引的整段检索都不能进入重试引擎。Tavily搜索POST按次计费，发送结果不确定；它沿用单次请求，不增加搜索轮数或费用范围。权限、认证、不支持、内容类型/格式错误和未知异常不重试。

发送后`ReadTimeout`/`WriteTimeout`/`ReadError`/`WriteError`/`RemoteProtocolError`记录`unknown/NETWORK_UNKNOWN`，不自动重放。取消、原deadline耗尽、程序关闭也停止等待和后续尝试。SafeHTTP传输自身始终不重试，Playwright有动态budget的文档/资源路径维持原有行为。

## 输入输出与生命周期

```python
retry = RetryService(store)  # 无Store时只保留进程内无正文回执
await retry.open()
with retry.activate(cid, trusted_parent_request_id):
    result = await retry.run(
        "context.sqlite_read", {"query": "合成问题", "limit": 5},
        async_read_callback, deadline=original_deadline_monotonic,
    )
history = await retry.history(cid)
await retry.close()  # 必须先于共享Store.close
```

`run(tool, parameters, callback, *, deadline, cid=None, business_id=None, cancel_event=None)`返回原callback值或原失败，不持久化响应。callback为可信无参数async函数；deadline是原业务的monotonic绝对时刻，不得每次重置。最多三attempt，同一child业务ID、独立连续sequence1..3，等待和执行均计入原预算。普通退避固定0.2/0.5秒。Retry-After支持RFC整数秒与HTTP日期；无效、超过remaining或大于0.5秒单次等待上限时停止，不无视服务器要求提前请求。日期已过期则只使用正常退避。

可信handler通过`activate(cid,parentRID)`绑定会话；不增加renderer安全分类参数。scope的同步调用计数加tool/参数digest派生UUID5，不同子读取（含同问题重复读取）不会误合并；每个子业务内部三attempt共用身份。显式同business_id再次调用会被`RETRY_TERMINAL`拒绝，零重新执行；没有正文结果缓存，旧成功不能被当成新事实。并发会话通过ContextVar隔离。独立Browser日常服务未绑定Store/cid时使用进程内回执，不依赖应用迁移。

`BrowserService(..., retry=retry)`；`read(url, mode="auto", cid=None, business_id=None, cancel_event=None)`中的新增身份参数只由可信后端入口传递，也可继承activate。每页原20秒期限保留；重试与最多三跳同源重定向合计最多四次HTTP传输，整个页最多三attempt，不在每hop重置次数。Browser每响应仍最多512000字节、正文8000字符；原四请求最大字节预算不扩大。Research的十个URL/两搜索轮等业务计数仍由原服务控制，一页的内部attempt不创建新网页业务。

`open()`建`retry_runs`/`retry_attempts`并将遗留running改为interrupted，不恢复请求。表只含cid、业务ID、tool、参数SHA256、sequence、时间、delay、reason、state及固定error_code，无URL、问题、正文、响应或凭据。参数digest用于绑定，不是匿名化保证。SQLite每业务事实保留到所属会话删除，避免历史显示裁剪后重放；账本磁盘空间随使用增长，不自动删除身份。每cid最多32个同时running；`history(cid)`最新32run，每run最多三attempt，整包32KiB，裁剪整run时truncated=true。无Store回执仅最近128run，不提供跨重启幂等性。

history形状：`{id:cid,runs:[{business_id,tool,parameter_digest,state,started_at,finished_at,attempts:[{sequence,state,started_at,finished_at,reason,delay_seconds,error_code}]}],truncated}`。状态为running/succeeded/failed/unknown/cancelled/timed_out/interrupted；succeeded仅意味着适配器返回，Browser格式和后续引用核验仍可能失败。business_id为ASCII `[A-Za-z0-9_.:-]{1,128}`，固定error_code最多64字符；时间为带UTC offset的ISO字符串。UI只读，无修改策略/执行旧attempt/批准新能力入口。

`has_unresolved(cid)`只识别running，不以startup interrupted或只读unknown阻塞删除。`forget(cid)`停止该cid未来attempt、等无正文账本收尾并清其内存投影；SQLite删除由原Chat同一事务按cid清两表，墓碑阻止晚写重建。真实chat及独立Mission可归属；已删除/待删cid拒绝读取和写入。

`close()`先禁止新run、设置所有取消event，然后等initial/terminal账本写入收尾再返回，不关闭共享Store。取消抵抗协程的晚响应只排空，不能回到业务或复活终态。initial写入入队后即使task.cancel也先等事务落定再记录取消；事件循环阻塞、账本等待超过deadline及保存后取消均拒绝返回值，只允许当前finalizer保守撤回成功返回资格。账本写入不自动重试。存储锁和运行环境可延迟收尾，不能承诺强制停止任意线程；回执收尾可比执行deadline更晚，但不会在deadline后开启或接受读取成功。

## 验证

依赖仅复用项目Python3.12、httpx、aiosqlite/SQLite，无安装、模型或真实凭据。测试仅合成数据。

L0：

```text
backend/.venv/Scripts/python.exe -X utf8 -m py_compile backend/src/orvia_backend/retry/__init__.py backend/src/orvia_backend/retry/policy.py backend/src/orvia_backend/retry/service.py backend/src/orvia_backend/browser/service.py backend/src/orvia_backend/browser/network.py backend/tests/test_v4_retry.py backend/tests/test_v4_retry_browser.py
git diff --check -- backend/src/orvia_backend/browser/service.py backend/src/orvia_backend/browser/network.py
```

L1/L2最终目标：

```text
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry.py backend/tests/test_v4_retry_browser.py -q --basetemp artifacts/test-results/V4-011/retry-final-temp --junitxml artifacts/test-results/V4-011/retry-final.xml
```

60通过，覆盖真实SQLite exclusive锁解除后成功/持锁三次上限、SQLite账本重开/旧ID/无正文、并发CID、初始化中断、删除墓碑、取消/关闭、initial保存等待、事件循环阻塞、保存后超时/取消、最终保存时task.cancel，以及历史显示裁剪不允许重放旧业务。真实合成TCP/HTTP覆盖连接前拒绝后成功、429/503后成功、三次上限、发送后断线未知、401/403/404/500拒绝、Retry-After超预算、redirect与retry共四请求、backoff取消、格式拒绝及动态budget不重试。公网合成域名到本机fixture的映射仅测试transport注入，生产DNS/公网安全策略没有放宽；不宣称真实Internet/供应商结果。

最终未知状态分类审查只改变9个相关目标，按实际改动最小复验：

```text
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry.py backend/tests/test_v4_retry_browser.py -q -k 'unknown or disconnect' --basetemp artifacts/test-results/V4-011/retry-unknown-temp --junitxml artifacts/test-results/V4-011/retry-unknown.xml
```

9通过/51未选；其余51项有效结论复用，合计60不同目标通过。早期`retry-lifecycle.xml`40通过/2失败，是合成late callback用固定sleep而未等其真实开始；改成entered事件同步后，`-k late_success`的`retry-lifecycle-recovery.xml`3通过，最终60目标再次通过。失败记录保留，不把零执行的测试竞态称真实晚值验收。

另补静态HTML同步提取消耗原20秒期限的边界。`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_retry_browser.py::test_html_extraction_elapsed_original_deadline_does_not_complete_read -q --basetemp artifacts/test-results/V4-011/retry-extraction-temp --junitxml artifacts/test-results/V4-011/retry-extraction.xml`，1通过；模拟只推进提取后的时钟，真实HTTP只请求一次，HTTP回执成功但正文读取返回失败，明确不把响应成功当业务完成。合计61个不同重试/Browser目标有通过证据。

Browser相关旧回归：

```text
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_browser.py backend/tests/test_browser_engine.py -q --basetemp artifacts/test-results/V4-011/browser-regression-temp --junitxml artifacts/test-results/V4-011/browser-regression.xml
```

37通过/4未显式启用Chromium测试skip；既有真实动态浏览器证据按PROGRESS复用，本次实际重试目标没有运行Playwright。Application、Research协议/权限、桌面IPC/Electron和全任务闭环由主Agent分别验证并记录PROGRESS。产物均在被Git忽略的`artifacts/test-results/V4-011/`。

## 限制

没有真实云模型、Tavily、Internet、人工原生确认或独立Windows测试；不提供通用网络重试或副作用撤销。允许的公网静态读取仍可能产生服务器访问记录。安全分类来自固定程序适配，不能把任意GET或恶意自声明服务放入该类别。取消不能强杀未知协程/线程；late值不会被采用。SQLite参数digest不包含正文，仍应按本地事实资料保护。全部目标完成、部分结果接受与引用/产物核验保留原任务完成链，尝试成功不会自动满足这些条件。
