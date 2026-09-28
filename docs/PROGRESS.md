# 开发进度与验证证据

## 当前状态（2026-09-28）

本轮仅 M01。实现和本机分级验证已完成；代码提交 `d9bab2a` 成功，两次正常 push 均因 GitHub TLS 连接错误失败，未推送。保留本地提交并停止，M02–M08 未开始，M01 尚未全部完成 Git 收尾。

## 启动预检

- 项目：`D:\Users\18532\Desktop\LXH\Project\Orvia`。
- 已阅读技术设计 v0.7（2026-09-28）。本轮三个独立固定模型映射覆盖旧文档的共用模型约定，详见 ARCHITECTURE。
- 远端：`https://github.com/Kr1sxu/Orvia`，默认分支与本地分支均为 `main`。
- `git ls-remote --symref origin HEAD` 与 `git fetch origin` 确认初始远端为 `8446647`（Initial commit），非空仓库，历史只有 MIT LICENSE。
- 预存工作区：`LICENSE` 已删除但未暂存，`.gitignore` 未跟踪；保留该删除，不纳入提交。无已有 README、AGENTS 或代码，无祖先 AGENTS 约定。
- `.env.local` 三个模型变量均存在且非空，仅检查状态，不输出密钥。未验证供应商可用性；M01 不读取凭据、不调用模型。Tavily 未配置，搜索留在 M07。
- 默认 Python 是 3.11.7；`py -0p` 找到已安装 Python 3.12.6，项目固定使用后者。Node 24.19.0、npm 11.17.0、uv 0.12.19、Windows x64。

## M01 已实现并验证

- [x] √ npm workspaces、Electron/React/TypeScript/Vite、Python 3.12/uv 工程及锁文件。
- [x] √ 真实窗口 → 单一 preload API → 校验来源的 IPC → 固定 Python 子进程 → UTF-8 JSON Lines → 健康响应。
- [x] √ hello 握手、版本校验、请求关联、64 KiB 行上限、中文分片、错误恢复、5 秒请求超时与无自动重放。
- [x] √ Node 隔离、sandbox、CSP、新窗口/导航/权限/网络拒绝，Python 环境变量白名单。
- [x] √ EOF 关闭及自有进程清理；修复退出早于首次请求的启动竞态。
- [x] √ 中文注释、根文档、桌面/后端/跨进程测试模块 README。
- [x] √ Git commit 成功（代码提交 `d9bab2a`）。
- [ ] Git push 成功。
- [ ] M01 全部收尾完成并停止。

## 实际验证记录

结果目录统一为 `artifacts/test-results/M01/`，已 Git 忽略。测试未调用真实模型、无费用、不处理真实用户资料。开发运行输出 `apps/desktop/dist/` 为可重复启动的构建目录，亦不入 Git。

| 级别 | 实际命令 | 结果与证据 | mock / 真实模型 | 未覆盖风险 |
|---|---|---|---|---|
| L0 | `npm run build`（内含 `npm run check`、两套 tsc 与 Vite 构建） | 最终通过，`build.log` | 无 / 否 | 未构建安装包 |
| L0 | `npm audit --json`（重定向至结果目录） | 修复后 0 项已知漏洞，`npm-audit.json` | 无 / 否 | 审计数据库不能证明没有未知漏洞 |
| L1 | `.\backend\.venv\Scripts\python.exe -m pytest backend\tests --junitxml=artifacts/test-results/M01/backend-junit.xml` | 16/16 通过；协议状态、有界读取、无换行 EOF、非法 UTF-8/JSON | 内存流，无协议/模型 mock / 否 | 不替代操作系统管道测试 |
| L1 | `npm run test:unit -- --reporter=json --outputFile=artifacts/test-results/M01/desktop-unit.json` | 当时 9/9；协议/权限 4 项仍有效，生命周期后来增加 1 项，见下一行 | 生命周期模拟子进程，其余无 mock / 否 | 拒绝路径的真实恶意渲染页面未穷举 |
| L1 | `npx vitest run apps/desktop/tests/backend.test.ts --reporter=json --outputFile=artifacts/test-results/M01/lifecycle.json` | 最终 6/6；不兼容握手、超时、异常关闭、不重放、EOF/终止、先退出后请求不 spawn | 模拟进程/管道/时间 / 否 | kill 失败且没有 close 的极端 OS 状态未验证 |
| L2 | `npm run test:integration -- --reporter=json --outputFile=artifacts/test-results/M01/integration.json` | 最终 3/3；真实 Python、并发关联、中文分片/合并、错误恢复、缺失解释器、EOF 与 PID 退出核验 | 无 / 否 | Windows 当前开发环境，未覆盖其他系统 |
| L3 | `npm run test:e2e` | 最终 1/1；真实 Electron 窗口+真实 Python、两次健康检查、隔离属性、退出 PID 核验；`e2e.json`、`e2e.log`、`health-window.png`，截图已视觉检查 | 无 / 否 | 无干净机器安装验收；不包含后续 Agent/文件任务 |

最终有效目标用例共 30 项：Python 16、桌面协议/权限 4、桌面生命周期 6、跨进程 3、E2E 1。不是 L4 全量回归，未测试未实现模块。

### 失败、修复与重跑依据

1. 依赖安装尚未完成时，首次 `npm run build` 与 `npm run test:integration -- --reporter=json --outputFile=artifacts/test-results/M01/integration.json` 分别因 `tsc` / `vitest` 未就绪而 exit 1，无测试执行。安装完成后相关命令通过。
2. 初始 npm audit 返回 3 项已知问题（moderate/high/critical 各 1），报告 `npm-audit-initial.json`。将 Vite 6.4.1 → 6.4.3、Vitest 3.2.4 → 4.1.11，更新锁文件后审计 0。因依赖变化重跑受影响的 TS 构建和测试；未重跑无关 Python 单测。
3. 代码审查发现 stop 先于首次 health 时仍可 spawn；修复 start 前关闭状态检查，新增用例后仅重跑生命周期 L1、客户端 L2、构建及对应 L3，复用其他结论。
4. 第一次 `npm run test:e2e` 的真实健康响应已经通过，但退出核验取用了 Playwright 启动器 PID，查不到 Python 导致失败，保留 `e2e-initial.log`。改为从 Electron 主进程读取 PID 后，仅重跑该 E2E，1/1 通过。
5. Electron 44 npm 包不自动下载运行时，增加 `npm run setup:electron`，已实际执行成功。npm 对 esbuild 安装脚本的提示未阻塞构建；未调整全局 npm 策略。

## 限制与下一轮

仅提供 Windows 源码开发启动，无安装包、托盘、自动重连、持久化日志、Agent、数据库、凭据存储、模型适配、文件操作或浏览器工具。stderr 持续消费但不保存原文。安全策略不是 OS 沙箱。
健康检查仅证明本地通信正常；三模型真实可用性与能力需要在后续配置模块用合成数据验证。未承诺真实模型支持情况。
本轮完成提交/推送后停止；只有用户明确要求，才开始 M02。

## Git 收尾

提交前已检查 `git status`、`git diff`、`git diff --cached`、`git diff --cached --check`；清除 5 个文件末尾多余空行后静态检查通过，纯空白修订不重复代码测试。
通过内存比较本地 Key 与 38 个暂存文件及本地测试产物，密钥匹配为 0；禁止路径为 0；JSON 配置、Markdown 本地链接及 `.env.example` 空值均通过。报告 `staged-hygiene.json` 仅含计数，无密钥或摘要。
测试报告、运行数据、虚拟环境、node_modules 与真实 Key 均未暂存；`git check-ignore` 已确认保护生效。预存 LICENSE 删除未纳入本轮提交。
- 首次提交尝试：因 `Author identity unknown` / `unable to auto-detect email address` 失败，未产生 commit；随后用户确认身份。
- 提交成功：`git -c user.name='踪显' -c user.email='18532112451@163.com' commit -m "feat(M01): establish restricted Electron Python health bridge"`，生成 `d9bab2a`，38 个模块文件。作者身份已核对。
- 推送失败：连续两次 `git push origin main` 均 exit 1，错误为 `OpenSSL SSL_connect: SSL_ERROR_SYSCALL in connection to github.com:443`。未报告远端更新成功，保留本地提交，不 force push、不重写历史、不关闭 TLS 校验。
- 身份阻塞已解除：用户明确确认沿用“踪显 <18532112451@163.com>”。仅为本次 Git 命令指定该身份，不修改全局配置。
- 模块代码已提交，另将本次失败回执作为独立文档提交保留；这些本地提交尚未推送。工作区预存 LICENSE 删除仍未暂存。网络恢复后只需继续正常 push 和更新回执，不开始 M02。
- 本次仅 Git 与文档收尾，复用上述 L0–L3 结论，不重复运行代码测试。
