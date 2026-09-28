# M10–M11 会话与桌面任务应用服务

本模块把对话、Computer 只读观察、LangGraph 计划、独立审批和动作账本连接起来。没有自动任务、技能广场、插件、Browser 搜索或任意执行入口。

## 结构与公共接口

- `contracts.py`：私有 IPC 请求和模型提案白名单；未知字段拒绝。
- `repository.py`：在应用 `app.sqlite` 中维护会话、消息及请求去重表，复用 Store 的串行数据库锁。
- `__init__.py`：`ChatService.handle(method, params)`；由 Application 初始化并调用，不单独监听端口。

`chat.create({client_request_id,title})` 幂等创建一对一 Mission 会话；`chat.list({})` 返回最多 100 个会话；`chat.get({id})` 返回快照。`chat.send({id,request_id,text})` 接收最多 2000 字消息。`chat.grant({id,root})` 的绝对根只允许可信主进程从系统选择器提供。`chat.inspect({id,tool,arguments})` 仅允许列表、文件名搜索、属性、空间统计。`chat.approve/resume/undo({id,operation_id,revision})` 必须来自独立用户按钮，绑定最新计划摘要和当前根授权。

快照含 `id/title/mission_id/messages/grant/operation/messages_truncated`。消息有角色、文本、种类、数据和时间。授权输出只含目录名和 token，不输出绝对根；每次快照重新核对根身份，已替换目录的授权显示失效。操作输出相对源/目标、状态及 SHA256 revision；历史计划消息保留该安全投影，执行结果保留逐项核验布尔证据，不包含内部根和身份数据。最近 30 条消息再按 46 KiB 裁切；较早记录仍存于数据库，`messages_truncated=true` 明示省略，当前不提供历史分页接口。只读消息递归裁剪 `data` 内列表至 8 KiB，保留错误并明确标记不完整。

## 模型与权限

会话 Mission 固化三个角色配置；M10 规划只调用该 Mission 的固定 Main 模型。Computer 是受限程序工具执行器，本轮不调用其模型，Browser 不参与。缺失 Main 凭据时给出明确错误，禁止回退供应商。凭据由既有 Electron 私有初始化传入内存，本模块不读取环境文件。

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
