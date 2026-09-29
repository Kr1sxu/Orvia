# Orvia Python 后端（M01–M13）

当前入口是对话式应用；下方M01–M07段落保留历史接口说明，当前授权与UI以 `chat/README.md` 为准。M13 `documents/` 提供显式附件本地提取、版本引用、M06检索与Markdown/JSON导出，依赖/预算/运行/测试见 [文档模块](src/orvia_backend/documents/README.md)。固定子进程解析不接收路径或凭据，Computer gateway复用PathPolicy完成单文件读与新建导出；不上传文件，不扩大目录权限。

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
- `src/orvia_backend/computer/actions.py`：M04 审批后文件动作、账本核验、恢复和受限撤销。
- `src/orvia_backend/context/`：M06 jieba + SQLite FTS5 任务范围上下文与偏好，见该目录 README。
- `src/orvia_backend/browser/`：M07 Tavily、HTTP、Playwright 只读网关；M08 PyInstaller 发布入口与冻结验收见 `packaging/README.md`，详见模块 README。
- `tests/`：协议、模块边界与合成集成测试。
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
正常后端进程不读取 `.env.local`，Key 由可信 Electron 私有管道注入内存。数据目录由主进程提供，数据库保存草稿、无密钥配置和动作账本。M03/M04 不读取 Key、不调用模型；M04 只对已审批的动作计划执行文件写操作。

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

主进程私有协议已增加 M03–M07 的工具与任务方法，renderer 仍只开放配置和草稿；不提供任意 SQL、任意模型提示词或桌面控制接口。模型适配只由受控后端代码与显式测试调用，渲染端没有模型执行入口。
这不是操作系统级沙箱；应由可信 Electron 主进程启动，禁止把 stdio 直接暴露给不可信远程端。
M04 已验证动作计划、审批、核验、恢复和受限撤销；M06 增加显式提交文本的上下文索引和偏好。仍无通用删除、覆盖、任意脚本或 renderer 写操作 UI。父进程负责超时和进程清理，EOF 关闭数据库连接后退出。

M07 增加 browser.read / browser.search，须存在的 mission_id；来源与正文证据不自动落盘。Tavily 仅以内存 SecretStr 持有，不作为模型配置。Browser 策略、Chromium 依赖和合成试用见 `src/orvia_backend/browser/README.md`。

## M14 本机打包验证

最新未签名候选版为0.2.0-rc.1，包含对话及文档能力；上文“安装包未重建”描述保留为历史模块状态。PDF/OCR冻结资源、安装包流程、升级/卸载的命令与边界见根目录 packaging/README.md、docs/PROGRESS.md。测试产物统一为 artifacts/test-results/M14/。真实本地组件测试不等于云模型/Tavily验证；生产签名和独立Windows验收经用户确认暂缓。
