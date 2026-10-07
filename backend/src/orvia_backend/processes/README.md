# V4-009 普通 Windows 用户进程

独立 Computer 工具，只管理可核验的同用户、普通令牌、非保护及非关键 Windows 进程。启动、等待、温和关闭和强制终止分别准备并原生确认，任何一次批准只消费一次。`exited` 只证明准确进程退出，`still_running` 只证明仍运行，不声称目标业务完成。

## 结构与依赖

- `native.py`：Windows HANDLE、令牌/SID/保护/关键 PID、程序 SHA256、原始创建身份和实际操作。
- `service.py`：会话范围、准确审批包、单次 SQLite 账本、有限结果及删除保护。
- `__init__.py`：`ProcessService`、`ProcessError` 公共入口。

沿用 Python 3.12、psutil 7.2.2、aiosqlite 和标准库 ctypes；无新依赖、模型或系统配置安装，不调用三个角色模型。仅 Windows；不管理 WSL 内部任意 Linux 进程，不接管终端或按模糊名称批量终止。

原生保护常量按Microsoft [WinBase.h](https://raw.githubusercontent.com/microsoft/win32metadata/main/generation/WinSDK/RecompiledIdlHeaders/um/WinBase.h)及[TokenInformationClass](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ne-winnt-token_information_class)核对；实际API不可用或令牌字段不可读时关闭能力。PID创建/等待/终止沿用Windows已核验HANDLE，`WM_CLOSE`只是应用关闭请求，应用可拒绝。

## 权限边界

程序路径仅由主进程原生单选 `.exe` 提供，可选 cwd 同样原生选择，默认准确程序父目录。Computer `selected_file('computer', ...)` 和 `PathPolicy` 拒绝链接、联接、ADS、UNC 和凭据/内部目录；native 再次独立核验可执行普通文件与实际权限。参数完整展示且不提供自由环境变量，native 不继承角色 Keys、代理或敏感环境。

目标绑定 PID、`create_time`、原始 FILETIME `creation_ticks`（100ns 十进制字符串）及可执行路径/SHA256。JS 浮点创建时间不足以替代精确 ticks。PID 复用、程序内容变化、SID 不同、管理员/未知令牌、AppContainer/UIAccess/未知隔离状态、受保护/关键进程或权限不可读取均拒绝。拒绝 Orvia 自身、祖先及未直接登记自有关键子进程；不能因本模块程序派生后代就泛称所有后代可管理。其它已有 Job 的目标保守拒绝。清单缓存只便于展示，预览、原生批准前 `review` 和动作使用的同一 HANDLE 都重新核验身份，缓存/服务声明不能授予权限。

重启丢失 native 的直接启动归属登记时，只有用户明确 `preview_action`/`review` 遇到归属保护拒绝，服务才读取当前会话一条 `action=launch/status=still_running/verified=true`、PID/create_time/精确ticks完全相同的 SQLite 事实。`restore_launched` 在准确 HANDLE 上重新核验原完整身份、程序 SHA256、SID、普通令牌、关键/保护/隔离状态后登记；**登记不是动作批准**，仍须新的操作身份和逐次原生确认。不在启动或 list 批量恢复，不从 unknown/取消/其它会话/无正文尝试推断归属。正文最近32条淘汰、会话删除或身份/程序变化后没有恢复来源，保守拒绝。native归属内存上限256，超额可丢弃旧归属，但只能依上述严格事实按目标恢复。

温和关闭只向准确 PID 顶层窗口发送 `WM_CLOSE`，不读取标题或窗口内容；`close_sent` 记录是否实际投递。没有窗口或拒绝关闭时保留 `still_running`，不会自动升级终止。强制 `TerminateProcess` 必须另一个独立操作身份及原生批准，可能丢失未保存内容或留下不完整文件，不能通用撤销。等待仅观察，超时不关闭目标。

启动在挂起实际新进程 HANDLE 上核验 SID、普通令牌、保护、关键进程及实际程序 SHA256 后恢复；失败时未释放的自有挂起进程才回收。已释放程序不会因等待超时、会话删除或 Orvia 服务关闭被主动终止。外部系统 Job 或程序自身行为仍可能影响其存活，不承诺它永远运行。

普通程序可按其实际用户权限读取/改变文件或联网，当前模块不是沙箱，不限制 CPU 或磁盘配额。准确程序的退出不代表其启动的其它进程、外部 broker 或全部业务已完成。venv `python.exe` 可能是 redirector，真实验收使用 base Python 私有合成副本，避免把 launcher 退出称为脚本或后代完成。没有原子文件系统沙箱保证，不承诺阻止普通账户并发替换全部隐式依赖。

## 公共接口

`ProcessService(store, chat, computer, native=None)` 可注入同步 native fixture 进行默认测试；生产使用真实 `native` 模块。

| 方法 | 输入 | 输出/行为 |
|---|---|---|
| `open()` / `close()` | 无 | 启动仅恢复未知；关闭只等当前原生操作，不杀已释放程序 |
| `list(cid)` | 会话 | `{processes,truncated,unavailable_reason}`，最多50条/48KiB |
| `preview_launch(cid, executable, args, cwd=None, wait_seconds=3)` | native 准确程序/目录、完整参数 | `ProcessPreview`，零启动 |
| `preview_action(cid, action, pid, create_time, creation_ticks, wait_seconds=3)` | `wait/close/terminate`，准确创建身份 | `ProcessPreview`，零动作 |
| `review(cid, operation_id)` | 原准备身份 | 同一完整包及现查，不创建新身份或暗中改批准内容 |
| `execute(cid, operation_id, revision)` | 原生准确一次批准 | `ProcessExecution`，启动前持久化 running |
| `status(cid, operation_id)` | 本会话操作身份 | 持久化事实，等待过程中可只读查看 |
| `history(cid)` | 会话 | `{executions,truncated}`，最多10条/48KiB |
| `has_unresolved(cid)` / `forget_previews(cid)` | 内部管理入口 | running/unknown 阻止永久删除；撤销内存准备 |

`Identity` 为 `{pid,name,executable,create_time,creation_ticks,sha256}`，不含真实 cmdline、env、SID、窗口文本。`ProcessPreview` 为 `{id,operation_id,revision,action,target,launch,wait_seconds,purpose,risk}`；`launch` 含 `{name,executable,sha256,args,cwd}`，target 与 launch 按动作互斥，完整 JSON ≤48KiB。内存最多20份，跨重启失效。

`ProcessExecution` 为 `{id,operation_id,revision,action,status,target,exit_code,started_at,finished_at,verified,close_sent,error}`。状态 `running/exited/still_running/unknown/failed`；`verified` 仅表示已核验准确进程退出或仍运行，非业务成功。错误仅稳定 `{code,message}`。native明确安全前置拒绝记 `failed`；可能执行但未完整核验记 `unknown`，绝不自动重试。

时间条件为1～15秒，默认3，针对实际目标等待；权限/程序哈希、枚举和原生创建收尾另有有限预算，原生线程不能安全硬取消，不把等待3秒称为整个 IPC 必然3秒，不能硬保证系统内核/磁盘阻塞时的2秒收尾。参数最多16项，每项1000字符，实际 JSON 总8KiB；不允许 NUL 或密钥/敏感字段样式。未知输出不授予后续操作。

## SQLite、取消与删除

`process_attempts(cid,operation_id,revision,state)` 为每会话128次独立无正文事实，启动任何动作前事务写入 `running`，不随缓存或正文淘汰。`process_executions(cid,operation_id,data_json)` 保留最近32条；历史展示最多10条/48KiB。永久删除仅事务清这两表和审批缓存，不触碰用户应用、原件或已经启动的程序。

启动事务、预览缓存最终写入、review及结果最终事务检查会话和删除墓碑；review至消费间撤销也拒绝发出 native 动作。删除账本或墓碑后的迟到响应不能恢复正文。running/unknown 阻止永久删除；已核验 still_running 是已知操作结果，不因程序仍运行自动阻止删除或自动杀程序。

重启仅将遗留 running 和对应正文事务改 unknown，原有 unknown 事实保持，不自动启动/恢复批准/重发。通信取消后保持原生线程所有权直到实际收尾，保存 unknown 和已获得的准确目标身份；重复取消也不能丢弃后到启动。服务关闭等待当前操作，不能把线程等待取消当作目标退出或自动强杀许可。

## 试用

开发启动后进入进程面板，刷新可操作目标。启动时原生选择准确普通 `.exe`、填写完整参数，可另选目录；准备后核对路径/SHA256/参数/等待及风险，逐次原生批准。等待、温和关闭和强制终止均选择清单中的准确目标后单独准备，批准时核对创建身份和未保存内容风险。温和关闭返回仍运行时，只有再次选择强制终止并完成独立批准才终止。

## 验证与限制

累计38个不同服务用例有有效通过证据，其中34个真实临时 SQLite＋mock native、4个真实服务/native。初始24项通过（`service.xml`），包含单次账本在调用前落盘、完整 argv/cwd、close 不升级、wait 不杀、权限拒绝、PID精确ticks变化、程序/cwd变化、跨会话与错误版本、最终 native guard、重启 unknown、128尝试、历史32/10、晚墓碑不恢复正文和两次通信取消仍保留线程。新增 review 至消费撤销目标通过并复验准确启动（`service-revocation.xml`，2通过，1新增）。

真实服务/native3目标已通过（`service-real.xml`，8.49秒）：合成 private base Python 在中文/空格程序及cwd启动 exit7；启动后仍运行再另批 wait 获得 exit9；隐藏合成窗口拒绝 WM_CLOSE，实际 `close_sent=true/still_running` 后另一个 operation 批准 terminate 获得实际退出码0xE009，旧 close 批准重放拒绝。marker准确匹配目标PID后的窗口目标最小复验也通过（`service-window.xml`，1通过）。只对自有合成程序进行关闭/终止，测试清理同样使用准确身份，不碰用户真实应用；无云或真实 Keys。

恢复范围最终最小集合 `service-restore-final.xml` 11通过（10新增，1既有迟到删除保护），包括同会话已核验启动来源恢复归属后另批动作、unknown/未核验/跨cid/精确ticks变化/伪造PID/正文淘汰/程序变化均零恢复。一个实际目标先准确启动合成进程，清空该目标 native归属登记，实际 inspect 拒绝后从 SQLite 准确来源恢复，旧launch事实保持，新批准 terminate 才实际退出；该集合最终3.66秒。

主要实际命令（项目根目录）：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_processes.py -q --basetemp=artifacts/test-results/V4-009/service-data --junitxml=artifacts/test-results/V4-009/service.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_processes.py -k real_service -q --basetemp=artifacts/test-results/V4-009/service-real-data --junitxml=artifacts/test-results/V4-009/service-real.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_processes.py::test_revocation_during_review_to_consume_prevents_native_action backend/tests/test_v4_processes.py::test_sqlite_launch_freezes_exact_args_cwd_consumes_before_native_no_replay -q --basetemp=artifacts/test-results/V4-009/service-revocation-data --junitxml=artifacts/test-results/V4-009/service-revocation.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_processes.py::test_real_service_native_exact_launch_wait_close_and_separate_terminate -k window-ignore -q --basetemp=artifacts/test-results/V4-009/service-window-data --junitxml=artifacts/test-results/V4-009/service-window.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_processes.py -k 'restor' -q --basetemp=artifacts/test-results/V4-009/service-restore-final-data --junitxml=artifacts/test-results/V4-009/service-restore-final.xml
```

证据统一在 Git 忽略的 `artifacts/test-results/V4-009/`，native目标、Application协议、桌面及Electron结论由主 Agent 在 PROGRESS记录。真实管理员/系统/其他用户目标不进行破坏性测试，权限边界使用受控 mock；真实用户程序、全部第三方应用、独立 Windows机器和人工原生 dialogs 未覆盖。不安装依赖、不push、不发布或重建安装包，不提前实现后续模块。
