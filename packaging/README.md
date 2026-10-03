# Windows 未签名候选包与安装验收

## M20完整包：0.3.0-rc.1（本机完整验收通过）

M20重建包含M15–M20的冻结后端、离线OCR/PDFium/ONNX、M16文档库与中文字体、M19三字体与折帆、M18私有Python3.12.6标准库、可信UIA工作器，以及锁定Playwright的完整可见Chromium和headless资源。冻结服务与脚本解释器分别核验；安装版只从resources复制经manifest与SHA256复核的私有解释器，不搜索系统PATH、不使用个人浏览器、不把PyInstaller服务当脚本解释器。已有私有运行时篡改、资源身份或隔离不符时拒绝执行，不静默修复。

普通候选身份`cn.orvia.desktop`输出`artifacts/test-results/M20/production-release/`；隔离安装验收身份`cn.orvia.m20.fulltest`／`Orvia M20 Full Test`输出`artifacts/test-results/M20/release/`。二者使用相同业务源码和冻结资源，测试包只增加可信独立安装／窗口身份。普通候选包不安装到用户现有Orvia；旧M14/M19包保留。此处说明实现与操作入口，实际功能、资源、安装和对照结果见[PROGRESS](../docs/PROGRESS.md)，未验收项不提前记为完成。

在功能验收和统一桌面构建后，使用已锁定依赖顺序运行，不并发builder：

```powershell
.venv/Scripts/uv.exe sync --project backend --locked --group packaging
npm run build
backend/.venv/Scripts/python.exe -X utf8 packaging/build_backend.py
npx electron-builder --config packaging/m20-baseline.config.cjs --win nsis --x64 --publish never
npx electron-builder --config packaging/m20-full.config.cjs --win nsis --x64 --publish never
npx electron-builder --config electron-builder.config.cjs --win nsis --x64 --publish never
```

后端准备输出`M20/build/`，资源清单分列Python运行依赖、React／Electron原始许可、完整Chromium的原始credits、FFmpeg LGPL原件、PyInstaller bootloader例外和锁定NSIS原始许可。所有许可随包保存原字节，根LICENSE仅从Git历史生成安装资源，不恢复工作区文件。脚本不读开发凭据、不调用模型、不下载OCR或浏览器资源；缺锁定缓存明确失败。基线只读提取旧M14ASAR，重新封装独立测试身份的0.2.0-rc.1，不能称包含新功能。

实际安装链使用`tests/integration/m20-install.ps1`的`Preflight → InstallBaseline → Upgrade → Uninstall`；中间以`ORVIA_M20_UPGRADE_STAGE=seed|verify`运行`tests/integration/m20-upgrade.test.ts`。这是同一测试身份0.2→0.3真实版本升级，合成profile、注册身份、安装EXE／卸载器／快捷方式和原字节hash都须匹配；脚本仅处理固定`M20/install-smoke/`、当前用户唯一测试注册身份和自有快捷方式，拒绝重解析点，不删除配置。`VerifyPending`只核对已有现场，不重复安装。普通Orvia注册、安装、配置不参与。

开发／安装对照测试分别用`ORVIA_M20_OFFLINE_MODE=development|installed`运行`m20-installed.spec.ts`、`ORVIA_M20_PARITY_MODE=development|installed`运行`m20-runtime-parity.spec.ts`。它们使用真实产品后端，安装模式从实际安装EXE启动并清空个人PATH与开发凭据；开发模式只将凭据Vault置空，不替换工具／资源。单独的`m20-business.spec.ts`模型／网络mock与真实Supplier验证不能混为一谈。`m20_package_audit.py`核对完整资源、ASAR、字体／图标／许可、版本与凭据泄漏，只输出计数和hash；准确参数与执行记录见进度。

真实供应商验证显式`ORVIA_M20_LIVE=1`且`ORVIA_M20_LIVE_MODE=development|installed`才运行`m20-live.spec.ts`；全轮两次Main预算、各链一次，失败亦记账，不自动重试。安装版仅在独立合成profile以safeStorage保存Main，测试产物不含Key。日常测试仍为合成数据与mock。生产签名、独立Windows／VM／AVD验收继续暂缓，不发布Release、不自动更新，不称正式发行。

## M14历史候选版：0.2.0-rc.1

## M19定向视觉资源包（验收通过，非完整发行包）

用户已确认原创折帆非文字图标。生产配置改用builder26.15.3的`signExecutable:false`，仅关闭生产签名，保留EXE图标编辑；窗口ICO、NSIS安装/卸载图标显式指定，三字体由Vite打包进ASAR，三原OFL额外分发。实际目录EXE、安装器、安装后EXE、卸载器四份PE各9尺寸图标与源ICO精确匹配，ASAR字体/SVG与包外ICO/OFL实际hash一致，四份PE为NotSigned。Windows实际关联图标和快捷方式已提取核验，快捷方式箭头叠层不要求与源图逐像素全图相等。源与维护见[视觉资源README](../apps/desktop/resources/README.md)。

在已完成`npm run build`且本地M14冻结资源仍可用时，执行`npx electron-builder --config packaging/m19-visual.config.cjs --win --publish never`。独立appId/productName/shortcutName输出`artifacts/test-results/M19/release/`，不覆盖旧M14包。仅复用旧冻结后端/Chromium资源验证UI/字体/图标，不承诺M15–M18安装功能，不能称M20后完整安装包验收。资源审计：`backend/.venv/Scripts/python.exe -X utf8 backend/tests/m19_resource_audit.py`、`node tests/e2e/m19-assets.cjs`。

实际安装与快捷方式脚本为`powershell -NoProfile -File tests/integration/m19-install.ps1 -Stage Install`，只接受全新M19唯一测试标识和结果目录，无已有记录/路径/快捷方式才安装；不覆盖普通Orvia。`VerifyPending`只核验安装器/EXE/hash/注册身份/快捷方式，恢复记录而不重装；`Upgrade`只按既有自有记录更新，保存历史；`Uninstall`核验自有EXE/注册身份/hash后卸载，不删除用户配置。本轮实际安装、记录恢复、两次同标识升级、最后卸载均通过，自有EXE/注册项/快捷方式已移除；日志与历史保留。已有验收记录不能直接当全新Install重复使用。

用户授权可见桌面后，设置`ORVIA_M19_DESKTOP_ALLOWED=1`和`ORVIA_TEST_MODULE=M19`运行`npx playwright test tests/e2e/m19-packaged.spec.ts`已通过；三字体离线加载，实际任务栏唯一新测试按钮裁切并查看为折帆图标。安装器appId、可信包元数据orviaAppId与窗口setAppDetails保持一致，测试标识`cn.orvia.m19.visualtest`与生产`cn.orvia.desktop`分开。旧Orvia分组曾显示Electron图标，源码资源正确并不足以证明任务栏正确；独立测试新分组已验证，旧固定项刷新仍受Windows缓存/既有安装影响。未清系统缓存，也未覆盖旧M14安装。只裁切自有按钮，不保存其他用户任务栏内容。

历史M19交付时保留生产签名、独立Windows及M20后完整资源对照待办；现M20完整包本机对照已完成，前两项仍暂缓。

## M18历史源码与安装资源边界

历史M18交付范围：当轮只交付开发源码与合成验收，不重建安装包。规格已携带固定 UIA PowerShell 工作器，但没有宣称冻结或安装版 M18 验收通过。隔离脚本目前要求开发后端的经校验 CPython3.12 私有副本；PyInstaller 后端不是通用解释器，冻结模式明确拒绝脚本运行，不查 PATH 回退。M20 后重建时仍须准备并核验专用脚本运行时、完整可见 Chromium、工作器及三项流程与开发版一致。M14 旧包不含 M15–M18，生产签名和独立 Windows 验收继续暂缓。

## M16 源码的冻结依赖

M16 在后端增加 python-docx、python-pptx、ReportLab 和内置 OFL 中文字体；`orvia-backend.spec` 明确收集 `publication/assets`，开发环境及 M16 隔离冻结后端分别验证三格式实际生成。冻结输出仅位于 `artifacts/test-results/M16/`，不是新安装器、升级包或已签名发行版。M14 现有 `0.2.0-rc.1` 安装包保持原状，不含 M15/M16；将来重新打包仍需完成安装包专项验收，M14 暂缓的独立 Windows 与生产签名状态不变。依赖许可证与文件限额见 `backend/src/orvia_backend/publication/README.md`。

本轮按用户授权完成本机打包与回归；生产证书签名、独立无开发环境 Windows 验收暂缓，M14 完整发布验收仍未完成。不发布 GitHub Release，不开启自动更新。

## 构建与资源

在仓库根运行：

```powershell
.venv/Scripts/uv.exe sync --project backend --locked --group packaging
npm run package:win
```

输出为 `artifacts/test-results/M14/release/Orvia-0.2.0-rc.1-win-x64-setup.exe` 与 `win-unpacked/Orvia.exe`，均被 Git 忽略。先校验测试记录和 `SHA256SUMS.txt` 再分发测试包。签名状态应为 `NotSigned`，不是正式已签名发行版。构建不发布，不读取开发凭据；electron-builder 可能打印签名步骤名称，这不代表已成功签名，以 `Get-AuthenticodeSignature` 为准。

`build_backend.py` 使用 PyInstaller onedir/console 保留私有 stdio；`orvia-backend.spec` 收集固定代码依赖、PDF 原生库、离线 OCR 权重/字典及 ONNX Runtime DLL。冻结子进程使用现有 `--document-worker` 固定入口，只有附件字节输入，不开放脚本入口。新增依赖版本写入 runtime manifest，不在用户机器下载 OCR 权重或查找系统 Python。

桌面 dist 使用 ASAR；后端、锁定 Chromium 和 runtime manifest 位于 resources。安装白名单不包含仓库根、环境文件、测试数据库或日志。许可证仍仅从 Git 历史读取生成包内资源，不恢复或修改工作区 LICENSE。

## 安装、升级、卸载

安装器为 Windows x64、当前用户安装，不自动提权；默认不创建桌面快捷方式、不自动启动。用户数据使用 Electron userData；升级保留数据，历史会话不恢复文件权限，不自动执行旧审批。不同 Windows 账户的凭据无法保证互通，safeStorage 损坏时明确失败，不回退明文。

测试脚本 `tests/integration/m14-install.ps1` 只操作本轮 `M14/install-smoke`，拒绝任何非本轮 Orvia 安装和重解析路径。`InstallLegacy` 安装已有 M08 测试包，`Upgrade` 安装候选版，`Uninstall` 仅运行验证过的本轮卸载器。`Install` 可在无本轮记录和已有安装时直接安装。脚本不递归删除任何目录；记录与安装不一致时保留现场。`VerifyPending` 仅在已有 pending 记录时核对安装器哈希、安装 EXE 与目录包哈希、固定卸载路径及版本后恢复记录，不重新执行安装器，也不伪造历史退出码。

卸载默认保留用户数据、加密凭据和历史证据，不表示卸载后已删除个人资料。测试只核对隔离合成数据，不读取或清理默认个人 userData。若安装失败、路径不可写或被安全软件隔离，保留错误信息，核对磁盘空间、写权限、安装包校验和；不要关闭安全软件或改 TLS 绕过检查。正式误报申诉、多个真实 Windows 账户及独立机器兼容性未验收。无网络仍能使用本地扫描、文档与导出；云模型和网页任务会报告不可用，不能靠历史记录伪装成功。

## 验证入口

- 源码全量：`pytest backend/tests`、`npx vitest run apps/desktop/tests tests/integration`、`npx playwright test`。先设置 `ORVIA_TEST_RESULTS=artifacts/test-results/M14` 和 `ORVIA_TEST_MODULE=M14`；动态引擎测试显式设置 `ORVIA_BROWSER_TEST=1`。
- 冻结后端：设置 `ORVIA_FROZEN_BACKEND` 为本轮绝对 EXE 路径，再运行 `pytest backend/tests/test_frozen.py backend/tests/test_m14_frozen.py`。
- 安装包用户流程：设置 `ORVIA_PACKAGED_EXE` 为本轮安装后的绝对 EXE 路径，再运行 `npx playwright test tests/e2e/m14.spec.ts`。旧 M08 面板测试不用于新对话界面。
- 升级数据：安装旧包后以 `ORVIA_UPGRADE_STAGE=seed` 运行 `npx vitest run tests/integration/m14-upgrade.test.ts`，升级后以 `verify` 再运行。两阶段共用本轮合成 profile。
- 内容与密钥审查：`backend/.venv/Scripts/python.exe -X utf8 backend/tests/m14_package_audit.py`。只输出计数与安装器 SHA256，不输出密钥值；读取开发凭据仅用于内存匹配审查，不调用服务。

精确命令、通过/失败/跳过和已知限制以 `docs/PROGRESS.md` 为准。真实本地 Electron、safeStorage、SQLite、FTS、Chromium 和 OCR 与云端服务区分：选择器/模型/外网响应按测试 mock，真实云模型、Tavily 调用为零。本机清空 PATH 不等于独立机器验收。冻结后端审批与源码对话审批分别验证，安装版不默认调用真实 Main 模型。


2026-10-03最终包：普通候选521447957B，SHA256 `ff419e90e6623aa2e1915cf1699d8ce14df6d7de8dc8058bc6711382ae6d090e`；FullTest521447927B，SHA256 `dad5b9278af02c26df879fcda3e510ba8e65858ba4e2270bf6a85b26823cca68`。两包与当前build的22份业务dist、共同runtime-manifest完全一致（`node tests/integration/m20-candidate-parity.cjs`）；实际安装4183份resources/1298858022B逐字节匹配。冻结后端新构建包含M15–M20，SHA256 `d660514b5f72b546b2063259f424520d6ecd91a056845afc17f1419c3162bfd2`，59输入hash稳定。D7中间包归档M20/intermediate-D7，不冒充最后版本。

已实际通过旧0.2→0.3安装升级/历史与引用保留/旧授权失效、安装离线目录/OCR/导出/strictIPC、三格式真实生成、私有Python LPAC/UIA/完整可见Chromium运行时及固定Main真实SSE；具体替身与限制见PROGRESS和M20忽略目录中的development-installed-comparison.md。安装与包资源审计通过，实际安装器/EXE/卸载器NotSigned。卸载与提交终态以PROGRESS为准，不能从构建日志推断。真实调用仅两次：开发1024上限失败，安装独立4096上限成功，总5120输出token预算、20秒网络/30秒生成、零重试；实际安装用量680输入+713输出。生产签名及独立Windows验收继续暂缓。

最终自有卸载exit0，EXE/注册项/快捷方式移除，合成profile及历史SQLite保留测试通过。普通安装身份未运行；发布签名/独立环境仍未完成。
