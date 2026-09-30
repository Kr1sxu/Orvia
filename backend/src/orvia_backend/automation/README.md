# M18 可控执行模块

三项能力共用会话和审批账本，分别授权：Python任意源码的隔离执行、普通应用UIA桌面动作、准确站点的浏览器写操作。用户已于2026-09-30确认来源、LPAC隔离、逐任务应用/站点及每步/外发独立审批。来源中的指令没有权限；M17文件批准不能执行脚本，M12网页读取不能提交表单。

## 结构与公共接口

| 文件 | 用途 |
|---|---|
| contracts.py / service.py | 固定Application私有协议、会话/版本复核、逐步计划、取消和完成判断 |
| repository.py | SQLite m18_operations条件状态更新，最小审计、重启中断、不重放 |
| scripts.py | 粘贴/.py/模型草稿的完整预览、显式输入复制、产物核验及逐文件新建回传 |
| windows_isolation.py | 固定CPython私有复制、manifest变换、LPAC/Job/句柄/环境/预算和整树回收 |
| desktop.py / desktop_worker.ps1 | 普通权限窗口绑定、独立MTA UIA工作器、单步读回、受限保存副本 |
| browser.py / ../browser/write_network.py | 专用Chromium、准确origin、实际请求暂停/审批/出口、DOM结果条件 |
| browser_runtime.py | SDK配套Chromium原字节私有版本目录、完整hash、链接/预算检查及沙箱只读执行ACL |

`chat.automation.*`只接受各Pydantic strict业务字段，主进程对应Zod及固定preload。用户界面不能选择方法名、解释器、Shell、任意坐标、请求头、Cookie、审批状态或绝对路径。

| 固定后缀 | 输入 → 输出 |
|---|---|
| script.preview/file | 会话、完整源码或main单选.py、输入相对路径 → operation_id/revision/完整plan |
| script.model_preview/model_generate | ≤1000字需求、预览版本及请求UUID → 固定Computer发送范围或待审脚本plan |
| script.execute/status | 会话/步骤/版本 → 立即返回事实身份；后续读取真实exit/stdout/stderr/产物 |
| script.export | 步骤版本/产物索引、main原生新文件路径 → 文件名/字节/hash/读回verified |
| desktop.windows/grant/observe | main原生选窗、opaque grant → public控件/状态hash；exe/PID/HWND不传renderer |
| desktop.preview/execute | 唯一控件/action/value/前置hash/副作用/预期目标 → 300秒版本计划，独立原生确认后单次派发 |
| browser.open/origin | main原生确认准确HTTPS站点与动作类别 → 新内存会话或追加准确origin |
| browser.observe/preview/execute | 公共控件与hash、动作/值/类别/新文字条件 → 单步审批及异步状态 |
| browser.pending/request | 当前真实暂停请求及新版本 → 原生独立批准/拒绝一次外发，不复用点击批准 |
| browser.close/cancel/history | 准确会话或步骤版本 → 自有资源收尾、事实查询；没有重放恢复接口 |

M18消息kind为automation，不能成为Main文件规划的text指令历史。完整源码/输出/页面/实际网络正文仅在任务副本或内存，不写会话正文或最小SQLite审计。测试报告/截图不属于产品默认持久化策略。

## 脚本运行与权限

依赖现有固定`backend/.venv/Scripts/python.exe`的CPython3.12基础安装，不查PATH、不联网下载、不安装依赖。首次运行复制exe/DLL/标准库至应用数据`automation/runtime/python312`，排除site-packages、GUI/测试/安装工具，`python312._pth`锁定私有搜索路径。每次核对完整hash清单，已有副本变化就拒绝，不覆盖修复。

本机CPython的exe/DLL/pyd嵌入manifest触发LPAC SxS初始化拒绝。因此仅私有副本禁用固定RT_MANIFEST并记录`manifestless-console`变换，原安装不改。私有副本原数字签名失效，不能冒充原签名二进制；它由固定来源与变换后的完整hash核验。冻结后端不是通用Python：当前冻结模式明确不可用，不静默选系统解释器；M20安装版重建时需另行准备并核验脚本运行时资源。

每任务新LPAC SID、零capability、Low integrity、UIAccess=0。新进程挂起后加入Job，核验AppContainerSID、零cap、LPAC访问语义、非提升、Win32k禁止和全部UI限制后才恢复。AppContainer不做网络或loopback豁免；不继承密钥、用户环境或非批准句柄。Job设置KillOnClose、内存/进程预算且读回验证；取消/超时/超限回收整树。

| 预算 | 限额 |
|---|---|
| 完整源码 / 预览 | UTF-8最多32KiB；预览JSON最多48KiB（仍受64KiB协议信封约束） |
| 输入 | 授权目录中显式最多8个普通文件，各2MiB，总16MiB；只读复制，不挂载原根 |
| 运行 | 30秒，Job内存512MiB，最多4进程，标准输出/错误合计16KiB |
| 产物 | 只写output；最多512目录项/12文件，各2MiB，总16MiB，采样停止与退出后有界逐文件验证 |
| 回传 | 一次原生确认一个新文件，拒绝覆盖/链接/ADS/敏感路径，fsync和句柄/字节读回 |

限制是上限而非资源承诺。Windows允许LPAC访问必要基础只读资源及其私有系统存储，不宣称只可访问三个目录。磁盘监测不是OS配额，高速写入可能瞬时超额。网络栈初始化、ctypes/GUI、subprocess等可被隔离拒绝；本机普通Python子进程启动被拒绝，不能宣称已成功运行四个Python进程。任意脚本可提交审查，不承诺全部Python标准库或第三方代码兼容。退出码0只证明这次执行结束，不能证明脚本业务语义正确；输出始终是不可信数据。

## 桌面运行与权限

固定系统Windows PowerShell5.1、`-NoProfile -NonInteractive -Mta -File`启动可信UTF-8 BOM工作器，JSON只选择固定UIA动作，不拼Shell或执行用户代码。绑定当前同用户会话、普通完整性、exe文件身份、PID创建时间、HWND及类；复查防止PID/窗口复用。只观察已选窗口及已识别同进程弹窗；密码属性、Win32 ES_PASSWORD及密码子树屏蔽，不默认截图。观察最多160项/16KiB，超限停止，不悄悄裁掉身份。

支持Value文本输入、Invoke点击、SelectionItem选择、Toggle勾选、Focus聚焦及已识别公共文件保存框的save_new。原生审批抢焦点不算目标内容变化；实际动作前重新定位并确认前景/焦点/唯一性。整机仅一个桌面后台动作在执行，取消只回收自有worker/可核对编译子进程，不关闭用户应用。已派发动作后无法取得读回为uncertain，不自动重复。

普通应用可能自行保存/联网，不是OS沙箱；外发类别除每步批准还有独立原生业务确认，桌面不能像Browser逐HTTP请求拦截。个人Chrome/Edge/Firefox等网页操作通过专用Browser入口；终端、IDE、安全/提权/系统设置、Orvia自身等拒绝。自绘控件/不可读回控件不支持，不回退坐标/SendInput。UI变化证明控件效果，业务结果须人工对照预期目标。

保存新副本先让应用存入随机私有staging，再以PathPolicy独占创建原生选择的新文件，最多10MiB，校验bytes/hash。应用当前文件继续指向staging，不能称已把原文档保存到选定路径，也不承诺通用撤销。保存框异步出现时先重新观察，不重复点保存按钮。

## 浏览器运行与权限

开发环境先执行`backend/.venv/Scripts/python.exe -m playwright install chromium`准备完整可见Chromium；原有headless-shell不能代替可见窗口。每次用户原生确认准确公共HTTPS页面及form/message/upload/delete/transaction类别，专用可见窗口手工登录、全新内存Cookie、不导入个人profile。每任务最多8个准确origin/最多4专用会话；跨源资源须原生追加授权，先前被拒的请求不自动重试。

Windows从SDK固定路径建立`automation/browser-runtime/chromium-<版本>`私有副本：根仅保留chrome.exe，DLL、manifest及资源均原样放入版本子目录，避免本机flat布局的SxS 14001和混合DLL路径的沙箱崩溃。文件字节（含原签名数据）不变，不修改SDK/cache/系统程序集。最多1024文件/1GiB/2048目录项，拒绝reparse/硬链接/恶意XML；每次核对来源、元数据与整个副本hash，变化时拒绝而不覆盖修复。仅公开程序副本给ALL APPLICATION PACKAGES及ALL RESTRICTED APPLICATION PACKAGES只读执行，profile/任务数据不授予这些ACL；不放宽后端环境白名单。显式启用Chromium sandbox，可见原生验收读回renderer为Untrusted/非提升并核验自有进程回收。启动10秒、context/page各8秒有界；初始化失败关闭本次自有浏览器，关闭未确认时提示人工核对，不自动重试。

所有请求先route拦截再WriteNetwork固定公开DNS/IP/TLS出口，禁止continue直接联网。Worker/ServiceWorker/子框架/WebSocket/下载/附件/未知MIME不开放。初始同源GET资源有界引导；动态fetch/xhr GET、声明GET写端点和后续导航、任何非GET（含HEAD/OPTIONS）/自动保存必须每个请求独立审批。初始页面为声明的GET写端点时，先返回专用会话与明确尚未加载的空页面观察，批准实际请求后才加载；不会等待拿不到会话身份的审批。HTTP重定向不直接跟随，须用户重新明确授权最终HTTPS页面；写请求取得重定向回执后结果为uncertain，先核对外部效果。程序无法证明服务器对未声明的资源GET没有副作用。站点复杂CDN、框架、验证码、302登录/提交及WebSocket可能不兼容，拒绝而不降安全策略。

实际请求形成URL/method、普通字段、文件名/大小/hash、正文bytes/hash、敏感遮盖和完整性说明。普通JSON/表单在8KiB、30字段、深度6预算内展示；截断/未知正文/敏感字段明确不视作全量。单上传2MiB、最多1文件，只main原生选择；实际multipart还需独立批准。Cookie/Authorization/密码/支付秘密只在专用内存，不入模型、审计或日志。请求3MiB、排队最多4项/总4MiB、单审批180秒；每会话200请求/8MB响应，各响应512kB。拒绝或过期绝不外发。

HTTP2xx/3xx仅response_received/verified:false。外发完成核验必须有当前请求回执，且批准前指定的精确文字子串在提交前正文不存在、提交后真实DOM出现；否则awaiting_verification。文字匹配仍不是独立业务真值或结算证明。本地填写/勾选/选择/上传只核验实际控件值；纯点击无回执不能标完成。发送中取消/断线uncertain，关闭回收专用context/进程及等待请求，绝不自动重发。

## 状态、审计与恢复

计划300秒有效，native main保存实际预览，后端会话/版本/前置条件再检。`awaiting_approval → running → completed`只在对应程序证据成立；Browser另有awaiting_request/response_received/awaiting_verification。失败、取消、中断、不确定独立记录。每会话最多100步骤，history最近20事实；源码/页面和秘密不能审批。重启只读事实，不恢复运行时授权；没有自动继续或通用撤销。

SQLite保留哈希、目标必要元数据、状态及核验摘要；请求审计只保留准确origin、method、正文/URL哈希、字节、类别与完整性/文件数量，不保存URL路径/查询、字段正文、文件路径或请求头。脚本副本/产物留应用私有任务目录供本次核对/回传。未实现按日期自动删除任务副本；它们不进入Git，用户可退出应用后管理自己的测试数据。原始截图/网络/网页正文默认不持久化。

宿主异常强杀时Job的KillOnClose仍回收运行进程，但finally可能来不及移除本次OS私有AppContainer profile；残留不恢复任务授权或自动重放。正常退出尝试删除自有profile，本轮未单独核验profile删除成功。新文件回传/副本写入中断可能留下待人工核对的部分新文件，不自动删除或覆盖补写。

## 试用、测试与限制

`npm run build`后`npm start`，新建对话展开“M18可控执行”。粘贴`from pathlib import Path; Path('output/result.txt').write_text('合成结果',encoding='utf-8')`，完整预览→原生批准→实际状态completed→逐文件回传；输入文件须先选择目录并明确列相对路径。桌面先开自己的合成应用、原生选择窗口，选控件/动作/值/副作用/人工预期，逐步预览批准，再重新观察。Browser填准确HTTPS站点、允许类别，在专用窗登录，控件计划另批，实际请求出现后再次原生决定，再核对新出现结果。

默认测试不调用模型。可选脚本草稿只发送≤1000字用户需求至固定Computer `glm-5.3-flashx`/`https://open.bigmodel.cn/api/paas/v4`，4096输出token、30秒等待（适配器20秒）、一次零重试，原生确认费用后生成待审稿，不执行。Main/Browser固定映射不变。

测试代码在`backend/tests/test_m18_*`、`apps/desktop/tests/m18-*`、`tests/e2e/m18*`。报告/合成运行时/fixture/截图只放忽略的`artifacts/test-results/M18/`。实际命令、通过数、mock范围和残余风险见[PROGRESS](../../../../docs/PROGRESS.md)。真实LPAC/UIA/Chromium合成验收不代表真实第三方网站/所有应用兼容、供应商模型可用或独立Windows机器验收。M14旧包无M15–M18，M20后重建安装包核对待办保留，不发布Release。
