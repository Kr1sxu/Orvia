# Computer 只读工具（M03）

## M13 单文件附件与新建导出

`read_attachment('computer', selected_path)` 仅供主进程选择器经过Application/ChatService进入，一次性读取最多10 MiB的允许文档；复用PathPolicy根链、相对路径和句柄身份，不授予父目录访问，不改变现有grant。`export_document('computer', selected_path, bytes, format)` 仅接收程序生成且已预览确认的Markdown/JSON，复用`PathPolicy.new_file`验证新文件名和父目录，通过`x+b`拒绝覆盖、fsync及读回核验，不写任意模型内容。角色不是computer一律拒绝。

导出审批与M04整理审批分离：保存框只确认一个预览版本的新建文件，不能替代移动/重命名审批；导出不包含删除或撤销接口。M16 复用相同 `export_document` 的路径策略、独占创建与读回验证，固定允许 `.docx/.pptx/.pdf` 且每份最多2 MiB，内容由后端固定生成器提供，renderer 不能传写入字节。详见 `../documents/README.md` 与 `../publication/README.md`。底下M03“只读”描述属于原工具集合。

## M10 接入更新

M03 只读能力已通过对话卡片接入。`ComputerGateway.authorized_root(mission_id)` 供会话动作入口复核当前授权根身份；重启、根替换后需重新选择目录。PathPolicy 在 resolve 之前检查原始路径链，拒绝链接、Windows 联接与 ADS。

M04 ActionService 的计划现包含 SHA256 revision、根/源身份。审批和执行前重新核对，计划内重复源/目标或父目录顺序冲突在审批前拒绝；核验比较账本 after 身份。中断步骤不能证明未执行时拒绝重放；撤销开始就记录部分撤销状态。旧无快照计划需重新生成。对话入口另行验证会话、最新 operation、版本与当前 grant，旧私有接口不向 renderer 透传。

目标回归见 `backend/tests/test_m10_action_safety.py` 和 `test_chat.py`，仅合成目录、临时数据库与模型 mock。以下 M03 段落保留原工具边界；当前整体桌面行为见 chat/README。

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
