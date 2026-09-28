# Orvia Python 后端（M01–M03）

## 用途和目录结构

提供 Electron 子进程的 UTF-8 stdio JSON Lines 握手与健康检查。

- `src/orvia_backend/__main__.py`：进程入口。
- `src/orvia_backend/protocol.py`：请求校验与单连接握手状态。
- `src/orvia_backend/server.py`：有界读取、异步调度、响应输出。
- `src/orvia_backend/application.py`：可信初始化、配置状态和草稿接口。
- `src/orvia_backend/domain/`：Pydantic 数据契约与导出 Schema。
- `src/orvia_backend/storage/`：SQLite 迁移、事务、幂等与模型快照。
- `src/orvia_backend/configuration/`：内存凭据、固定配置与模型适配。三个子模块均有独立 README。
- `src/orvia_backend/computer/`：M03 只读文件工具、系统探测与 Mission 权限网关，见该目录 README。
- `tests/`：协议和流读取单元测试。
- `pyproject.toml`：Python 包、版本约束和测试配置。

## 输入输出与公共接口

stdin 每行一个 UTF-8 JSON 对象，stdout 每行一个响应，诊断仅写 stderr。
请求格式为 `{ "v": 1, "id": "非空字符串", "method": "hello", "params": {} }`。
完整行最多 64 KiB（含 CR/LF）；超限帧分块消费到下一换行，返回 `INVALID_REQUEST`，不回显输入。
EOF 时最后一个没有换行的完整 JSON 也可处理，随后干净退出。

- `hello`：返回 `{ "protocol": 1, "service": "orvia-backend", "python": "3.12.x" }`，可重复。
- `health`：握手后返回 `{ "status": "ok", "service": "orvia-backend" }`。
- 成功信封：`{ "v": 1, "id": "原ID", "ok": true, "result": {} }`。
- 错误信封：`{ "v": 1, "id": null, "ok": false, "error": { "code": "INVALID_REQUEST", "message": "说明" } }`。可识别 ID 时保留 ID。
- 错误码：`INVALID_REQUEST`、`UNSUPPORTED_VERSION`、`METHOD_NOT_FOUND`、`NOT_READY`。

`Session.handle(bytes)` 处理单帧，`serve(BinaryIO, BinaryIO)` 服务连接。
M02 的 `Application.handle(bytes)` 在 hello 后接受主进程私有 `initialize({data_directory,credentials})`，一次连接仅初始化一次。`credentials.replace` 更新内存 Key；二者不对渲染进程公开。M03 增加 `computer.grant/revoke/status/execute`，只读请求必须带 Mission 与当前连接的 `grant_id`，角色固定为 Computer。
初始化后 `configuration.status({})` 仅返回无 Key 配置和存在性；`missions.create({client_request_id,title})` 保存草稿；`missions.list({})` 返回最新 20 条；`missions.get({id})` 返回指定草稿。M03 文件工具只能通过 Computer 网关调用，不开放 SQL 或任意命令。
错误增加 `NOT_INITIALIZED`、`ALREADY_INITIALIZED`、`INVALID_PARAMS`、`CONFLICT`、`NOT_FOUND`、`STORAGE_UNAVAILABLE`。接口错误只含固定说明，不序列化 Pydantic 输入或供应商原始错误。
阻塞读取通过 `asyncio.to_thread` 与主协程分离；单连接依次处理，不并行执行请求。

## 依赖与配置

要求 Python 3.12；运行时依赖 Pydantic、aiosqlite、httpx，版本在 uv.lock 固定。pytest 为开发依赖，hatchling 为构建依赖。
正常后端进程不读取 `.env.local`，Key 由可信 Electron 私有管道注入内存。数据目录由主进程提供，数据库只存草稿与无密钥配置。M03 不读取 Key，不调用模型，不操作用户文件。

## 运行方式与示例

在项目根目录执行：

```powershell
.\.venv\Scripts\uv.exe sync --project backend --locked
.\backend\.venv\Scripts\python.exe -I -u -X utf8 -m orvia_backend
```

输入以下两行，可依次获得握手和健康响应；交互环境关闭 stdin 后退出：

```json
{"v":1,"id":"hello-1","method":"hello","params":{}}
{"v":1,"id":"health-1","method":"health","params":{}}
```

## 测试方式

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests --junitxml=artifacts/test-results/M01/backend-junit.xml
```

测试使用内存流与真实处理函数，不调用模型。实际子进程通信与 Electron E2E 由根目录集成测试负责。
测试执行结果和未覆盖风险以 `../docs/PROGRESS.md` 为准。

## 权限边界与已知限制

只开放健康检查、初始化、配置和草稿方法，不提供 shell、用户文件整理、任意 SQL、任意模型提示词或桌面控制接口。模型适配只由受控后端代码与显式测试调用，渲染端没有模型执行入口。
这不是操作系统级沙箱；应由可信 Electron 主进程启动，禁止把 stdio 直接暴露给不可信远程端。
M02 只验证草稿跨重启持久化；不是执行中任务恢复，后者属于 M04/M05。无审批、取消、进度事件和文件工具。父进程负责超时和进程清理，EOF 关闭数据库连接后退出。
