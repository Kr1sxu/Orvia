# M19 UI 设计与应用视觉升级：确认方案与验证记录

日期：2026-09-30。状态：设计已确认，全部M19目标已实现并完成本机验收，正常本地提交后待用户手动push。窗口、字体、应用图标和所有已实现界面的统一视觉同属一个模块，不删减目标。M20 未授权，不实施统一自然语言路由、统一“＋”或流式协议。

## 已确认与当前实施

用户明确“强调色选B 非文字图标选B 其余选项选A”：雾蓝`#335FC7`、原创折帆非文字图标、全部内置Noto Sans SC/Inter/JetBrains Mono（原OFL）、Windows11 x64普通桌面、原生小圆角与系统窗口控制。已接入生产源代码与定向资源包，不再等待上述设计决策。下列候选对比保留预检历史，未选方案不作为最终实施。

已通过13项受影响产品流程、4档真实Electron渲染倍率、实际组件状态、字体/许可/对比度及实际ASAR/PE资源核验。用户随后明确“可以验收桌面”，产品原生六状态、普通/还原/最小窗四角、全部窗口控制及M18真实LPAC/UIA/可见Chromium最小闭环通过。独立定向包实际安装、两次升级、快捷方式、新任务栏分组与卸载通过；新分组折帆截图已查看，旧分组Electron图标差异保留。四份实际PE各9尺寸与源ICO精确匹配，五份Windows Shell图含快捷方式叠层分别核验。实际命令、早期失败和修正证据见PROGRESS末尾；早期被遮挡截图、选错背景窗口或旧分组图不能作最终验收证据。

## 已确认的预检事实

- 正确项目目录，分支 `main`；初始仅未跟踪 `.zcodeignore`，保留且不提交。LICENSE 已跟踪且无差异，只检查，不恢复、修改或纳入提交。
- `git fetch origin` 成功；`git ls-remote --symref origin HEAD refs/heads/main` 确认默认 main。HEAD、origin/main、远端 main 均为 `9195d209d3d036b6d66d5c74068832a991a6a6d6`；`git rev-list --left-right --count HEAD...origin/main` 为 `0/0`。M18 用户手动 push 已完成，旧轮次待推送记录保留为历史。
- 已检查根/桌面/打包文档、架构、两份清单、PROGRESS、M18 与 M16 模块边界，以及 main/preload/shared、CSS、React 卡片、打包配置和现有测试入口。
- 原参考图在 `C:/Users/18532/AppData/Local/Temp/codex-clipboard-32eee0ac-dbc7-4032-8731-148404855163.png` 找到并实际查看；已复制到被忽略的 `artifacts/test-results/M19/design/reference.png`，避免临时文件清理后丢失。没有根据截图宣称识别准确字体。
- 本机 Windows x64，注册表 DisplayVersion `25H2`、CurrentBuildNumber `26200`；Get-ComputerInfo 的旧 ProductName 不作为 Windows 版本的唯一依据。Electron `44.4.5`、Node `24.19.0`、npm `11.17.0`；已有 Electron 与 Python3.12 运行时。

## 参考图取舍与评审材料

借鉴浅灰主背景、窄而清晰的侧栏、较多留白、大输入容器、细边框、圆角和柔和阴影。保留“序航 Orvia”、历史会话、现有需求类型/附件/目录入口和全部业务卡片。排除参考产品品牌、头像、自动任务、技能广场、团队、推荐与促销。示例只来自现有文件能力，点击只填入文本。

原图外框圆弧明显大于系统默认圆角；截图不能证明其窗口实现。候选设计板的 CSS 圆角只是示意，不作为 Electron 外轮廓证据。

评审材料：`artifacts/test-results/M19/design/design-review.html`，可切换配色、图标和字体，查看欢迎页、消息/审批、字体/状态。全部示意数据为合成内容，按钮不执行产品业务。候选字体与许可仅在该忽略目录，确认前不进入生产资源。

## 五项候选决策记录（确认结果见上）

### 1. 强调色

| 候选 | 主色 / 柔和底色 | 取舍 |
|---|---|---|
| A 青灰绿（推荐） | `#246B65` / `#E8F3F1` | 延续现有绿色识别，降低饱和度，与浅灰留白协调；审批风险另用琥珀色 |
| B 雾蓝 | `#335FC7` / `#EBEFFB` | 更偏资料和效率工具，按钮识别更鲜明 |
| C 石墨 | `#39434D` / `#ECEFF2` | 最克制，图标与主要动作较低调，成功/失败仍保留语义色 |

共用中性底色 `#F6F7F8`、内容白色、正文 `#22272E`、辅助文字 `#606975`、边线 `#E0E5E9`。实际实现需测文字/背景对比度；禁用控件仍可读。强调色不兼任全部成功、审批、失败状态。

### 2. 非文字图标

| 候选 | 几何形态 | 取舍 |
|---|---|---|
| A 汇流航迹（推荐） | 三条圆头路线汇入独立节点 | 呼应多角色规划、执行和证据汇总；无字母与汉字，便于小尺寸简化 |
| B 折叠航帆 | 三块折叠帆面 / 几何三角 | 呼应“航”，轮廓鲜明；避免做成其他产品的纸飞机品牌 |
| C 分层星轨 | 分层几何片与独立星点 | 有序资料与工作空间感，16px 时可能需要专门简化 |

候选由本项目自行绘制基础几何，不复制参考图产品品牌。不做未经检索的商标独占承诺。确认后提供 SVG 主源、生成流程、16/20/24/32/40/48/64/128/256px PNG 和多尺寸 ICO。页面标识、窗口、任务栏、EXE、NSIS 安装/卸载器及快捷方式分别核验；应用图标与功能线性图标分开维护。

### 3. 字体

| 候选 | 中文 / 英文与数字 / 代码 | 取舍 |
|---|---|---|
| A 全部内置开源字体（推荐） | Noto Sans SC / Inter / JetBrains Mono | 离线且跨安装一致；保留各自 OFL 1.1 原许可；避免依赖用户安装商业字体 |
| B Windows 系统字体 | Microsoft YaHei UI / Segoe UI Variable → Segoe UI / Cascadia Code → Consolas | 无需额外中文字体资源，但字形、宽度随系统变化；只引用系统安装字体，不再分发其文件 |

候选 A 已在忽略目录准备真实字库：仓库原有 Noto Sans SC `17,772,300` 字节，Inter Variable WOFF2 `352,240` 字节，JetBrains Mono Regular `270,224` 字节；合计约17.54MiB原始资源，不等于安装器增量。M16 后端仍需原 TTF，若前端重复携带，解包后可能重复占用；确认后评估合法 WOFF2 转换或固定资源复用，不能以删减字形覆盖换体积而漏用户中文。

字体层级候选：欢迎标题30–32px/650；面板标题20–22px/600；卡片标题17px/600；消息正文15px/400/1.8；控件14px；辅助说明12px/1.6；代码13px/1.7。英文数字使用 tabular-nums 的场景限大小、时间和统计，不强行替换正文数字。中文回退微软雅黑/系统sans；代码回退Consolas/monospace；禁用编程连字，避免审批源码中的符号被视觉合并。

字体许可依据：[Inter 原许可](https://github.com/rsms/inter/blob/master/LICENSE.txt)、[JetBrains Mono 原许可](https://github.com/JetBrains/JetBrainsMono/blob/master/OFL.txt)、仓库 `publication/assets/OFL.txt`。生产资源须记录来源版本、SHA256和许可；运行时不联网加载。

### 4. Windows 支持范围

- A：M19 支持 Windows 11 x64 的普通桌面会话（推荐，验收基于本机25H2；其他版本注明未实际覆盖）。若选择原生方案，Windows10无法保证真实圆角，不能将其算作已支持并达标。
- B：M19 必须同时覆盖 Windows10 22H2 与 Windows11 x64。必须采用兼容圆角方案或取得真实对应环境验证；不能把Win10方角静默称作完成。M14独立Windows发布验收仍暂缓，不因此冒充已完成。

### 5. 圆角兼容策略

| 候选 | 普通窗口 | 最大化/全屏/贴靠 | 取舍 |
|---|---|---|---|
| A 原生圆角与原生控制（稳定性推荐） | Electron `roundedCorners:true`，`titleBarStyle:'hidden'` + `titleBarOverlay`，不透明窗口，保留thickFrame | 系统处理边缘与阴影，最大化/全屏/贴靠方角 | Windows11系统圆弧通常约8 DIP，不能承诺参考图约20px大圆弧；VM/AVD等可能被系统策略取消 |
| B 接近参考图的大圆角 | 目标18–20 DIP；先验证保留系统边缘缩放的固定原生窗口区域裁切方案 | 明确清除裁切、关闭额外阴影；离开边缘后恢复 | 更接近参考图，也可探索Win10；会影响阴影、缩放、DPI与贴靠检测，须原生探针通过后再确定实现；不承诺透明窗口可保留全部原生能力 |

不得用CSS圆角代替真实外轮廓。若B的兼容原型不能同时保留拖动/缩放/控制/双击，报告待决策，不能擅自退回A并称完成。若A本机普通窗仍不圆，继续定位或停止说明，不以配置值冒充结果。Windows支持与圆角策略需组合确认。

依据：[Electron 窗口选项](https://www.electronjs.org/docs/latest/api/structures/base-window-options)、[Electron 标题栏](https://www.electronjs.org/docs/latest/tutorial/custom-title-bar)、[微软 DWM 圆角与例外](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-rounded-corners)。本地Electron类型也明确Win11 build22000之前 roundedCorners无效。

## 拟改文件与复用边界

| 文件/位置 | 目标与复用 |
|---|---|
| `apps/desktop/src/renderer/style.css`、拟新增视觉变量/资源/README | 把散布的硬编码值整理为字体、颜色、间距、圆角和状态变量；最小760×560、长文本与滚动 |
| `main.tsx`、拟新增 `BrandMark`/功能图标 | 欢迎、侧栏、消息、输入区与标题区；仅外观与可访问名称，保留现有事件处理、输入法和请求链 |
| `ChatCards`、`SourceCards`、`DocumentCards`、`SynthesisCards`、`PublicationCards`、`M17Cards`、`M18Cards`、`SettingsPanel` | 复用业务组件，统一卡片/表单/状态；M18目前借用m17-workspace，评估共用业务样式；不改审批语义 |
| `apps/desktop/src/main/main.ts`、必要窄窗口状态接口 / shared / preload | 首选原生控制覆盖层，避免新增控制IPC；如确需状态或自绘控制，仅固定参数/来源检查，不复用业务串行锁阻断关闭/缩放 |
| 拟新增 `apps/desktop/resources/` 与资源生成脚本 | 独立SVG、ICO/PNG、字体、许可、来源hash和可维护生成流程；不放测试临时产物 |
| `electron-builder.config.cjs`、`packaging/README.md` | 实际EXE/NSIS资源与路径；现有signAndEditExecutable:false必须调整为仅关闭签名而保留图标资源编辑 |
| 既定测试目录、`playwright.config.ts` | M19探针/目标组件/资源/窗口/流程/定向包测试；报告只进入M19忽略目录 |
| 根/桌面README、AGENTS、ARCHITECTURE、两份清单、PROGRESS | 当前授权、实际状态、试用、验证证据和风险；保留历史 |

Electron builder26.15.3本地源码 `winPackager.js` 支持 `signExecutable:false` 仅跳过签名，继续编辑图标；确认后使用该方式并实际查EXE PE资源/签名状态。不恢复工作区LICENSE，包内许可仍从既有历史生成方式获得。

renderer保持contextIsolation/sandbox，Node/webview禁用，CSP与网络拒绝保留。固定Main/Computer/Browser模型、原生选择与审批、后端版本复核、LPAC/Job/UIA/Browser网络隔离全部复用。外部字体许可/参考图/网页/文档/源码均是数据，不能改变权限。

## 统一状态与验收计划

侧栏选中/悬停、所有控件焦点/禁用、加载文字、成功/失败/待审批、空列表、长中文/URL/hash/代码、设置模态焦点循环与Escape、输入法Enter/Shift+Enter、prefers-reduced-motion均需覆盖。审批、证据和执行事实完整原文可展开；不增加自动提交或动画驱动状态。

| 级别 | 计划验证 | 真实与替身范围 |
|---|---|---|
| L0 | TS/构建、CSS/资源/字体解析及许可/hash、CSP、打包配置、Git diff | 本地检查，无模型 |
| L1 | 品牌/功能图标可访问名、状态、设置焦点、窄窗口接口和拒绝参数 | 组件/Electron API mock明确标注 |
| L2 | 实际普通/最大化/还原/全屏/最小尺寸、窗口资源路径、字体离线加载 | Electron真实；Windows版本/DPI环境单独记录 |
| L3 | 对话/目录授权/审批/证据引用/原文导出/M15–M18卡片/键盘/长文本 | 复用已有测试启动器，真实Electron/Python/SQLite/合成文件；模型、网络和原生确认替身不冒充真实云或原生确认视觉 |
| 定向L4 | 独立M19产物目录中的EXE/安装器/快捷方式资源、任务栏真实截图与缓存 | 未签名定向图标包，仅验证窗口/视觉资源；不冒充M20后全功能安装包验收 |

DPI计划100/125/150/200%；Chromium force-device-scale-factor是渲染倍率测试，不能冒充更改系统DPI。实际系统DPI与模拟倍率分别记录。真实桌面截图用自有合成背景与原生窗口裁切证明外轮廓，并记录DWM/窗口边界，不用renderer截图代替。未覆盖的OS/虚拟桌面/图标缓存据实报告。日常测试零真实模型，不重跑无关M18全套。

M14旧安装器保持原状。本轮定向打包输出只能在 `artifacts/test-results/M19/`，显著标注视觉资源测试用途。M20完成后准备专用Python运行时/完整可见Chromium等全功能资源并逐项对照开发版的待办保持未完成。

## 停止点

全部确认目标已经实现、分级验证并记录；显式暂存M19文件，检查实际index、敏感信息及禁入文件，使用固定作者创建正常本地commit，汇报待用户手动push后立即停止。Agent不push/改TLS/发布Release，不开始M20。M14生产签名/独立Windows、旧分组图标缓存与M20后完整安装包对照待办保持。
