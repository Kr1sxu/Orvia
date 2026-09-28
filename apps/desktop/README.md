# Electron 桌面模块（M10）

用途：以对话完成授权目录观察、计划审批、执行核验与受限撤销。新建/历史会话在侧栏，中央消息流展示事实卡片，底部输入框持续提问，设置保留固定模型与凭据管理。不提供自动任务、技能广场、团队管理等入口。

## 结构

- `src/main/main.ts`：窗口、来源校验、系统目录选择及串行业务 IPC。
- `src/main/backend.ts`：私有 Python stdio 客户端；`chat-contracts.ts` 校验会话输入/快照，`chat-errors.ts` 提供固定中文错误。
- `src/main/credentials/`：开发凭据加载、发布 safeStorage 与后端同步，详见该目录 README。
- `src/main/preload.ts`：固定 contextBridge 函数；`src/shared/api.ts` 定义类型。
- `src/renderer/main.tsx`：欢迎页、会话、输入与异步状态；`ChatCards.tsx` 展示工具与计划证据；`SettingsPanel.tsx` 管理凭据。

## 输入输出与公共接口

所有函数返回 `{ok:true,result}` 或 `{ok:false,message}`，错误不回显原始请求/供应商正文。

| preload 函数 | 输入与结果 |
|---|---|
| `chatList()` | 最多100条 `{id,title}` 历史会话 |
| `chatCreate({client_request_id,title})` | 幂等创建会话与固定 Mission |
| `chatGet({id})` | 读取会话事实快照 |
| `chatSend({id,request_id,text})` | 最多2000字，固定 Main 规划，返回新快照 |
| `chatChooseDirectory({id})` | 主进程系统选择器；取消无授权变化，成功返回会话 |
| `chatInspect({id,tool,arguments})` | 只允许列表、文件名搜索、属性和空间统计 |
| `chatApprove/Resume/Undo({id,operation_id,revision})` | 当前会话、根授权、最新计划及版本都有效才执行 |
| `health/settings/saveCredential/removeCredential` | 连接与固定模型设置，发布模式保存/移除加密凭据 |

旧 `missions/createMission` 与 M09 只读窄接口保留兼容；界面不再以草稿面板作为任务入口。没有通用方法转发、绝对根输入或任意命令接口。目录授权不包含文本读取/系统权限。M09 的开发测试目录环境变量入口已移除；E2E 只在测试启动器中替换模型与目录对话框。

## 配置与运行

依赖沿用根锁文件：Electron、React、TypeScript、Vite、Zod，无新增运行依赖。开发 Python 固定为 `backend/.venv/Scripts/python.exe`；发布使用安装资源，不回退系统 Python。开发数据默认 `.orvia/`，测试用 `ORVIA_DEV_DATA_DIR` 隔离；发布忽略该变量。

根目录运行 `npm run build` 后 `npm start`。示例：选择只含合成 `a.txt` 的目录 → 查看列表 → 发送“把 a.txt 重命名为 b.txt” → 核对源/目标与版本 → 独立批准 → 查看程序核验 → 必要时撤销最近变更。重新打开会话后必须重新授权原根。未授权的消息不会在选择目录后自动重放，请再次提交目标。

主动发送会把必要对话与文件元数据发送给固定 Main 云服务；不自动发送文件正文。开发主进程读根 `.env.local`，发布只用 safeStorage，不回退明文。输入的 API Key 提交即清空，不进入消息。

## 验证

L0：`npm run check`、`npm run build`。L1：`npx vitest run apps/desktop/tests/chat.test.ts apps/desktop/tests/backend.test.ts apps/desktop/tests/protocol.test.ts`。L2：`npx vitest run tests/integration/m10.test.ts`。L3：先构建，设置 `ORVIA_TEST_MODULE=M10` 后运行 `npx playwright test tests/e2e/m10.spec.ts`。

报告、数据库和截图均在忽略的 `artifacts/test-results/M10/`；准确命令与结果见根 PROGRESS。E2E 保留真实 Electron/Python/SQLite/文件网关，以测试专用启动器替换模型和凭据来源，系统选择器用测试侧 mock；不触发真实模型。显式真实 Main 合成预检与规划测试脚本单列，不属于默认测试。

## 权限与限制

sandbox/contextIsolation 开启，Node/webview 禁用，拒绝联网、导航、新窗口和权限申请。所有入口检查主窗口、顶层 frame、精确 URL、参数个数与结构；UI 单操作锁及后端会话锁避免重复提交。原始错误不显示，模型文本标为建议，程序卡片才代表执行事实。

私有 UTF-8 JSON Lines 每行64 KiB；会话请求65秒客户端超时，对应模型50秒总预算，最多三次请求，每次1024输出token；其他开发请求仍5秒，发布20秒。当前展示请求阶段，无伪造百分比或token流式输出。关闭中断不自动重放；历史快照不是执行恢复。

历史只显示最近30条并按46 KiB裁剪，较早记录仍保存，当前无分页。只读卡片8 KiB，截断明确提示。没有托盘、自动重连、通用取消或自动任务；稳定性扩展属于M11。M08安装包未随本轮重建。旧无身份快照计划拒绝审批；部分撤销/不确定中断需人工核对，不承诺任意回滚。外部进程并发文件竞态不能由路径检查完全消除。
