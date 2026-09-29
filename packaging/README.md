# M14 未签名测试候选版：0.2.0-rc.1

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
