# Orvia Python 后端（M01）

## 用途和目录结构

提供 Electron 子进程的 UTF-8 stdio JSON Lines 握手与健康检查。

- `src/orvia_backend/__main__.py`：进程入口。
- `src/orvia_backend/protocol.py`：请求校验与单连接握手状态。
- `src/orvia_backend/server.py`：有界读取、异步调度、响应输出。
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
阻塞读取通过 `asyncio.to_thread` 与主协程分离；单连接依次处理，不并行执行请求。

## 依赖与配置

要求 Python 3.12；运行时只用标准库。使用 uv 管理环境，pytest 为开发依赖，hatchling 为构建依赖。
M01 不读取 `.env.local`，无需模型密钥；后续模块再引入持久化、凭据和 Agent。

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

仅支持两个固定方法，不提供 shell、用户文件读写、数据库、网络、模型或桌面控制接口。
这不是操作系统级沙箱；应由可信 Electron 主进程启动，禁止把 stdio 直接暴露给不可信远程端。
M01 无任务恢复、审批、取消、进度事件和文件工具。父进程负责超时、关闭 stdin 和必要时终止进程；本服务在 EOF 后退出。
