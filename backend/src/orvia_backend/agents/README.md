# LangGraph 三 Agent（M05）

## 用途和结构

本模块把 Main、Computer、Browser 固定为同一 Python 后端中的逻辑角色。`graph.py` 使用 LangGraph `StateGraph` 和 SQLite `AsyncSqliteSaver` 编排规划、动作计划、审批暂停、执行、核验和完成判断；`roles.py` 固化能力表，并让未配置 Tavily 的 Browser 明确返回不可用。

## 输入输出与公共接口

`MissionGraph(store, checkpoint_path)` 是异步上下文管理器。`start(state, thread_id)` 接收合成任务目标、授权根和已校验动作列表，返回 `awaiting_approval` 或 `completed/failed` 状态；`approve_and_resume(thread_id)` 从 SQLite checkpoint 恢复并继续执行。Application 暴露 `mission.run` 与 `mission.approve`，仍只接受可信主进程私有 JSON Lines。

Main 只能规划和完成判断，Computer 只能准备/执行已经审批的 M04 动作，Browser 经 M07 BrowserService 提供只读搜索与网页读取接口，当前图不自动调用它。图状态不保存 Key、模型响应原文或任意命令。

## 依赖、运行和测试

Python 3.12、LangGraph 0.6、`langgraph-checkpoint-sqlite`、aiosqlite、Pydantic。依赖版本写入 `backend/uv.lock`。

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_agents_graph.py backend/tests/test_agent_roles.py backend/tests/test_application_actions.py
```

测试使用临时 SQLite checkpoint、合成目录和 M04 真实文件动作，不调用真实模型或搜索服务。

## 权限边界与已知限制

LangGraph 节点不能自行扩大 Computer 授权；所有写入仍经过 M04 审批账本。checkpoint 只保存编排状态，文件事实以 M04 账本和执行核验为准。M05 使用程序提供的合成动作列表，Main 的真实模型规划仍未开放；M07 HTTP/Playwright 只读服务已可独立调用；未配置 Tavily 时不产生伪造搜索结果。
