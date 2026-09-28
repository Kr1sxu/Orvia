# Electron 桌面模块（M01）

用途：React 显示本地连接状态；主进程持有 Python 子进程，preload 只暴露无参数 `window.orvia.health()`。

## 目录结构

- `src/main/`：窗口、IPC 权限策略、stdio 客户端、协议解析、preload。
- `src/renderer/`：健康状态页面与样式。
- `src/shared/api.ts`：渲染端公共返回类型。
- `tests/`：协议与 IPC 策略单元测试。
- `dist/`：忽略的编译输出。

## 输入输出与公共接口

`health(): Promise<HealthReply>` 成功返回 `{ok:true,result:{status:'ok',service:'orvia-backend'}}`；失败返回 `{ok:false,message}`。
主进程只接收 `orvia:health`，校验窗口、顶层 frame、精确页面 URL、零参数。
`BackendClient(root).health()` 首次启动并 hello 握手，然后按 UUID 关联响应；`stop()` 发送 EOF 并等待关闭，1.5 秒后终止自有进程。
协议 v1 使用 UTF-8 JSON Lines；每行最多 64 KiB（含换行），5 秒超时，最多 16 个待响应请求。不兼容版本或失联后不自动重试。

## 依赖与配置

版本由根 `package-lock.json` 锁定；Electron、React、TypeScript、Vite、Zod。
开发 Python 固定在 `backend/.venv/Scripts/python.exe`，需要先从根 README 安装。启动使用 `-I -u -X utf8 -m orvia_backend`，只继承系统运行必要变量，不继承密钥。
不加载 `.env.local`，不需要模型服务。M01 用普通 CSS，组件库和状态库按后续需求引入。

## 运行方式与示例

从仓库根执行 `npm run build`，再执行 `npm start`。看到“健康检查通过”后点击“重新检查连接”进行第二次调用。修改源码后重新 build/start。

## 测试方式

根目录 `npm run check`（L0）、`npm run test:unit`（L1）、`npm run test:integration`（L2，真实 Python）、`npm run test:e2e`（L3，真实 Electron/Python，先 build）。报告参数见 `docs/PROGRESS.md`，结果放 `artifacts/test-results/M01/`。

## 权限边界

渲染端启用 sandbox/contextIsolation，禁用 Node/webview；拒绝新窗口、导航、权限申请及联网请求。CSP 只允许本地静态资源。渲染端不能选通道、命令或路径。
进程通过 `shell:false, windowsHide:true` 启动；stdout 专用于协议，stderr 持续消费但不持久化原始内容。应用不是操作系统安全沙箱。

## 已知限制

仅 Windows 开发环境；未打包、无托盘、无自动重连、无日志持久化、无文件操作、无模型调用。关闭窗口即退出。安装包资源定位属于 M08；Mission/凭据配置属于 M02。health 表示通信正常，不代表整个 MVP 已完成。
