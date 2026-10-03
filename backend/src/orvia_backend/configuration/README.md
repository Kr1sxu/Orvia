# 模型配置与适配

用途：固定三个角色的模型映射，在内存持有凭据并提供有预算的模型调用基础。M02 不执行 Agent 任务。

目录：`__init__.py` 定义 Credentials/ModelRegistry，`client.py` 提供 ModelClient 和脱敏失败码。模型配置来自 `domain`，不另建可变副本。

输入输出与公共接口：`Credentials` 将 Key 包装为 SecretStr；`ModelRegistry.status()` 仅返回配置和存在性；`key_for(profile)` 仅供后端内部客户端取值。`ModelClient.complete(profile,messages,max_tokens,tools)` 返回 Completion（正文、工具提议、结束原因、token 用量）。工具提议只是数据，不执行函数。

M20增加 `ModelClient.stream(profile,messages,*,max_tokens=256,tools=None,response_format=None,on_delta=None)`；只使用同一固定配置的真实 `text/event-stream`。`on_delta` 是等待式异步回调，只接收供应商实际 `content` 增量；工具参数、推理字段与拒绝正文不显示为答案。客户端在回调完成前停止消费后续流，最后仍返回同一 `Completion`。JSON Object 是唯一可选结构化格式，模型提案和工具参数始终是不可信数据。

接口默认256只是适配器默认值。M20类型化意图和普通回答显式传`max_tokens=1024`；M15结构化证据回答保留原有`max_tokens=4096`，流式与另行原生确认非流式相同。业务输出上限不能从适配器默认值推断。适配器接受1–4096的显式预算，调用方维持各已实现业务自己的边界。

每次网络超时20秒、零重试、无重定向/环境代理；SSE单事件16KiB、整次512KiB（心跳和注释也计入）、正文64KiB、工具拼接64KiB/最多16项。严格UTF-8、CR/LF跨字节块、有限SSE字段，必须同时收到完成原因与`[DONE]`，缺失或断流明确失败。工具名称/ID/参数跨块拼接后须为严格JSON对象；重复键、异常索引和超预算拒绝。兼容`role:null`和`tool_calls:null`，供应商`aborted/insufficient_system_resource`为失败；不据模型别名静默放宽固定角色。

`chat/json_stream.py` 的 `AnswerJSONStream.feed()` 只增量解码顶层`answer`字符串，支持转义和代理对；`finish()`再次完整验证JSON并拒绝重复键。这些增量是临时文字，M15最终引用/结论校验和落盘成功后才成为保存回答；不存在将完成文本定时打字的路径。统一对话工作阶段共享50秒预算，暂停等待用户不计工作时间。

依赖配置：Pydantic、httpx；三角色、模型、地址、凭据引用固定，Mission 保存无 Key 快照。缺失 Key 明确失败，无备用模型。开发凭据由 Electron 从根 `.env.local` 读取，发布由 safeStorage 解密，经私有 stdio 初始化进入内存。

运行/示例：通过正常桌面初始化后调用 `configuration.status`；客户端仅由后端代码或显式真实测试使用，不向渲染端开放自由提示词或模型地址。

测试：`python -m pytest backend/tests/test_configuration.py` 使用合成 Key 和 httpx.MockTransport；真实合成探测脚本在 `backend/tests/`，须显式 `--run-live`。结果放 `artifacts/test-results/M02/`。

权限边界：HTTPS 固定目标、拒绝重定向、20 秒超时、零自动重试、显式受限输出token、响应 64 KiB；不写 Key、原始供应商错误或输入到日志/SQLite。客户端不创建授权、不触发文件/浏览器工具。

已知限制：token 数控制输出额度，不等同人民币精确费用上限；价格与账单由供应商决定。M02仅验证基础能力的描述是历史状态。M20没有模型自动降级：固定Main流式失败/不支持时说明临时结果与重复费用风险，另行原生确认最多一次同模型非流式请求；批准在调用前条件落库消费，失败也不能复用。证据回答仍要重新预览确切片段并通过既有M15原生生成入口；桌面/浏览器未知副作用没有此降级或自动重试。

M20目标测试：`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m20_model_stream.py backend/tests/test_configuration.py -q --basetemp=artifacts/test-results/M20/model-stream-temp --junitxml=artifacts/test-results/M20/model-stream.xml`。使用真正分次异步的httpx MockTransport合成字节，验证背压、取消关闭、UTF-8/CRLF逐字节、工具参数、结束标记、心跳/输出限额和固定地址，不读取`.env`或调用云端。mock通过不代表固定供应商真实流式兼容；真实合成调用与本轮最终结果以PROGRESS记录为准。

M07：Credentials 新增可选 tavily 搜索 SecretStr；configuration.status 的 search_available 表示是否配置。搜索服务与三个角色模型映射独立，替换凭据同时清除旧搜索 Key，不持久化、不自动联网验证。
