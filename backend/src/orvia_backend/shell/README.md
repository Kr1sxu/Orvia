# V4-008 普通账户 Shell

独立 Computer 工具，检测本机已有 PowerShell、Windows PowerShell、Git Bash 和普通 WSL 发行版。完整脚本、解释器身份、工作目录、显式输入、预算与核验条件经可信主进程原生逐次批准后才执行。退出码零记录为 `exited`，不会称作业务完成。

## 结构与依赖

- `service.py`：审批包、输入全文版本、SQLite 单次尝试、状态/核验、逐文件回传及会话删除。
- `runtime.py`：实际解释器检测、普通权限启动、输出预算、超时取消和自有进程回收。
- `__init__.py`：`ShellService`、`ShellError` 公共入口。

复用 Python 3.12、aiosqlite、Computer `PathPolicy` 和项目现有进程支持，不安装解释器、不新增模型或依赖、不更换三个角色配置。本机实际 PowerShell 7、Windows PowerShell 5.1、Git Bash 服务执行均已通过，准确版本和 runtime 检测记录见 PROGRESS。WSL 缺少普通发行版或独立子进程回收先决条件时明确不可用；Docker 内部发行版不能冒充用户 Shell，本机无普通发行版，不称 WSL 已完成真实执行验收。

## 权限与路径

这是普通账户任意脚本执行，**不是 LPAC 沙箱**。默认工作目录为应用私有 `<data>/shell/<cid>/<run_id>/work`；输入副本与产物目录分别为同级 `inputs`、`output`，脚本通过 `ORVIA_INPUT_DIR`、`ORVIA_OUTPUT_DIR` 访问。用户可另行原生选择普通工作目录与最多三个输入原件，主进程才可向后端提供这些路径。

目录和副本不是文件或网络隔离。脚本仍可能在当前普通账户权限内读取或改变其它文件、联网及创建副作用；Job/取消不会回滚这些副作用。原生确认显示完整内容，字符串检查不能证明安全。runtime 拒绝已提权宿主，清除密钥环境并保留必要运行环境，不传模型凭据。敏感字段/密钥样式脚本在准备阶段拒绝，但不承诺识别所有任意编码的密钥。

任何输出、模型草稿、文件、MCP 或 Skill 声明均不能批准后续动作。不会接管用户已有终端/IDE，不自动升级权限、安装环境、重复执行或导出文件。

## 公共接口与字段

`ShellService(store, chat, computer)` 的 `open()` 仅建表和将遗留 `running` 转为 `unknown`。`close()` 设置全部当前任务取消并等待实际回收，不启动新任务。

| 方法 | 输入 | 输出/行为 |
|---|---|---|
| `detect()` | 无 | `{interpreters}`，行含 `id,label,executable,version,sha256,available,reason,distro` |
| `preview(cid, interpreter_id, script, timeout_seconds=20, expected_stdout=None, output_names=[], cwd=None, inputs=[])` | 准确脚本，native 目录/输入 | `ShellPreview`，零执行 |
| `review(cid, run_id)` | 本会话准备身份 | 原完整包，重新核验解释器/输入/目录；不暗中更新批准内容 |
| `execute(cid, run_id, revision)` | 完整原生批准的准确包身份 | `ShellExecution`，单次消费、无自动重试 |
| `status(cid, run_id)` / `cancel(cid, run_id)` | 本会话执行身份 | 持久化当前执行；取消只通知当前自有任务 |
| `history(cid)` | 会话 | `{executions,truncated}`，最多十条/48KiB |
| `export_preview(cid, run_id, name)` | 核验记录中的产物名 | 准确大小、SHA256 和回传 revision |
| `export(cid, run_id, name, path, revision)` | native 另行批准的新文件路径 | `{filename,bytes,sha256,verified:true}` |
| `has_unresolved(cid)` | 会话 | `running/unknown` 是否阻止永久删除 |
| `forget_previews(cid)` / `purge_files(cid)` | 内部删除/撤销入口 | 撤销内存批准；仅清私有任务树，拒重解析路径 |

`ShellPreview` 包含 `id,run_id,revision,interpreter,script,cwd,inputs,output_names,timeout_seconds,expected_stdout,budgets,purpose`；`inputs` 行为 `{name,path,bytes,sha256}`。revision 绑定完整脚本和输入全文哈希，不只裁剪片段。解释器版本/可执行 SHA256、目录身份或输入变化均拒绝旧批准；native 执行前读取同包，真正启动前再次核验。

`ShellExecution` 包含 `id,run_id,revision,interpreter_id,status,exit_code,stdout,stderr,stdout_truncated,stderr_truncated,children_reaped,started_at,finished_at,verification,outputs,error`。状态为 `running/exited/timed_out/cancelled/unknown/failed`。产物行为 `{name,bytes,sha256}`，错误仅稳定 `{code,message}`。

`verification.status` 为 `passed/failed/not_requested/unknown`。显式条件只是 stdout 包含准确文本、指定产物存在并满足普通文件/大小/全文 SHA256 条件，不能证明一般业务完整或内容语义正确。非零退出、超时、取消、输出截断、回收未确认不能 `passed`；未声明条件的零退出为 `not_requested`。

## 固定预算与事实

| 项目 | 上限 |
|---|---|
| 脚本 | UTF8 16KiB；PowerShell 私有文件为 UTF8 BOM，Bash 为 UTF8 |
| 原生审批包 | 实际 JSON 48KiB；内存最多20份 |
| 运行时间 | 1～60秒，默认20；预算针对实际运行 |
| 输入 | 最多3个普通独立文件，单10MiB、合计30MiB；全文复核并复制 |
| stdout / stderr | 各16KiB，合计32KiB；JSON转义膨胀会进一步截断 |
| 核验文本 | 可选1～1000字符 |
| 指定产物 | 最多10个普通 leaf 文件名，单1MiB、合计2MiB；拒链接/硬链接/ADS/设备名 |
| 尝试事实 | 每会话128次，独立无正文账本不淘汰 |
| 执行正文 | 最近32条，展示最多10条/48KiB |

身份检测单次探测预算25秒，准备读取和复制另受3/30MiB输入量及审批包约束；不能把运行20秒称为整个准备/IPC流程的20秒总时限。极端 Windows 原生创建/回收阻塞可能超额，runtime 必须保留后到 Job 所有权直到实际回收，不能靠硬丢弃等待伪造已回收。指定产物大小是回查/回传预算，不能限制任意普通权限脚本实际磁盘写入。私有任务文件保留到会话永久删除，最多128个已尝试任务加20个准备；重启清理无独立尝试账本的规范 UUID 私有准备目录，保留已尝试及非规范未知目录。没有全盘空间配额保证，需用户自行控制输入与脚本。

`shell_attempts(cid,run_id,revision,state)` 在启动前事务持久化 `running`；`shell_executions(cid,run_id,data_json)` 保存实际有限结果。缓存丢失、历史正文淘汰、重启、取消和未知结果都不授予旧批准重跑权限。重启不复连、不恢复批准、不重新执行。执行前、预览缓存写入前和最终事务均检查会话及删除墓碑；迟到结果不能恢复被删除正文。

永久删除前运行中和未知记录阻止删除；可删除时仅清应用私有会话树，任何重解析路径导致安全停止清理。输入原件、原生工作目录和已回传成品保留。逐文件回传再次读取、核验批准 SHA256，`x+b` 独占新建、fsync、读回，绝不覆盖现有文件。

## 试用

运行现有开发启动流程，在 Shell 面板检测环境，选择准确解释器，输入合成脚本及核验条件。可选择工作目录与输入；准备后核对完整原生审批，执行结束查看真实退出/回收/核验状态。需要成品时再选核验产物，原生选择新的保存文件。取消原生批准零执行，正在执行取消只请求自有进程回收。

PowerShell 合成示例：

```powershell
Write-Output '合成执行'
[IO.File]::WriteAllText((Join-Path $env:ORVIA_OUTPUT_DIR '合成.txt'),'合成产物')
```

声明 stdout 条件 `合成执行` 和产物 `合成.txt`。Bash 示例：

```bash
printf '合成执行\n'
printf '合成产物' > "$ORVIA_OUTPUT_DIR/合成.txt"
```

## 验证

测试只使用 `backend/tests/test_v4_shell.py`、临时 SQLite、合成目录/脚本及 mock runner；实际本机解释器用例另行标注。无真实云模型、无真实密钥或用户预存文件。所有产物在 Git 忽略的 `artifacts/test-results/V4-008/`。

最终43个不同服务用例有有效通过证据：38个真实 SQLite＋mock runner 目标（`service-final.xml`）及5个真实本机解释器目标（`service-real.xml`）。覆盖晚墓碑预览清理、runtime异常未知且不可重试、硬链接产物拒绝、正文淘汰不删除单次账本、启动清理只作用无账本的规范私有目录及原有未知事实保留。首次全文件运行 fixture 误用 `app.gateway`，修为 `app.computer` 后32通过，另1个 SQLite Row/tuple断言修正后最小复验通过；这些初始错误保留在证据，最终针对启动恢复/清理改动重跑38个受影响服务目标全部通过。

实际服务目标分别在 PowerShell 7、Windows PowerShell 5.1、Git Bash 执行完整批准脚本，读取原生中文/空格文件副本、写入指定产物、核验 SHA256、单文件新建回传，再清理私有目录并核验输入原件/工作目录/导出成品保留。实际 PowerShell 超时与脚本启动 marker 出现后的取消均返回已回收的已知中断、核验 `unknown`，旧批准重放拒绝。这五项共18.86秒，不用 mock 退出码冒充真实执行。

实际命令：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell.py -q --basetemp=artifacts/test-results/V4-008/service-fix-data --junitxml=artifacts/test-results/V4-008/service-fix.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell.py::test_sqlite_single_approval_before_start_and_exit_not_business_completion -q --basetemp=artifacts/test-results/V4-008/service-one-data --junitxml=artifacts/test-results/V4-008/service-one.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell.py::test_preview_late_tombstone_clears_private_directory backend/tests/test_v4_shell.py::test_runtime_exception_is_unknown_not_retried_or_deletable backend/tests/test_v4_shell.py::test_hardlinked_output_cannot_be_verified_or_exported backend/tests/test_v4_shell.py::test_history_bytes_cap_and_body_eviction_never_remove_attempt_fact -q --basetemp=artifacts/test-results/V4-008/service-boundaries-data --junitxml=artifacts/test-results/V4-008/service-boundaries.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell.py::test_startup_clears_only_unattempted_canonical_private_task_directories backend/tests/test_v4_shell.py::test_startup_unknown_no_automatic_execution_and_delete_blocked backend/tests/test_v4_shell.py::test_runtime_exception_is_unknown_not_retried_or_deletable backend/tests/test_v4_shell.py::test_export_separate_approval_hash_recheck_no_overwrite_and_user_files_preserved -q --basetemp=artifacts/test-results/V4-008/service-cleanup-data --junitxml=artifacts/test-results/V4-008/service-cleanup.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell.py -k 'not real_service' -q --basetemp=artifacts/test-results/V4-008/service-final-data --junitxml=artifacts/test-results/V4-008/service-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell.py -k real_service -q --basetemp=artifacts/test-results/V4-008/service-real-data --junitxml=artifacts/test-results/V4-008/service-real.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_shell.py::test_preparation_rejects_invalid_limits_without_start -q --basetemp=artifacts/test-results/V4-008/service-limits-data --junitxml=artifacts/test-results/V4-008/service-limits.xml
```

runtime 分层测试、Electron 原生确认流程与最终接口验证结论由主 Agent 在 PROGRESS 记录。未运行项目不标为完成；不把 mock 或构建通过当实际执行证明。不自动 push、发布或重建安装包。
