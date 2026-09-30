# M18 任意脚本、桌面点击、浏览器写操作：确认设计

日期：2026-09-30。用户要求仅本轮M18，三项全部实现、验证、记录并正常本地提交才完成，不开始M19–M20。预检候选设计之后，用户集中确认五项范围，并明确“全部允许”指普通权限应用及准确站点/动作由每任务原生授权，仍逐步审批和实际外发另批。实际结果及未覆盖风险以PROGRESS为准，设计本身不授予任何运行权限。

## 预检事实

- 项目 `D:\Users\18532\Desktop\LXH\Project\Orvia`，分支main；`git fetch origin`、`git ls-remote --symref origin HEAD refs/heads/main`成功。默认main，本地/远端同为 `19b1f8a7d4db03927d3eb60949c1de53be7b0727`，ahead/behind=0/0，用户已同步上一轮两个提交。
- 预检只见未跟踪`.zcodeignore`；保留不提交。LICENSE当前已跟踪且干净，只记录，不恢复/修改/暂存。AGENTS、根README、架构、两份清单、进度及涉及模块README已阅读。
- 本机Windows构建26200/25H2、CoreCountrySpecific，WindowsSandbox.exe不存在。原技术设计的Windows Sandbox不能当本机已有前提；实际采用原生LPAC＋Job。
- M14生产签名/独立Windows验收继续暂缓，旧安装包不含M15–M18。M20后重建并核对安装版与开发版待办保留。

## 用户已确认范围

| 能力 | 本轮确认 |
|---|---|
| 脚本语言/来源 | Python3.12：粘贴完整源码、原生单选.py、另行审查固定Computer草稿；固定现有Python的私有副本，不自动安装依赖 |
| 脚本权限 | LPAC＋Job，显式输入只读复制，任务隔离区写，产物逐文件另批回传；无网络/提权，隔离无法核验就停止 |
| 桌面 | 每任务原生明确选择普通权限应用及具体动作；UIA唯一控件，不盲坐标，操作后实际读回 |
| Browser | 每任务原生准确HTTPS站点及具体类别：填表、消息、上传、删除、交易；专用可见窗口手工登录，Cookie仅内存，不复用个人profile |
| 审批/恢复 | 每步原生批准，实际外发另批；取消阻止后续动作/回收自有资源，已发出的动作核验，未知不重试，无通用撤销承诺；最小hash/核验审计，不默认截图/原始网络或网页持久化 |

“允许任意应用/站点逐任务授权”不表示全部第三方程序都具有可操作UIA控件，或所有站点适用受控网络策略。终端/IDE/安全输入/提权/系统界面拒绝；个人浏览器网页统一走专用Browser入口以保留实际请求审批。未经批准的页面、代码、文档、模型均不能扩大权限。

## 实施结构和复用

Application→ChatService.automation→固定Pydantic契约，main的m18-ipc/Zod保留实际预览身份，preload只提供固定21业务方法。renderer继续sandbox/contextIsolation/noNode/无联网或通用IPC。Computer gateway/PathPolicy处理显式输入与新文件回传；Store/ChatRepository处理SQLite和请求去重；M07只读URL/DNS/IP/TLS规则复用但写网关与只读证据分开。M17文件批准不构成脚本执行批准，M17结果可由用户显式选择为脚本输入。

共同operation绑定会话、kind、目标、源码/参数/输入hash、前置状态、300秒revision。先条件更新账本再派发，重复审批拒绝。running/awaiting_request/awaiting_verification/cancel_requested重启为interrupted，权限不恢复，未知动作不重放。取消/状态/待请求旁路长任务，不持会话或SQLite锁等待未来审批；整机桌面后台动作串行。

| 位置 | 责任 |
|---|---|
| automation/contracts.py/service.py/repository.py | 严格固定接口、计划、归属/版本再检、一次性状态、最小审计/核验/取消 |
| automation/scripts.py/windows_isolation.py | 三来源、显式输入复制、私有runtime、LPAC/Job真实执行、产物与新建回传 |
| automation/desktop.py/desktop_worker.ps1 | 固定MTA工作器、exe/PID创建时间/HWND/会话绑定、UIA前置条件/焦点和读回、新文件staging副本 |
| automation/browser.py/browser/write_network.py | 专用内存登录、准确origin、全部受控网络、每个实际请求独立审批、新DOM期待条件 |
| Application/ChatService/server | 装配/生命周期、固定私有stdio与控制旁路 |
| main/m18-contracts.ts/m18-ipc.ts/backend.ts/preload.ts/shared/api.ts | 主进程原生目标/路径/发送/步骤审批、严格IPC与固定返回 |
| renderer/M18Cards.tsx/main.tsx | 三项完整预览、状态/账本、取消、产物/外发与完整性提示；无M19视觉升级/M20意图路由 |
| packaging/orvia-backend.spec | 固定UIA工作器程序资源；本轮不重建旧M14安装包 |
| 既定tests目录 / 中文README/架构/清单/进度 | 分级证据，产物仅忽略的artifacts/test-results/M18 |

三个角色继续固定Main deepseek-flash/api.deepseek.com、Computer glm-5.3-flashx/open.bigmodel.cn/api/paas/v4、Browser mimo-v2.6-flash/api.xiaomimimo.com/v1。默认零模型；可选脚本提案仅发送≤1000字用户需求到固定Computer，一次/4096输出token/30秒/零重试，另行原生费用确认。测试不读取密钥、不调用真实模型或真实账号。

## 实际技术边界

Python私有exe/DLL/pyd固定RT_MANIFEST变换避免零cap LPAC的SxS初始化拒绝，原安装不改；私有副本原签名失效、变换后的完整hash核验。SHGetKnownFolderPath获取必要LocalAppData，不拓宽后端环境白名单。新进程先挂起、加入Job并核验LPAC访问语义、SID、零cap、非提升/Low integrity/UIAccess=0、Win32k禁止及Job全部UI限制，再恢复。30秒/512MiB/4进程上限，stdout+stderr16KiB；输入8项/各2MiB/总16MiB，输出12项/各2MiB/总16MiB。产物采样监测不是OS磁盘配额；系统基础只读资源和AppContainer私有系统存储仍可能可访问。socket/ctypes/GUI/subprocess受隔离限制，不能把上限当功能承诺。冻结后端不是Python，当前明确不支持脚本运行，M20安装资源需另核验。

桌面普通应用不是OS沙箱，可能自行保存/联网。每步UIA前核对身份、唯一性、树摘要与前景/焦点；密码样式/子树拒读，超16KiB/160项观察停止。外发类别另有原生业务确认，但不能由桌面逐HTTP拦截；桌面网页操作转专用Browser。新副本从私有staging独占复制至原生选定路径，不覆盖，应用当前文件仍指staging。只验证真实控件效果，交易等业务真值人工核对。

Browser禁止continue直连、Worker/子框架/WebSocket/下载/私网和未授权origin；动态GET及后续导航、非GET（含HEAD/OPTIONS）/autosave一律暂停独立审批。初始URL为声明GET写端点时先返回尚未加载的会话，再独立批准该请求，不死锁；HTTP重定向拒绝直接跟随，须用户明确授权最终HTTPS页，已发送写请求的3xx回执为uncertain。初始资源GET的服务器副作用无法普遍证明。URL/method/字段/文件/hash/遮盖/截断的新版本180秒有效；超预览预算或敏感遮盖不冒充全量。最多4会话/每任务8origin、单上传2MiB/1文件、请求3MiB、排队4项/总4MiB、每会话200请求/8MB响应、各响应512kB，网页控件最多80/观察24KiB/待请求48KiB。2xx仅回执，需指定此前不存在的新文字出现在真实DOM才核验通过；仍不是服务器业务真值。发送中取消/断线uncertain，无自动重放。

## 分级验证与停止点

可见Chromium使用SDK固定来源的原字节私有副本：根chrome.exe，其余manifest/DLL/资源放同一版本目录；不修改原SDK、系统SxS或PE字节。完整hash、独立文件、恶意XML和有界目录检查；只给公开程序副本的AppContainer/LPAC组只读执行，保持profile/任务私有和后端四项环境白名单。显式启用Chromium sandbox，真实合成页读回renderer非提升/Untrusted和关闭后的自有进程回收；启动/context/page分别10/8/8秒有界，初始化失败关闭自有实例，不自动降策略。

L0：Python/PS语法、TS严格检查/构建、协议字节预算、文档/diff。L1：strict字段、未批准/过期/跨会话/重复、预算、路径/目标、秘密/完整性、取消。L2：真实SQLite和固定角色mock、真实LPAC/Job负例、真实UIA自有fixture、真实Chromium合成DNS/HTTP。L3：Electron→原生main→Python三项串联及取消/审批绕过，系统原生框mock单独标明。L4：新增OS执行权限导致共享生命周期变化，定向回归M04/M07/M10/M11/M12/M17/协议/退出；无独立机器或生产签名冒充。

测试只合成数据；真实引擎/OS执行与HTTP/模型/原生框替身分别记录。默认不持久化产品截图/网页/请求，测试产物不入Git。三项全部实际实现并验证后才勾选，显式暂存/敏感与cached diff检查，用固定作者正常本地commit。Agent不push/改TLS/重写历史/Release；汇报待手动push后停止，不开始M19。

## 技术依据

- [微软LPAC启动](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer)、[Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)。OS权限和资源生命周期分别核验，cwd/Job不能冒充文件或网络沙箱。
- [UIA线程](https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-threading)、[Invoke](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationinvokepattern-invoke)、[RuntimeId](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationelement-getruntimeid)。身份复核与读回由程序控制，RuntimeId不当持久授权。
- [Playwright网络](https://playwright.dev/python/docs/network)、[BrowserContext](https://playwright.dev/python/docs/api/class-browsercontext)。实际路由审批及专用会话不代替用户业务授权。
- [微软私有程序集](https://learn.microsoft.com/en-us/windows/win32/sbscs/about-private-assemblies-)、[Chromium沙箱设计](https://chromium.googlesource.com/chromium/src/+/main/docs/design/sandbox.md)。私有版本布局和公开程序的受限组只读ACL依此设计；本机崩溃原因以实际对照修复结果推断，不声称已获得完整崩溃堆栈。
