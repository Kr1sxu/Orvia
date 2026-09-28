# Computer 只读工具（M03）

## 用途

提供授权目录扫描、文件名搜索、元数据、受限 UTF-8 文本读取、逻辑空间统计，以及固定运行时版本探测和必要进程概况。不创建、移动、重命名、删除文件，也不接受任意命令。

## 目录结构与公共接口

- `paths.py`：本地绝对授权根、越界和符号链接/重解析点策略。
- `files.py`：`FileTools.list_directory`、`search_files`、`get_file_metadata`、`read_text_file`、`analyze_directory_space`。
- `system.py`：`SystemTools.detect_runtimes`、`list_processes`、`run_template`，仅有 `runtime_version` 固定模板。
- `gateway.py`：Mission、`grant_id`、Computer 角色、权限和 200 次调用预算。
- `actions.py`：动作计划、审批、执行核验、恢复和最近一次受限撤销。
- `contracts.py`：Pydantic 请求契约，额外字段拒绝；可生成 `contracts/m03.schema.json`。

文件工具返回 `complete`、`truncated`、`errors` 和扫描时间。空间统计是逻辑文件字节数，不代表可释放磁盘空间。文本仅允许 `txt/md/json/csv/log` 且单次最多 256 KiB、UTF-8。

## 依赖、运行与测试

Python 3.12、Pydantic 2、`psutil`。后端应用通过 `computer.grant/revoke/status/execute` 调用，授权只在当前 stdio 连接内有效。

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_computer_files.py backend/tests/test_computer_gateway.py backend/tests/test_computer_system.py
```

测试只使用临时合成目录和 mock 进程，不调用模型、不访问用户文件。

## 权限边界与限制

授权根必须是本地普通目录；每次调用复核根身份，拒绝 UNC、越界、符号链接和 Windows reparse point。系统工具只探测固定路径，子进程无 shell、无用户环境继承、8 KiB 输出上限和超时。M04 写操作仍只能来自已持久化并显式审批的计划，拒绝覆盖和删除；renderer 目录选择 UI 尚未开放。
