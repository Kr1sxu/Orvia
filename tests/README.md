# 跨进程与端到端测试

M20：默认合成模型与网络的完整自然流程在 `e2e/m20.spec.ts`、`m20-business.spec.ts`，真实 stdio 与落盘在 `backend/tests/test_m20_transport.py`，事件队列／契约／增量在桌面与后端既定测试目录。原生框替身只作合成选择和批准，不替换业务权限检查。`m20-installed.spec.ts` 用同一真实后端流程对照开发／冻结安装模式；`m20-runtime-parity.spec.ts` 实际验证私有LPAC、UIA工作器和完整可见Chromium，不能用mock启动器冒充安装能力。所有合成profile、数据、截图、日志和构建资源仅放忽略的 `artifacts/test-results/M20/`。

`m20-publication-parity.spec.ts`以`ORVIA_M20_PUBLICATION_MODE=development|installed`单独比较三格式：只读备份此前合法且已核验的合成mock回答及真实DOCX证据到新profile，不复制Vault或目录授权；实际产品后端通过三个自然请求各自预览/批准准确新保存路径，真M16生成和独立重开/引用/hash核验，PDF全部页渲染。回答origin始终标为mock，云调用0；审计用开发Python只读取已生成文件，不能作为安装产品解释器回退。真实原生选择/取消和Windows组合输入另在`m20-native.spec.ts`/`m20-ime.spec.ts`限定唯一自有PID/HWND测试，不推断其他应用或输入法。

`m20-live.spec.ts` 默认跳过，只有显式 `ORVIA_M20_LIVE=1` 与development/installed模式才调用固定Main。本轮最新已说明开发1次1024（已失败消费）与安装剩余独立1次4096（恢复M15原有上限），全轮最多2次/5120输出token、网络20秒／生成30秒、零重试；真实次数账本失败也消费，不自动重置。普通意图/回答仍1024；不为测试预算削减M15正常能力。Key仅由开发主进程或安装系统安全存储读取，报告只有计数／时间／用量／引用结构，不能打印原请求或凭据；失败也在finally保存观察到的计数/时间，不反造首次丢失记录。详细实际命令、mock／真实范围、失败修复及未覆盖风险见 [PROGRESS](../docs/PROGRESS.md) 和 [M20矩阵](../docs/M20_TEST_MATRIX.md)。各Electron启动器通过CLI设置独立profile，避免在主进程后续设置数据路径之前争用单实例锁。

M18历史：`e2e/m18.spec.ts`真实Electron→main→Python/SQLite并实际运行LPAC脚本、UIA合成应用、Chromium合成页面；原生确认/Computer模型/DNS/HTTP仅由测试启动器mock。`m18_desktop_fixture.ps1`只构建自有WinForms/标准Win32控件，所有源码副本/exe/私有运行时/日志/截图留`artifacts/test-results/M18/`。后端`test_m18_isolation.py`、`test_m18_desktop.py`、`test_m18_browser_engine.py`分别显式启用真实本机适配器，不能当真实网站或所有应用验收。测试不读取开发密钥/真实账号，不输出网络正文。精确命令、失效项修复、证据和L4定向回归见PROGRESS；当时M20安装版核对尚未开始，本轮已授权实施。M14生产签名和独立机器验收继续暂缓。

M13：`integration/m13-fixtures.ts`只生成无敏感DOCX/PNG；`integration/m13.test.ts`验证真实Python/stdio附件、索引、引用、导出与重启。`e2e/m13.spec.ts`通过测试专用启动器模拟原生选择器，真实运行Electron、后端、SQLite、解析和本地OCR，凭据来源替换为空，不读取开发Key，不调用云模型/Tavily。报告环境为`ORVIA_TEST_MODULE=M13`与`ORVIA_TEST_RESULTS=artifacts/test-results/M13`；精确命令及定向重跑见PROGRESS。该测试不代表系统原生对话框视觉或发布包已验收。

用途：验证桌面与真实 Python 的通信及实际用户窗口流程。

目录：`integration/` 使用 Vitest 启动 Python；`e2e/` 使用 Playwright 启动 Electron；桌面单元测试另在 `apps/desktop/tests/`，后端单元测试在 `backend/tests/`。

输入输出：合成健康检查请求、非法帧、草稿和合成凭据；输出断言、JSON/JUnit 报告及窗口截图。`integration/m02.test.ts` 对照 Pydantic JSON Schema 与 Zod，并使用真实 SQLite/重启；`e2e/m02.spec.ts` 验证 UI 草稿、私有接口边界及 Windows safeStorage。

依赖配置：根 npm 锁文件、backend uv 锁文件；Windows Python 3.12 环境与已构建 Electron 页面。Playwright 直接使用项目 Electron，不需要下载浏览器。

运行/示例：根目录 `npm run test:integration -- --reporter=json --outputFile=artifacts/test-results/M01/integration.json`；`npm run build` 后 `npm run test:e2e`。测试本身的验证依据是真实协议响应、进程退出及 UI 状态断言。

权限边界：仅启动自有 Electron/Python 进程，不处理真实用户资料。L2 使用合成 Key；L3 运行开发主进程会读取根 `.env.local`，只显示存在性并在内存注入后端，不调用模型；真实 safeStorage 测试只使用合成 Key。生成文件在被忽略的 `artifacts/test-results/M02/`，此前 M01 证据保留。

已知限制：M02 不验收安装包、Agent、文件审批或系统级安全隔离。发布凭据模块使用真实 safeStorage，但完整打包程序的设置流程留 M08；单元失败分支使用 fake safeStorage。真实模型脚本位于 `backend/tests/`，必须显式启用，且与这里的默认测试分开记录。

## M14历史本机打包验证

历史未签名候选版0.2.0-rc.1只含M10–M13；当时“安装包未重建”状态保留为历史，不能据此判断M20。本轮完整包、升级／卸载及对照命令见packaging/README.md、docs/PROGRESS.md，产物统一M20。M14历史证据仍在M14；真实本地组件不等于供应商或Tavily，生产签名和独立Windows继续暂缓。

M20最终前端竞态：m20.spec.ts中延迟create与paused拉取门闩、历史慢流三目标；m20-stream.test.ts验证paused直接接续、真正终态不可复活。`node tests/integration/m20-candidate-parity.cjs`只读比较普通/测试ASAR的22份dist与当前build；安装离线/runtime/publication/live实际证据及预算见PROGRESS，真实模型2次已耗尽，不默认重跑。
