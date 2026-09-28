# Electron 桌面模块（M01–M07）

用途：React 显示本地连接、固定模型配置与任务草稿；主进程管理 Python 和凭据，preload 只暴露六个固定业务接口。

## 目录结构

- `src/main/`：窗口、IPC 权限策略、stdio 客户端、协议解析、preload。
- `src/main/credentials/`：开发凭据只读加载、发布 safeStorage、后端同步；有独立 README。
- `src/main/contracts.ts`：与后端 JSON Schema 交叉验证的 Zod 契约。
- `src/renderer/`：健康状态页面与样式。
- `src/shared/api.ts`：渲染端公共返回类型。
- `tests/`：协议与 IPC 策略单元测试。
- `dist/`：忽略的编译输出。

## 输入输出与公共接口

`health(): Promise<HealthReply>` 成功返回 `{ok:true,result:{status:'ok',service:'orvia-backend'}}`；失败返回 `{ok:false,message}`。
`settings()` 返回固定配置、Key 是否存在和凭据来源；`missions()` 返回最新 20 条草稿；`createMission({client_request_id,title})` 幂等保存草稿；`saveCredential({role,key})` / `removeCredential(role)` 仅发布模式支持。每个入口校验窗口、顶层 frame、精确页面 URL、参数个数与 Zod 参数契约。
渲染端没有 `initialize`、任意方法、SQL、数据目录选择或读取 Key 的接口。M03/M04 的 `computer.*` 观察、审批和动作接口暂由可信主进程后端预留，尚未开放 renderer 目录选择与写操作 UI。所有返回为 `{ok:true,result}` / `{ok:false,message}`，不回显异常输入。
`BackendClient(root).health()` 首次启动并 hello 握手，然后按 UUID 关联响应；`stop()` 发送 EOF 并等待关闭，1.5 秒后终止自有进程。
协议 v1 使用 UTF-8 JSON Lines；每行最多 64 KiB（含换行），5 秒超时，最多 16 个待响应请求。不兼容版本或失联后不自动重试。

## 依赖与配置

版本由根 `package-lock.json` 锁定；Electron、React、TypeScript、Vite、Zod。
开发 Python 固定在 `backend/.venv/Scripts/python.exe`，需要先从根 README 安装。启动使用 `-I -u -X utf8 -m orvia_backend`，只继承系统运行必要变量，不继承密钥。
M02 主进程读取根 `.env.local`，私有初始化请求向后端内存传入凭据；Python 不继承 Key 环境变量。发布模式只读取系统加密存储，不回退开发 Key。UI 创建草稿无需联网，不自动调用模型。
开发业务数据默认 `.orvia/app.sqlite`，可用主进程环境变量 `ORVIA_DEV_DATA_DIR` 指定隔离开发/测试目录，发布模式忽略此变量。单实例运行，关闭窗口即退出。

## 运行方式与示例

先按根 README 同步 npm/uv 依赖和 Electron 运行时，再从根执行 `npm run build`、`npm start`。看到“健康检查通过”后查看三个角色，在“草稿名称”输入合成名称并保存；关闭、重启后仍可见。修改源码或开发 Key 后重新启动，源码变更需先 build。

## 测试方式

根目录 `npm run check`（L0）；按文件选择 Vitest 的凭据/生命周期 L1、真实 Python/SQLite/Schema L2；`npm run test:e2e`（L3，真实 Electron/Python/safeStorage，先 build）。实际最小测试命令见根 `docs/PROGRESS.md`，本轮结果在 `artifacts/test-results/M02/`。

## 权限边界

渲染端启用 sandbox/contextIsolation，禁用 Node/webview；拒绝新窗口、导航、权限申请及联网请求。CSP 只允许本地静态资源。渲染端不能选通道、命令或路径。
进程通过 `shell:false, windowsHide:true` 启动；stdout 专用于协议，stderr 持续消费但不持久化原始内容。应用不是操作系统安全沙箱。

## 已知限制

仅 Windows 开发环境；未打包、无托盘、无自动重连、无日志持久化、无文件操作或 Agent 执行。草稿不是已执行任务。安装包资源定位和无开发环境机器验收属于 M08；safeStorage 已验证实际 OS 加密，但完整发布安装流程未验收。
凭据落盘后同步后端失败时，停止旧后端并明确要求重启，不能继续使用已删除 Key。极端 OS 拒绝终止且不发送 close 时的退出上限仍未验证。

M07：发布凭据选择增加 Tavily 搜索，开发主进程读取 TAVILY_API_KEY；搜索状态来自后端实际凭据存在性。模型配置仍严格三个角色，未向 renderer 开放 Browser 读取/搜索接口。

## M09 桌面整理只读界面

M09 在主进程通过系统目录选择器建立一次 Computer 目录授权，renderer 只接收任务 ID、授权 ID 和目录名摘要。目录绝对路径不会进入页面或 preload；`computer-scan` 只允许 `list_directory`、`search_files`、`get_file_metadata`、`analyze_directory_space` 四个固定只读工具，具体路径、越界、符号链接和权限检查继续由 M03 gateway 执行。

界面支持一级文件列表、文件名搜索、文件属性、逻辑空间统计和大文件清单，并展示扫描进行中、空结果、截断、不可访问、授权失效和失败提示。空间统计不会清空已经显示的文件列表。开发测试可在主进程设置 `ORVIA_TEST_DIRECTORY` 注入合成目录，发布模式始终使用系统选择器。

运行 `npm run build && npm start` 后点击“选择目录”即可试用。M09 不执行移动、重命名、创建目录、删除、审批、撤销或模型任务；授权只在当前后端连接内有效。
