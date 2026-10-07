# V4-003 五轮上下文与长期记忆

此模块从已保存请求、消息和当前有效资料构造本地事实投影。自动发现候选不调用模型；用户逐批原生批准准确发送预览后，固定 Main 才整理摘要和候选。跨会话记忆仅供本地检索/展示，不能授予文件访问、执行或正文上云许可。

## 结构与公共接口

`service.py` 提供 `MemoryService(chat)`，复用 `chat.store` SQLite 连接和串行事务锁；模型客户端在调用时读取 `chat.client`，不会保存凭据。`__init__.py` 导出服务及与既有 `ToolError` 相同的 `MemoryError(code,message)`。

所有接口均为 async：

| 接口 | 输入、输出与行为 |
|---|---|
| `open()` | 追加独立表；重启将未结束模型批次记作 interrupted，不重发 |
| `synchronize(cid)` | 仅本地识别偏好/人物/项目中文明确模式，核验和撤销失效来源支持；返回 status/excluded |
| `context(cid,query='')` | 最近五个完整终态请求轮、当前状态、批准摘要、可选本地记忆，返回 rounds/current/summary/memories/truncated |
| `list(cid)` | 本会话候选及派生记忆各最多20条、summary_pending/truncated |
| `preview(cid)` | 冻结固定供应商、用途、instructions、input、revision、精确发送 bytes；不调用模型 |
| `generate(cid,revision)` | 仅已原生批准 revision 可调用；固定 Main 一次 nonstream complete、30秒总期限、1024输出 token，无 retry；成功返回 list |
| `search(query)` | 全库 FTS5/jieba，只返回经批准且准确来源仍有效的 verified 记忆，最多10条 |
| `correct(cid,memory_id,value)` | 限源会话，保存用户确切修正消息为新来源，旧值撤销；不调用模型、不构成新模型交互轮 |
| `forget(cid,memory_id)` | 删除该派生记录与相关候选，清掉本会话摘要/批次正文；以无正文 memory:ID 抑制再发现，保留原始消息 |
| `revoke_source(cid,origin)` | 移除 document:eid/browser:eid 对应支持；同一记忆仍有其它有效支持时保留 |
| `delete_conversation(cid)` | 删除该会话全部派生表数据；应用已有 purge 在其原始删除事务中同样处理这些表 |

表为 `memory_candidates`、`memory_records`、`memory_summaries`、`memory_batches`、`memory_attempts`、`memory_revocations` 和 `memory_fts`，源会话字段统一为 `cid`。无正文的memory_attempts保留(cid,revision,state)调用事实，不受最多20份预览缓存淘汰或纠正/遗忘清理影响；每会话最多128次尝试，满额拒绝新调用，不淘汰未知结果。启动迁入旧非prepared事实并将running记作interrupted，会话删除才清该账本。不复用旧 `context_preferences` 的值为自动确认事实。

候选/记忆记录含 id（64位 SHA256）、conversation_id、kind（preference/person/project）、key、value、status、sources。来源含 source_id、quote、status、origin；消息来源准确指向 message:UUID；资料来源准确指向 document:eid:unit 或 browser:eid:0。确认仅表示原文支持和批准过程通过，不代表第三方客观事实已被程序证明。矛盾值保留各自来源并标 conflict，不进入 verified 检索。

## 五轮、预算与来源核验

以 `chat_requests` 请求身份作为轮次，工具和澄清属于当前请求，不独立占轮。新消息由应用绑定 request_id；旧消息以准确用户请求起点（含既有 natural: 前缀）保守归属。completed 必须同时有用户及助手消息才能计完整轮，缺一对保留 completed_without_pair 当前事实；failed/cancelled/interrupted 逐字保留实际状态。未结束当前请求不自动视作成功。

原始投影最多读取最近1000条消息及既有100请求；窗口外每请求最多定点补一条原始用户及一条助手以核对是否完整，工具超量截断保持可见；同文旧请求无法准确补归属时不猜测。预算：单消息2048 UTF-8字节、每轮4096字节、context整包24KiB；超限明确 truncated，原始消息不删除。已批准长期来源最多128个/会话，在库内按精确ID定点回查，不会因原始窗口裁剪而消失。

候选最多64/会话，已存派生记忆最多512/全库，单条最多8个准确来源；每个来源摘录最多2048字节。list整包32KiB，search整包16KiB。摘要最多12条逐字原文结论/12KiB，保留此前摘要 items、准确原文支持和请求状态；预算用尽拒绝新批次并保留旧摘要，需新建会话继续，不能静默丢掉旧事实。

预览发送输入含以前已批准摘要及其原文、最多10个早于最新五轮的终态轮、最多16候选。实际 instructions＋紧凑 canonical JSON(input) ≤24KiB，完整预览≤32KiB；程序选批预算更保守以容纳可审查结构。来源与旧摘要全部绑定 revision，生成前后及最终 SQLite 写事务内重新核验。prepared→running 在网络前落盘，已调用、失败、中断和完成 revision 不重发。拒绝模型未知来源、额外字段、无原文支持的值、敏感字段、非本地明确候选的记忆；每个摘要轮必须至少引用其原始用户来源，否则不消费该轮。

## 使用与验证

开发版启动后添加合成会话/资料，进入设置的记忆入口查看候选、准确预览；原生取消不调用模型，批准后校验结果自动入库。搜索跨会话记忆须在源会话纠正或忘记。对话删除连同全部派生正文清理，保留原文件/导出成品。

运行核心目标检查：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_memory.py -q --basetemp=artifacts/test-results/V4-003/core-accept-data --junitxml=artifacts/test-results/V4-003/core-accept.xml
```

最终27个核心目标用例通过（真实 SQLite、合成资料、Main mock，无真实云调用），覆盖五轮/工具归属/待审批/失败取消中断、敏感内容和满载/长消息预算、取消零调用、准确发送字节、持久化和不重发、恶意来源/值/覆盖率、审批失效、缺凭据、跨会话冲突/纠正/忘记、附件来源撤回、多来源支持、窗口之外长期来源与完整轮、滚动摘要和事务前来源竞态。初次15通过2失败已修复；最小失败复验2通过，后续完整21通过，支持撤回最小复验3通过，最终窗口/预算最小3通过后全核心22通过。审查增加缓存淘汰/重启/未知状态三项、128尝试满额、大旧摘要实际字节预算共5项，核心＋3协议最终30通过（ledger.xml）；遗忘保留账本最小复验1通过。协议、Electron 和产品联调结果以根 `docs/PROGRESS.md` 为准。

## 依赖与限制

使用现有 Python 3.12、aiosqlite、Pydantic、jieba 和 ModelClient，不新增运行依赖，不加载模型或自动下载。中文候选规则只覆盖明确模板，例如“我的偏好是简洁回答”“我的项目是合成航线”“合成人甲的角色是负责人”“项目合成航线的目标是验证”。其它表达不猜测；Key/password/密码/身份证等明确模式过滤仅是有限识别，不能保证发现全部敏感正文，准确发送预览仍必须审查。

长期检索使用 FTS5精确词召回，不声称所有记忆都做语义向量索引。真实 Main 模型整理、独立 Windows 和安装包未由本核心 mock 验证替代；不更换三角色固定模型，不重建安装包、不push。
