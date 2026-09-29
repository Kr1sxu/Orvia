# 跨进程与端到端测试

M13：`integration/m13-fixtures.ts`只生成无敏感DOCX/PNG；`integration/m13.test.ts`验证真实Python/stdio附件、索引、引用、导出与重启。`e2e/m13.spec.ts`通过测试专用启动器模拟原生选择器，真实运行Electron、后端、SQLite、解析和本地OCR，凭据来源替换为空，不读取开发Key，不调用云模型/Tavily。报告环境为`ORVIA_TEST_MODULE=M13`与`ORVIA_TEST_RESULTS=artifacts/test-results/M13`；精确命令及定向重跑见PROGRESS。该测试不代表系统原生对话框视觉或发布包已验收。

用途：验证桌面与真实 Python 的通信及实际用户窗口流程。

目录：`integration/` 使用 Vitest 启动 Python；`e2e/` 使用 Playwright 启动 Electron；桌面单元测试另在 `apps/desktop/tests/`，后端单元测试在 `backend/tests/`。

输入输出：合成健康检查请求、非法帧、草稿和合成凭据；输出断言、JSON/JUnit 报告及窗口截图。`integration/m02.test.ts` 对照 Pydantic JSON Schema 与 Zod，并使用真实 SQLite/重启；`e2e/m02.spec.ts` 验证 UI 草稿、私有接口边界及 Windows safeStorage。

依赖配置：根 npm 锁文件、backend uv 锁文件；Windows Python 3.12 环境与已构建 Electron 页面。Playwright 直接使用项目 Electron，不需要下载浏览器。

运行/示例：根目录 `npm run test:integration -- --reporter=json --outputFile=artifacts/test-results/M01/integration.json`；`npm run build` 后 `npm run test:e2e`。测试本身的验证依据是真实协议响应、进程退出及 UI 状态断言。

权限边界：仅启动自有 Electron/Python 进程，不处理真实用户资料。L2 使用合成 Key；L3 运行开发主进程会读取根 `.env.local`，只显示存在性并在内存注入后端，不调用模型；真实 safeStorage 测试只使用合成 Key。生成文件在被忽略的 `artifacts/test-results/M02/`，此前 M01 证据保留。

已知限制：M02 不验收安装包、Agent、文件审批或系统级安全隔离。发布凭据模块使用真实 safeStorage，但完整打包程序的设置流程留 M08；单元失败分支使用 fake safeStorage。真实模型脚本位于 `backend/tests/`，必须显式启用，且与这里的默认测试分开记录。

## M14 本机打包验证

最新未签名候选版为0.2.0-rc.1，包含对话及文档能力；上文“安装包未重建”描述保留为历史模块状态。PDF/OCR冻结资源、安装包流程、升级/卸载的命令与边界见根目录 packaging/README.md、docs/PROGRESS.md。测试产物统一为 artifacts/test-results/M14/。真实本地组件测试不等于云模型/Tavily验证；生产签名和独立Windows验收经用户确认暂缓。
