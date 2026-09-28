# 跨进程与端到端测试

用途：验证桌面与真实 Python 的通信及实际用户窗口流程。

目录：`integration/` 使用 Vitest 启动 Python；`e2e/` 使用 Playwright 启动 Electron；桌面单元测试另在 `apps/desktop/tests/`，后端单元测试在 `backend/tests/`。

输入输出：合成健康检查请求、非法帧、草稿和合成凭据；输出断言、JSON/JUnit 报告及窗口截图。`integration/m02.test.ts` 对照 Pydantic JSON Schema 与 Zod，并使用真实 SQLite/重启；`e2e/m02.spec.ts` 验证 UI 草稿、私有接口边界及 Windows safeStorage。

依赖配置：根 npm 锁文件、backend uv 锁文件；Windows Python 3.12 环境与已构建 Electron 页面。Playwright 直接使用项目 Electron，不需要下载浏览器。

运行/示例：根目录 `npm run test:integration -- --reporter=json --outputFile=artifacts/test-results/M01/integration.json`；`npm run build` 后 `npm run test:e2e`。测试本身的验证依据是真实协议响应、进程退出及 UI 状态断言。

权限边界：仅启动自有 Electron/Python 进程，不处理真实用户资料。L2 使用合成 Key；L3 运行开发主进程会读取根 `.env.local`，只显示存在性并在内存注入后端，不调用模型；真实 safeStorage 测试只使用合成 Key。生成文件在被忽略的 `artifacts/test-results/M02/`，此前 M01 证据保留。

已知限制：M02 不验收安装包、Agent、文件审批或系统级安全隔离。发布凭据模块使用真实 safeStorage，但完整打包程序的设置流程留 M08；单元失败分支使用 fake safeStorage。真实模型脚本位于 `backend/tests/`，必须显式启用，且与这里的默认测试分开记录。
