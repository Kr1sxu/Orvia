# 模型配置与适配

用途：固定三个角色的模型映射，在内存持有凭据并提供有预算的模型调用基础。M02 不执行 Agent 任务。

目录：`__init__.py` 定义 Credentials/ModelRegistry，`client.py` 提供 ModelClient 和脱敏失败码。模型配置来自 `domain`，不另建可变副本。

输入输出与公共接口：`Credentials` 将 Key 包装为 SecretStr；`ModelRegistry.status()` 仅返回配置和存在性；`key_for(profile)` 仅供后端内部客户端取值。`ModelClient.complete(profile,messages,max_tokens,tools)` 返回 Completion（正文、工具提议、结束原因、token 用量）。工具提议只是数据，不执行函数。

依赖配置：Pydantic、httpx；三角色、模型、地址、凭据引用固定，Mission 保存无 Key 快照。缺失 Key 明确失败，无备用模型。开发凭据由 Electron 从根 `.env.local` 读取，发布由 safeStorage 解密，经私有 stdio 初始化进入内存。

运行/示例：通过正常桌面初始化后调用 `configuration.status`；客户端仅由后端代码或显式真实测试使用，不向渲染端开放自由提示词或模型地址。

测试：`python -m pytest backend/tests/test_configuration.py` 使用合成 Key 和 httpx.MockTransport；真实合成探测脚本在 `backend/tests/`，须显式 `--run-live`。结果放 `artifacts/test-results/M02/`。

权限边界：HTTPS 固定目标、拒绝重定向、20 秒超时、零自动重试、最大 1024 输出 token、响应 64 KiB；不写 Key、原始供应商错误或输入到日志/SQLite。客户端不创建授权、不触发文件/浏览器工具。

已知限制：token 数控制输出额度，不等同人民币精确费用上限；价格与账单由供应商决定。M02 只验证文本与工具提议基础能力，LangGraph 编排、流式输出、任务预算、取消和任意结构化输出兼容性留后续。没有模型自动降级。

M07：Credentials 新增可选 tavily 搜索 SecretStr；configuration.status 的 search_available 表示是否配置。搜索服务与三个角色模型映射独立，替换凭据同时清除旧搜索 Key，不持久化、不自动联网验证。
