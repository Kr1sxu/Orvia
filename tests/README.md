# 跨进程与端到端测试

用途：验证桌面与真实 Python 的通信及实际用户窗口流程。

目录：`integration/` 使用 Vitest 启动 Python；`e2e/` 使用 Playwright 启动 Electron；桌面单元测试另在 `apps/desktop/tests/`，后端单元测试在 `backend/tests/`。

输入输出：合成健康检查请求和非法帧；输出断言、JSON/JUnit 报告及窗口截图。无产品公共接口。

依赖配置：根 npm 锁文件、backend uv 锁文件；Windows Python 3.12 环境与已构建 Electron 页面。Playwright 直接使用项目 Electron，不需要下载浏览器。

运行/示例：根目录 `npm run test:integration -- --reporter=json --outputFile=artifacts/test-results/M01/integration.json`；`npm run build` 后 `npm run test:e2e`。测试本身的验证依据是真实协议响应、进程退出及 UI 状态断言。

权限边界：仅启动自有 Electron/Python 进程，不读写真实用户资料，不调用模型、不使用 API Key。生成文件只在被忽略的 `artifacts/test-results/M01/`。

已知限制：M01 不验收安装包、Agent、数据库、文件审批、真实模型或系统级安全隔离。单元测试的内存字节流不是模型 mock；L2/L3 正常链路使用真实本地进程。
