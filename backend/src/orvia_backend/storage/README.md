# M02 SQLite 存储

## 用途与结构

`__init__.py` 提供异步 `Store`，保存 Mission 草稿、模型快照、M04 文件操作账本和 M06 任务范围上下文。当前 schema 版本仍为 1；M04/M06 在现有版本内幂等创建业务表和 FTS5 表，使用 `PRAGMA user_version` 拒绝未来数据库。

## 输入、输出与公共接口

- `Store(path: Path)`：路径只能由可信后端启动配置提供。
- `await open()` / `await close()`：初始化、迁移或关闭数据库。
- `await create_mission(MissionCreate) -> Mission`：按客户端 UUID 幂等创建；同 UUID 不同标题报固定错误，不包含原文。
- `await get_mission(str) -> Mission | None`：查找单个草稿。
- `await list_missions() -> list[Mission]`：按时间及 ID 倒序列出最新最多 20 条，限制 stdio 响应大小。历史草稿仍可按 ID 查询，目前无分页接口。
- `await create_operation(operation)`、`get_operation(id)`、`update_operation(...)`：保存计划、逐步状态和核验快照。
- `await recover_operations()`：重启时把运行中或已审批未执行的计划标成 `interrupted`，不自动重放文件动作。
- `replace_context_document`、`search_context`、`clear_context`：原子替换、检索和清理 Mission 范围索引。
- `set_preference/get_preferences`、`update_summary/get_summary`：保存显式偏好和版本化摘要。

读取会重新验证完整契约。损坏的快照引发错误，不会替换成当前模型配置。

## 依赖与配置

Python 3.12、aiosqlite、domain 契约。SQLite 启用 WAL、外键和 2000 ms busy timeout。同一实例使用异步锁串行访问，同一数据库的写事务使用 `BEGIN IMMEDIATE`。不存在的父目录由 `open()` 创建。

## 运行方式与示例

由后端服务启动，不提供接受渲染进程路径的 RPC。

```python
from pathlib import Path
from uuid import uuid4
from orvia_backend.domain import MissionCreate
from orvia_backend.storage import Store

async def save_draft(trusted_data_dir: Path):
    store = Store(trusted_data_dir / "orvia.sqlite3")
    await store.open()
    try:
        return await store.create_mission(
            MissionCreate(client_request_id=uuid4(), title="合成草稿")
        )
    finally:
        await store.close()
```

## 测试方式

根目录执行 `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_storage.py --basetemp=artifacts/test-results/M02/storage-temp`。真实临时 SQLite 覆盖创建、并发幂等、冲突、重启持久化、迁移失败回滚、未来版本拒绝、SQL 快照禁止更新及离线损坏检测；无 mock、无模型。

## 权限边界与已知限制

只访问可信启动配置指定的数据库；密钥不入库。SQL trigger 禁止修改现有模型快照，但数据库不加密，也不抵御有权直接修改数据库文件的本机用户。上下文索引只保存调用方提交的文本块和来源，不自动读取文件；无自动备份、跨版本降级、分页或多设备同步，未来版本拒绝打开。

## V4-010 晚到索引

`replace_context_document`最终BEGIN IMMEDIATE写事务检查chat_deletions；分词期间已永久删除的会话不能再插入正文/FTS。没有chat记录的原有独立目录Mission仍可用，数据库FK继续限制不存在的Mission。实际墓碑拒绝及独立Mission检索测试通过；不授予已移除资料有效来源权限。
