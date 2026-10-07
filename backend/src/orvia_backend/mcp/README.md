# V4-007 明确审查的 MCP 工具

本模块增加固定 MCP `2025-06-18` 的外部工具入口，支持 Windows 本地 stdio 服务和准确 HTTPS endpoint 的 Streamable HTTP。SQLite 保存配置、工具清单批准和实际调用尝试/结果。启动应用只加载配置，绝不启动服务、联网、恢复调用或复用旧批准。三个角色原固定模型、审批和文件权限链保持原有边界。

主Agent整合验收：62个不同传输用例、57服务、8Application协议及21相关回归全部通过；59桌面单元与1实际Electron流程通过，零模型调用。stdio启动取消会等待不可取消的原生创建终结再关闭后到Job，极端系统调用迟滞可使清理超过30秒协议预算；不提前声称回收。children_reaped仅说明ownedJob成员，普通账户服务器经WMI/外部broker派生进程不保证入Job，见[Windows Job说明](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)。HTTPS DELETE=405或异常表示远端关闭未确认（closed=false），本地client仍实际关闭，不把不支持终止当成功。POST JSON/SSE无GET恢复/压缩/OAuth，主动sampling/roots/elicitation等请求拒绝，不自动跟随URI。

## 结构、依赖与启动

`service.py`：配置文件审查、程序版本、工具批准、参数预览、调用、凭据保护及SQLite事实。`transport.py`：真实 initialize / initialized、stdio JSON Lines、HTTPS JSON/SSE、版本和通知、超时及子进程回收。`protocol.py`：固定版本与有限严格JSON。`schema.py`：实际输入/outputSchema校验。`__init__.py`导出`McpService`及`McpError`。

沿用现有 Python 3.12 项目虚拟环境、aiosqlite、httpx、psutil，无新增工具安装、依赖或模型下载。开发版 `npm run dev`，设置内 MCP 面板先选择普通 `.json` 配置文件。选择后依次完成准确配置确认、准确程序/endpoint连接确认、完整工具清单确认和每次准确参数确认。配置、连接和工具清单确认不能代替调用参数批准；取消参数确认不会执行 `tools/call`。

配置严格只支持：

```json
{"name":"本地只读服务","transport":"stdio","executable":"C:\\工具\\server.exe","args":[],"cwd":"C:\\工具","allowed_tools":["get_record"]}
```

```json
{"name":"HTTPS只读服务","transport":"https","url":"https://example.com/mcp","allowed_tools":["get_record"]}
```

stdio executable 为本地普通绝对 `.exe`，cwd可省略，缺省使用程序目录；参数最多16个且合计8KiB，禁止env及明文凭据 flag / password / token / header / authorization。HTTPS须与传输共享的准确ASCII canonical URL核验一致，禁止userinfo、query、fragment（包括空`?/#`）、反斜杠、控制符、非HTTPS及重定向。服务最多5个，配置文件最多16KiB，普通绝对JSON文件，不接受symlink/reparse文件。身份包含程序SHA256、工作目录及既有文件参数的完整SHA256；单文件256MiB、合计512MiB、核验10秒。程序/参数文件变化使旧审查失效；隐式导入、外部资源或原生DLL不在此哈希保证范围。

## 接口与准确批准

`McpService(store,chat,connector=None)`共用原事实库/锁；connector仅用于测试注入真实TLS测试CA或合成Session，生产默认严格证书核验。以下均为async，`forget_previews(cid)`为同步清当前会话内存准备许可：

- `open()`：迁移四表，旧running记unknown，工具批准状态expired，零连接。
- `preview_config(path)`→`{review_id,revision,config}`；路径只由原生文件选择提供。
- `configure(review_id,revision)`→ServerSummary；原生准确配置确认，重新读文件防旧确认批准变化内容。
- `list()`→`{servers}`；ServerSummary字段`id/name/transport/revision/status/tools_count/blocked_count/reason/credential_configured`。configured、review_required、ready、disconnected、error按当前真实连接/批准展示，旧数据库清单不能恢复ready。
- `connect_preview(server_id)`→`{server_id,revision,config,identity,credential_configured,purpose}`，identity为`{executable_hash,cwd,args_files:[{path,sha256,bytes}]}`；purpose为“连接并发现 MCP 工具”。
- `connect(server_id,revision)`→ToolReview`{server_id,revision,server_revision,session_id,server_info,capabilities,tools}`；真实初始化和分页发现后仍需原生工具确认。
- `approve_tools(server_id,revision)`→ServerSummary；后端再次实际`tools/list`，完整元数据变化或list_changed通知均撤销旧审查，必须重连重审。
- `call_preview(cid,server_id,tool,arguments)`→`{id,server_id,revision,server_revision,session_id,server_name,tool,arguments,metadata,purpose}`。purpose为“调用已审查的只读 MCP 工具”，准备不调用工具，保存准备许可前再次检查会话未删除。
- `call(cid,server_id,revision)`→Execution`{id,server_id,revision,server_name,tool,status,result,error}`。原生参数批准后，重新核对程序/工具/连接及schema，网络前SQLite事务写running。每批只尝试一次，不传`approved=true`或把renderer正文当权限。
- `history(cid)`→`{executions}`，最多16条/32KiB；真实历史不是任意业务任务完成证明。
- `disconnect(server_id)`→`{server_id,closed,children_reaped}`；`remove(server_id)`→`{server_id,removed:true}`；关闭不确定时保留句柄和配置，反复移除不能把未知回收变为成功。
- `replace_credential(server_id,credential)`→ServerSummary，私有入口仅独立HTTPS Bearer或None。`close()`关闭所有当前连接并清内存凭据/准备许可。

ToolReview的tool为`{name,metadata,allowed,blocked_reason}`。完整原始metadata含name/title/description/inputSchema/outputSchema/annotations/_meta，未知字段或不支持schema不会被忽略：保留可审查元数据并标blocked_reason。分页最多8页、总32工具、总30秒，重复名称、游标循环和超量拒绝，完整ToolReview最多32KiB。

## 只读工具、结果与信任限制

工具必须同时在用户准确名称清单、匹配程序`get_/read_/search_/list_/query_/lookup_`命名且不含写入、删除、执行、发送、安装、交易等拒绝词。destructiveHint=true、readOnlyHint=false明确拒绝。readOnlyHint=true不是授权，也不证明服务器实际无副作用；配置不可信服务有供应方行为风险。Windows普通权限stdio程序通过Job进行后代回收，该Job不是文件或网络隔离沙箱；程序已有用户权限和隐式依赖须由用户审查。程序不会从MCP结果安装依赖、执行指令或授予文件目录grant。

输入8KiB，schema支持有界object/string/integer/number/boolean/array/null及有限长度/范围/enum/default，拒外部引用、正则、组合或未知约束。实际输出schema校验structuredContent，声明outputSchema却缺少structuredContent拒绝。只接受text、object structuredContent和resource_link；资源URI仅作普通数据，不抓取、不打开或执行。image/audio/embedded当前不支持，status=limited、result=null；非法内容字段或schema=status=failed，不视为工具成功。原始供应商异常正文不进入错误信息。

单`tools/call`20秒，整个call含前后工具重核60秒。传输超时、取消、session过期、服务发起请求、断线及未获得实际工具响应均记unknown并撤销许可/关闭连接，无自动重试或自动重连。返回但被结构/内容/依据核验拒绝的结果为failed/limited；isError=true为failed。completed仅证明一次已批准调用取得并通过校验的实际响应，不证明其文本结论真实或整个用户需求已完成。

独立Bearer不来自三个角色Key，仅主进程safeStorage私有提供给后端内存；stdio不注入Key或env。不写配置JSON、SQLite、stdout、错误或日志。更换凭据先断连并撤销旧许可，连接进行中更换也不能发布旧凭据会话。工具metadata、服务器身份、内容和structuredContent若原始字符串/字段名包含当前凭据，整包拒绝保存/展示；检查直接递归原始字符串，JSON转义引号/反斜杠也不能绕过。此检测不证明所有其他秘密都能识别，服务结果仍为不可信数据。

## SQLite事实与删除

`mcp_servers`全局保存原生确认的无Key配置和身份；`mcp_tool_reviews`每服务最多20份完整工具批准事实，重启失效。`mcp_attempts(cid,revision,state)`每会话128个无正文尝试，独立于可清的准备缓存；达到上限拒绝新调用，不丢弃未知事实。`mcp_executions`最多32条会话结果，展示最近16条。准备审查统一内存最多20份，不能用缓存通知证明调用完成或恢复重复调用许可。

调用前及最终结果事务检查会话实际存在且无删除墓碑。删除所属会话同既有删除事务清attempts/executions，晚到网络结果不得恢复任何正文；全局服务配置不属于该会话删除范围。原生disconnect/removal/凭据变更使所有旧准备许可失效；chat撤回/删除清当前准备许可。

## 实际验证

服务目标57个独立用例有有效通过证据：真实SQLite、合成Session边界、准确配置与工具批准、program/hash变化、readonly/schema/未知字段、分页游标、输出预算与内容类型、删除/late-write、unknown及128尝试、凭据转义回显、凭据连接竞态、60秒预算缩时测试、真实Windows stdio初始化/两页发现/一次调用/父子Job回收，以及真实本机TLS初始化/发现/批准/一次工具调用/独立Bearer/DELETE关闭。TLS测试CA只在测试connector注入，生产verify=True；所有凭据和数据为合成，不读取真实Key、不调用云模型。

初轮service.xml 31/32通过，唯一失败是测试connector复用已被关闭的合成Session；修复fixture后最小复验通过。后续service-final.xml 41通过，service-accept.xml 46通过；service-echo.xml 9通过（新增6项引号/反斜杠），service-content.xml 8通过（新增5项分页及content字段，重复验证真实stdio/TLS和主流程）。复用仍有效的通过结论，不重复无关全量回归。传输/schema另有59个独立真实stdio/TLS/协议目标及Application/桌面/Electron结果由主Agent记录PROGRESS，不与合成Session混称真实服务。

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp.py -q --basetemp=artifacts/test-results/V4-007/service-accept-data --junitxml=artifacts/test-results/V4-007/service-accept.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp.py::test_remote_echo_of_private_credential_never_saved_or_returned -q --basetemp=artifacts/test-results/V4-007/service-echo-data --junitxml=artifacts/test-results/V4-007/service-echo.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_mcp.py::test_discovery_budget_rejects_cursor_cycles_and_incomplete_catalogues backend/tests/test_v4_mcp.py::test_invalid_mcp_content_metadata_does_not_become_completed_evidence backend/tests/test_v4_mcp.py::test_actual_sqlite_single_approved_call_and_no_implicit_calls_on_open backend/tests/test_v4_mcp.py::test_real_service_stdio_pages_schema_call_and_child_reaping backend/tests/test_v4_mcp.py::test_real_service_tls_discovery_approval_call_and_private_bearer -q --basetemp=artifacts/test-results/V4-007/service-content-data --junitxml=artifacts/test-results/V4-007/service-content.xml
```

证据统一Git忽略的`artifacts/test-results/V4-007/`。本轮未连接用户真实外部服务、未测试第三方OAuth/任意schema/任意content类型/大型工具清单；供应方行为、隐式依赖、真实服务质量及费用未验证。不自动下载或安装MCP服务。未签名安装包和独立Windows机器不在本模块验证范围。
