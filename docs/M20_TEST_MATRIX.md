# M20 验收测试矩阵

日期：2026-10-03最终收口。四项方案A、功能F01–F24及流协议S01–S10按下表实际范围验证；真实Main安装成功与开发失败分别保留。完整包资源、实际隔离安装/版本升级及开发对照通过，卸载及合成profile保留已通过。此表不代表生产签名或独立Windows验收。

复用M15–M19已记录结论，仅重测M20改动及安装影响。所有测试限既定测试目录；真实Main预算共2次已消费，无追加重试。准确命令、历史失败、mock/实际组件及最新证据以PROGRESS为准。

产物统一放被Git忽略的`artifacts/test-results/M20/`。证据至少含验证ID、真实组件、替身范围、实际事件数与顺序、终态和覆盖限制；不记录密钥、原始云请求、用户资料或敏感响应。进度条、截图和构建成功不能单独证明任务完成。

## 功能与拒绝边界

| 验证ID／清单对应 | 级别与目标测试路径 | 实际验证、可观察成功证据 | 真实组件／mock范围 | 状态 |
|---|---|---|---|---|
| F01／A1–A2、E1 | L0／L1／L3；`apps/desktop/tests/m20-ui.test.tsx`、`tests/e2e/m20.spec.ts` | 默认提示“你想做些什么”；没有需求类型下拉；欢迎例子包含目录、文档和网页，直接发送进入同一自然语言入口 | 实际React／Electron；业务模型mock；沿用M19视觉 | 通过 |
| F02／A3、A7、C6 | L1／L3；`backend/tests/test_m20_natural.py`、`tests/e2e/m20.spec.ts` | 自然目录需求真实枚举206条／递归207条，程序答案与实际条目对应，模型调用数0 | 实际路由／文件网关／SQLite／Electron；无需模型 | 通过 |
| F03／A3–A5、E3 | L1／L3；`backend/tests/test_m20_natural.py`、`tests/e2e/m20.spec.ts` | 显式HTTPS读取→M15片段预览→回答，保存网页引用能回查且详情进入阅读区；仅提及URL、代码／资料中的URL不触发访问 | 实际路由／Browser限制／引用库；DNS／HTTP／Main mock，无公网兼容性证明 | 通过 |
| F04／A5–A6、E3 | L1／L2／L3；`backend/tests/test_m20_natural.py`、受影响M12／配置目标、`tests/e2e/m20.spec.ts`、`tests/e2e/m20-installed.spec.ts`开发模式 | 搜索、读取和已有证据理解路由不同；缺Tavily明确不可用，固定角色缺凭据明确失败，历史证据不冒充新搜索 | 实际凭据／路由；复用M12搜索边界，搜索／模型mock；真实Tavily0调用 | 通过 |
| F05／A3–A4、E4 | L1／L3；`backend/tests/test_m20_natural.py`、`tests/e2e/m20.spec.ts` | 唯一资料／最近网页支持指代；多资料以真实ID必要澄清并正确接续；裸本地路径不读取 | 实际资料关联／会话存储；模型mock，有限合成歧义用例 | 通过（方案A） |
| F06／A6、E5 | L1／L2／L3；`backend/tests/test_m20_natural.py`、`backend/tests/test_m20_transport.py`、`tests/e2e/m20-business.spec.ts` | 目录→重命名计划→原生拒绝后文件不变→批准→真实核验→父请求完成；文本同意不充当批准，未支持／提权任务明确拒绝 | 实际计划／审批链／文件账本；Main／原生决定mock | 通过 |
| F07／A7、B4、E5 | L1／L2／L3；`backend/tests/test_m20_natural.py`、`apps/desktop/tests/m20-contracts.test.ts`、`backend/tests/test_m20_transport.py`、`tests/e2e/m20-installed.spec.ts`开发模式 | 恶意合成资料、围栏／引号内指令不授予权限；strict契约拒绝伪造路径／批准／身份／额外字段，5组非法IPC实测拒绝，无Node／通用invoke | 实际契约／后端复核；有限恶意fixture，非所有攻击形式证明 | 通过 |
| F08／B1–B2 | L0／L1／L3；`apps/desktop/tests/m20-ui.test.tsx`、`apps/desktop/tests/m20-contracts.test.ts`、`tests/e2e/m20.spec.ts`、`tests/e2e/m20-native.spec.ts` | 单一“＋”可访问菜单键盘操作与焦点回还；固定文件／文件夹入口；另有真实原生目录／文件返回及Main取消后generate计数0 | 实际菜单／固定IPC；一般L3选择器mock，所属PID/HWND真实Windows框单列 | 通过 |
| F09／B2–B4、E4 | L1／L2／L3；`backend/tests/test_m20_natural.py`、`backend/tests/test_m20_transport.py`、`tests/e2e/m20.spec.ts`、`tests/e2e/m20-installed.spec.ts`开发模式 | 最多3份／每份10MiB／总30MiB；逐文件事实与超限拒绝；坏PDF不阻止同批DOCX ready；真实DOCX／PPTX／PNG OCR，无父目录授权 | 实际解析／SQLite；原生选择mock，OCR实际本地推理，无默认上云 | 通过（方案A） |
| F10／B3–B4、B6 | L1／L2／L3；`backend/tests/test_m20_natural.py`、`tests/e2e/m20.spec.ts`、`tests/e2e/m20-installed.spec.ts`开发模式 | 移除仅解绑、历史资料／引用保留、待发送预览失效；撤目录权限后拒绝执行；合成原文件未被解绑修改 | 实际资料／授权／历史；选择器mock | 通过（方案A） |
| F11／B5–B6、E1 | L2／L3；`backend/tests/test_m20_transport.py`、`tests/e2e/m20.spec.ts`、`tests/e2e/m20-native.spec.ts` | 先需求→waiting_input→选择资料／授权→同一原请求接续，用户消息一次；多附件结束后接续；真实原生返回亦完成目录回答／DOCX解析 | 实际stdio／SQLite／Electron；模型mock，真实与替身选择分别记录 | 通过 |
| F12／B5–B6、D5、E7 | L1／L2／L3；`backend/tests/test_m20_natural.py`、`backend/tests/test_m20_transport.py`、`tests/e2e/m20.spec.ts` | 取消选择／请求、切会话、断流／重启使旧接续失效，原请求保留；旧token／重复回包不串任务，重连无权限或自动重放 | 实际会话／连接／SQLite；受控终止自有stdio，选择器／慢模型mock | 通过 |
| F13／C1–C3、E2 | L1／L2／L3；`backend/tests/test_m20_natural.py`、`backend/tests/test_m20_transport.py`、`tests/e2e/m20.spec.ts`、`tests/e2e/m20-installed.spec.ts`开发模式 | 空0、混合类型与大目录直接显示真实条目；明确仅扩展名／元数据分类；批次前无虚构结果或正文理解声明 | 实际合成目录／扫描／SQLite；模型0调用 | 通过 |
| F14／C2、D4、E2 | L1／L2／L3；`backend/tests/test_m20_natural.py`、`tests/e2e/m20.spec.ts`、`tests/e2e/m20-installed.spec.ts`开发模式 | 206条按100／100／6；6000中实际发现5000、50页去重回查；长路径可变页长按实际游标／访问页历史；计数、深度、拒绝与截断明确 | 实际快照分页；时间／访问拒绝部分fixture；不声称未扫描6000条全部完成 | 通过（方案A） |
| F15／C2–C3、D4 | L1／L2／L3；`backend/tests/test_m20_natural.py`、`backend/tests/test_m20_transport.py`、`tests/e2e/m20-installed.spec.ts`开发模式及既有网关目标 | 一级／明确递归、深度／路径拒绝／reparse与身份边界、5000项／10秒墙钟／4MiB；真实scandir取40条后sink可控跨限不取第41；最终大目录复测通过 | 实际网关／枚举／SQLite；时间、不可访问和身份故障包含注入，未遍历所有真实Windows ACL组合 | 通过 |
| F16／C4–C6、E4 | L2／L3；`backend/tests/test_m20_transport.py`、`tests/e2e/m20.spec.ts`、`tests/e2e/m20-native.spec.ts` | 自然附件／网页摘要进入M15确切片段预览；批准后mock SSE／claims／引用核验与回查；真实Main原生取消0调用；本地检索不强制上云 | 实际M15验证／证据／Electron；Main mock，原生取消独立真实证明 | 通过 |
| F17／A6、C4、E5；M16 | L2／L3／L4；m20-publication-parity.spec.ts及m20-live.spec.ts | 开发/安装同合法合成mock回答seed，经3自然请求真实生成Word/PPT/PDF、3新账本、引用/标题/结构读回、各PDF2页实看；另有安装真实Main回答→三格式成功 | 真产品后端/本地M16；原生保存决定mock；seed与真实供应商证据分列，Office未渲染 | 通过（开发/安装三格式） |
| F18／A6、C4、E5；M17代码 | L2／L3；`tests/e2e/m20-business.spec.ts` | 自然需求在显式项目上下文生成允许栈草稿／差异／逐文件批准；拒绝不写，批准后文件和SHA核验、父请求完成；12文件／64KiB边界保留 | 实际M17／文件网关；Computer／原生决定mock，无安装／执行／部署 | 通过 |
| F19／A6、C4、E5；M17原型 | L2／L3；同F18 | 实际两页结构化原型可导航及表单模拟、三个文件批准写回；受限React预览沿用恶意HTML／脚本拒绝，源码不执行 | 实际预览／文件；Computer mock，非任意生成代码执行 | 通过 |
| F20／A6、C4、E5；M17清理 | L2／L3；同F18 | 自然清理合成Temp顶层40天old.tmp；取消不变→批准隔离→核验→明确恢复；新／其他类型／嵌套排除，无永久删除 | 实际清理账本／同卷文件；测试专用合成Temp根及原生决定mock，未操作用户Temp资料 | 通过 |
| F21／A6、C4、E5；M18脚本 | L2／L3／L4；`tests/e2e/m20-business.spec.ts`、`backend/tests/test_m20_packaged_runtime.py`、`tests/e2e/m20-runtime-parity.spec.ts` | 粘贴／Computer草稿／单选.py自然入口，批准后真私有Python3.12＋LPAC／Job与逐文件回传；同CID两脚本新token／operation_id精准2次continue；越界／socket／环境边界通过 | 开发真解释器／LPAC；Computer／原生决定mock；packaged_runtime单元不启动解释器，冻结安装真实对照通过 | 通过（开发/安装） |
| F22／A6、C4、E5；M18桌面 | L2／L3／L4；同F21 | 自然输入→点击在自有WinForms两次准确UIA操作，新步骤token／基线、两份completed账本及APPLIED读回后完成；running／旧成功fact不能推进 | 实际UIA工作器／窗口／账本；原生决定mock；拒绝fixture复用，不是所有应用兼容性证明 | 通过（开发/安装运行时） |
| F23／A6、C4、E5；M18浏览器 | L2／L3／L4；同F21 | 准确HTTPS／类别确认，专用可见Chromium真实fill读回仍暂停；POST另批／2xx／SHA／匹配新DOM后完成；开发运行时实际动态GET暂停拒绝／LowIL回收 | 真实Chromium／拦截／账本；DNS／HTTP／原生决定mock，无真实账号／交易／公网兼容性证明 | 通过（开发/安装运行时） |
| F24／A6、B6、C4、E5 | L2／L3；`backend/tests/test_m20_transport.py`、`tests/e2e/m20.spec.ts`、`tests/e2e/m20-business.spec.ts` | 附件／网页→回答→Word，Python草稿→另审→运行→回传实际闭环；desktop两步、browser填写与发送均依真实核验，取消／失败不执行后续 | 实际跨模块编排／账本；模型／网络／原生决定mock；复合范围有界，非任意业务 | 通过 |

## 真流、持久化与阅读体验

| 验证ID／清单对应 | 级别与目标测试路径 | 实际验证、可观察成功证据 | 真实组件／mock范围 | 状态 |
|---|---|---|---|---|
| S01／D1、E6 | L0／L1／L2；`apps/desktop/tests/m20-contracts.test.ts`、`apps/desktop/tests/m20-transport.test.ts`、`backend/tests/test_m20_transport.py` | strict版本／会话／业务请求／传输请求／流／seq；身份／额外字段拒绝；UTF-8分块、12KiB事件／64KiB帧，批次／delta／各终态走stdio | 实际Python子进程／JSON Lines／TS缓冲；供应商mock | 通过 |
| S02／D2–D3、E1–E2 | L2／L3；`backend/tests/test_m20_transport.py`、`tests/e2e/m20.spec.ts` | 工具实际枚举批次在最终答复前输出，门闩证明至少2个实际批次；路径对应真实目录；40条可见后kill另见S09 | 实际扫描／stdio／Electron；仅门闩／暂停，无模型或虚构进度 | 通过 |
| S03／D2–D3、D7 | L1／L2／L3；`backend/tests/test_m20_model_stream.py`、`backend/tests/test_m20_transport.py`、`tests/e2e/m20.spec.ts` | 异步SSE未完成时UI已显示answer delta；UTF-8／JSON转义／Unicode／心跳／DONE／finish_reason及慢流验证；无完成文本定时切字 | 真ModelClient／httpx解析／stdio／Electron＋MockTransport；不是供应商支持证明 | 通过（mock Main流） |
| S04／D2、D7、E7 | L2／L3／L4；`tests/e2e/m20-live.spec.ts` | 开发首次INVALID_GENERATION，111字前缀/seq66、无成功；安装独立1次11真实delta/20字/seq2–12、结束前输出、2引用与三格式成品核验成功，usage680+713=1393 | 真固定deepseek-flash/合成DOCX；开发1024与安装4096上限分别说明，共2次/5120预算，0重试；原生决定测试替身，Computer/Browser真实0 | 安装真实链通过；开发失败保留 |
| S05／D2、D5、C4；M15–M16 | L1／L2／L3；`backend/tests/test_m20_model_stream.py`、`backend/tests/test_m20_generation_errors.py`、`backend/tests/test_m20_transport.py`、`tests/e2e/m20.spec.ts` | 增量正文明确未核验；完整JSON／claims／引用通过才成功；坏引用、格式错误、取消／断流不形成M15／M16成功；重启partial无成品入口 | 实际verify_generated／存储／M16门禁；mock SSE，真实开发失败亦无成品 | 通过 |
| S06／D4、D7 | L1／L2／L3；同S05 | 不支持SSE／断流后原生明确同模型非流式一次新请求，计数2／stream true→false；重启无第三次，无自动补发。length与stop＋未闭JSON准确分开；M15恢复原4096输出上限，普通answer／意图1024 | 实际客户端／错误映射／策略；兼容／终态为mock。恢复4096不重放真实开发失败，不以mock推断其finish_reason | 通过（方案A） |
| S07／D4、E7 | L1／L2；`backend/tests/test_m20_model_stream.py`、`apps/desktop/tests/m20-stream.test.ts`、`apps/desktop/tests/m20-transport.test.ts`、`backend/tests/test_m20_transport.py` | slow consumer下有界队列／字节／条目／文本、stdout pause与ACK释放；非法／过旧ACK拒绝，停止消费／背压到限终止，取消终态亦排空 | 实际stdio／Node缓冲／reducer；受控consumer／时钟，非任意机器长期压力证明 | 通过 |
| S08／D5、E7 | L1／L2／L3；`apps/desktop/tests/m20-stream.test.ts`、`apps/desktop/tests/m20-transport.test.ts`、`backend/tests/test_m20_transport.py`、`tests/e2e/m20.spec.ts` | duplicate不重复追加，16项有界乱序／2秒gap；错流不污染会话，缺口停止读取持久事实不重发业务，父子流身份保持 | 实际reducer／stdio／SQLite；故障事件注入 | 通过 |
| S09／D5、E7 | L1／L2／L3；`backend/tests/test_m20_transport.py`、`backend/tests/test_m20_stream_persistence.py`、`backend/tests/test_m20_natural.py`、`tests/e2e/m20.spec.ts` | 扫描可见40条后实际杀自有stdio，3次重启分页稳定／一条partial事实；模型可见前缀后kill、2次重启同model_partial ID／完整已显示前缀／last_seq不退，无恢复token或重发。保存成功答案但终态未发时不重复假partial，后续复合仅未核验tail保留 | 真实kill／SQLite／重启，模型mock。目录批次／seq／消息分开提交，两个提交窗口故障注入；模型前缀＋seq同UPDATE。成功保存窗口及NUL／Unicode是实际SQLite目标，不称所有窗口实际kill | 通过 |
| S10／D4–D5、B6 | L2／L3；`backend/tests/test_m20_transport.py`、`tests/e2e/m20.spec.ts` | 允许期取消／超时／断流持久cancelled／failed／interrupted并按原身份排空；重连无权限／自动重放；未知副作用不强杀后重试 | 实际任务／stdio／账本；慢SSE／扫描mock；供应商取消计费未测 | 通过 |
| S11／D6、E6–E7 | L1／L3；`apps/desktop/tests/m20-ui.test.tsx`、`tests/e2e/m20.spec.ts`、`tests/e2e/m20-ime.spec.ts`、`tests/e2e/m20-ime-input.ps1` | 慢mock SSE切历史保持100px阅读位置／草稿／焦点，旧流不写新CID；合成composition／Enter229不误发。另真OS VK NIHAO→Space，trusted start／update、ordered end／你好草稿／请求1→1 | 实际Electron／OS SendInput，HKL0804／Electron44.4.5／Chromium152.0.7977.130；end=false按匹配源码记录。候选Enter仅合成229，未确认具体Microsoft拼音profile／其他IME | 通过（范围见本列） |
| S12／C4–C5、D6 | L0／L3；`apps/desktop/tests/m20-ui.test.tsx`、`tests/e2e/m20.spec.ts` | 长中文／混合文本／长路径／分页和终态可读；答案／真实成品直接呈现，详情／审批按需展开；760×560引用详情／最终Word无横溢、输入可见；M19资源保留 | 实际React／Electron／离线资源；合成资料；其他Windows／DPI／辅助技术全组合未重测 | 通过 |

## 完整安装包与开发版对照

| 验证ID／清单对应 | 级别与目标测试路径 | 实际验证、可观察成功证据 | 真实组件／mock范围 | 状态 |
|---|---|---|---|---|
| P01／完整安装待办 | L0／L4；`backend/tests/m20_package_audit.py`、`apps/desktop/tests/runtime.test.ts` | 候选版本与npm／uv锁自身版本一致；冻结源码含M15–M20；依赖锁定；三字体、折帆、OFL／历史LICENSE许可、OCR／PDFium／ONNX、M16库／字体、UIA工作器完整且hash一致；ASAR白名单无密钥／库／日志／用户文件 | 实际冻结/完整包与安装资源审计通过；无模型 | 通过（具体范围见最终对照） |
| P02／M18私有解释器 | L2／L4；`backend/tests/test_m20_packaged_runtime.py`、`tests/e2e/m20-runtime-parity.spec.ts` | 启动实际安装EXE→实际PyInstaller后端→可信资源CPython3.12→校验并复制私有运行时→真实LPAC＋Job合成脚本；报告进程映像／版本／manifest hash；篡改或缺失关闭能力，无系统PATH回退 | packaged_runtime单元仅合成资源字节验证路径／hash拒绝，不启动解释器；runtime-parity才验证实际被冻结后端与独立解释器。不得以开发解释器或m18_backend.py替换产品backend后称安装通过 | 通过（具体范围见最终对照） |
| P03／可见Chromium／UIA | L2／L4；同P02 | 实际包锁定headless与完整可见Chromium均存在；安装后专用可见窗口和UIA合成应用动作核验；缺资源／篡改／个人浏览器路径不回退；零网络／提权脚本边界与开发一致 | 实际安装运行时／Chromium／UIA；自有合成站点／应用；DNS／HTTPmock范围明记 | 通过（具体范围见最终对照） |
| P04／真实安装升级卸载 | L4；`tests/integration/m20-install.ps1`、`tests/integration/m20-upgrade.test.ts` | 唯一M20身份和无reparse隔离路径安装旧版本基线→合成历史→真正新版本升级→数据保留／权限失效／无重放→核对EXE／注册项／快捷方式／hash→自有卸载；不碰普通Orvia或旧包，不删除用户配置 | 实际NSIS／Windows注册／文件／SQLite；基线明确旧资源封装；不能以同版本重装称升级 | 通过：安装/实际升级/卸载及profile保留 |
| P05／开发／安装关键对照 | L3／L4；`tests/e2e/m20.spec.ts`、`tests/e2e/m20-publication-parity.spec.ts`、`tests/e2e/m20-installed.spec.ts`、`tests/e2e/m20-runtime-parity.spec.ts`、`tests/e2e/m20-live.spec.ts` | 同一合成fixture按F11／F13–F17／F21–F23分别比较请求状态、条目／引用／三格式成品结构、批准边界、LPAC／UIA／Chromium和S02／S04流证据；每项记录相同／差异／未覆盖，不能只比欢迎页 | 真实开发与实际安装EXE／冻结资源；mock与真实供应商各列，安装后端不替换 | 通过（具体范围见最终对照） |
| P06／离线／缺凭据／限制 | L4；`tests/e2e/m20-installed.spec.ts`安装模式、`tests/e2e/m20-runtime-parity.spec.ts` | 空safeStorage缺凭据明确；离线原生解析／OCR／列表／导出实际工作；云任务报告失败；系统PATH隔离、环境注入／资源缺失均无回退；renderer无Node／通用invoke；不把本机PATH测试称独立机器 | 实际安装safeStorage／资源／Electron；网络禁用与故障注入范围明记 | 通过（具体范围见最终对照） |
| P07／定向跨模块回归 | L4；既有`test_m15_synthesis.py`、`test_m16_publication.py`、`test_m18_protocol.py`及实际受影响测试；M20整合入口 | 按改动影响选择M15审批／M16引用／M17写入／M18权限／旧会话迁移／协议回归；保留既有有效M19资源与窗口结论；新失败只重跑失败最小集合，不无条件全套 | 开发99桌面单元／受影响后端127／stdio与持久化18／成功窗口42等实际通过，模型／网络mock；不累加重跑；安装关键业务及运行时对照已通过 | 通过（开发定向/安装对照） |
| P08／独立发布事项 | 发布验收；不纳入本轮通过率 | 生产证书签名、独立Windows机器／VM／AVD／其他系统DPI／安全软件兼容性仍暂缓；候选NotSigned，不能称正式发行；旧任务栏固定项缓存差异保留 | 尚无本轮独立环境证据 | 用户暂缓，未完成 |

## 建议命令与证据记录

以下命令对应已新增入口，仍须依阶段和前置资源选择执行；矩阵编辑本身不运行测试。ID保留映射，避免漏验。L0构建、mock增量、供应商真实流和安装版各有独立结果，不合并为一个“通过”。

```powershell
# L0：源码变更后执行；输出保存到M20结果目录
npm run check
npm run build

# L1：自然语言编排、扫描、资料、生命周期与实际模型SSE适配器的mock
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_m20_natural.py backend/tests/test_m20_model_stream.py --junitxml=artifacts/test-results/M20/backend-target.xml
npx vitest run apps/desktop/tests/m20-contracts.test.ts apps/desktop/tests/m20-stream.test.ts apps/desktop/tests/m20-ui.test.tsx --reporter=json --outputFile=artifacts/test-results/M20/desktop-target.json

# L2：实际Python/stdio/SQLite与Node运输缓冲；模型、网络为合成替身
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_m20_transport.py --junitxml=artifacts/test-results/M20/stdio.xml
npx vitest run apps/desktop/tests/m20-transport.test.ts --reporter=json --outputFile=artifacts/test-results/M20/transport.json

# L3：实际Electron；启动器仅替换明确的模型/网络/原生业务对话框
$env:ORVIA_TEST_MODULE='M20'
$env:ORVIA_TEST_RESULTS=(Join-Path (Get-Location) 'artifacts/test-results/M20')
npx playwright test tests/e2e/m20.spec.ts
# 独立的自然语言写入／生成／执行业务，仅在上项完成后顺序运行
npx playwright test tests/e2e/m20-business.spec.ts --output=artifacts/test-results/M20/business-e2e
# 真选择结果与取消，不替换产品后端；SelectionItem读回与测试固定BM_CLICK仅作用于本次所属HWND
npx playwright test tests/e2e/m20-native.spec.ts --output=artifacts/test-results/M20/native-e2e
# OS组合与合成229保护分列；须显式physical模式，仅自有窗口固定NIHAO/Space
$env:ORVIA_M20_IME_PHYSICAL='1'
npx playwright test tests/e2e/m20-ime.spec.ts --grep '真实Windows中文IME' --output=artifacts/test-results/M20/ime-physical-e2e

# L4：须新冻结资源与准确候选配置完成后执行，不复用M19定向视觉包
backend/.venv/Scripts/python.exe -X utf8 packaging/build_backend.py
npx electron-builder --config packaging/m20-full.config.cjs --win --publish never
backend/.venv/Scripts/python.exe -X utf8 backend/tests/m20_package_audit.py
# 旧版资源基线另按packaging/m20-baseline.config.cjs构建；它只验证升级，不冒充新后端
powershell -NoProfile -NonInteractive -File tests/integration/m20-install.ps1 -Stage InstallBaseline
$env:ORVIA_M20_UPGRADE_STAGE='seed'
npx vitest run tests/integration/m20-upgrade.test.ts
powershell -NoProfile -NonInteractive -File tests/integration/m20-install.ps1 -Stage Upgrade
$env:ORVIA_M20_UPGRADE_STAGE='verify'
npx vitest run tests/integration/m20-upgrade.test.ts
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_m20_packaged_runtime.py --junitxml=artifacts/test-results/M20/packaged-runtime.xml
$env:ORVIA_M20_PARITY_MODE='development'
npx playwright test tests/e2e/m20-runtime-parity.spec.ts
$env:ORVIA_M20_PARITY_MODE='installed'
npx playwright test tests/e2e/m20-runtime-parity.spec.ts
backend/.venv/Scripts/python.exe -X utf8 backend/tests/m20_package_audit.py --installed
powershell -NoProfile -NonInteractive -File tests/integration/m20-install.ps1 -Stage Uninstall
```

S04独立入口m20-live.spec.ts须显式ORVIA_M20_LIVE=1和development／installed模式，独占live-budget.json损坏／重复消费即关闭。已说明固定Main、合成DOCX、20秒网络／30秒生成、零重试：开发首次历史1024输出token已失败消费，安装独立剩余1次恢复M15原4096上限，合计2次／5120token，不重放开发失败、不增加次数。原completion及finish_reason／usage未保留，不补造或从111字猜原因；安装结果另记，不在默认命令中触发。runtime-parity固定实际安装路径`artifacts/test-results/M20/install-smoke/`及可信资源链，安装测试清除开发环境配置，不能通过修改后端启动器伪造产品冻结能力。普通m20-launch仅在测试侧注入合成凭据及mock网络；其结果不能替代runtime-parity或供应商真实流。

2026-10-03已取得独立业务L3的七项成功证据：`business-rename.json`为真实目录→重命名计划→原生拒绝／批准→文件读回与父请求接续；`business-sequential.json`中四项通过分别为代码草稿逐文件批准写入、两页受限原型导航与表单、旧合成Temp隔离与恢复、Computer草稿及第二次原生单选.py的真实LPAC／Job执行与token／operation_id隔离；`business-browser.json`为专用可见Chromium填表读回后父请求仍暂停，再经POST另批及响应／页面匹配核验才完成；`business-desktop-completed.json`为同父请求下两个独立token、准确自有窗口、真实UIA输入与点击、两份completed账本及最终APPLIED文字读回。桌面执行返回running时不接续，需同本次预览operation_id的completed与verified后再推进。模型／HTTPS网络／原生选择批准框均为测试替身，stdio、SQLite、文件核验、LPAC／Job、UIA、Chromium与权限复核为真实组件。先前失败报告保留；成功范围只对应这些具体断言和表内注明的复用边界，不等于任意业务、应用或公网验收。

主对话8个不同L3目标均已通过，最终`publication-system-fact-e2e.log`为Word真实文件／引用／父流程完成／成品viewport，`history-verified.log`为慢SSE中阅读／草稿／焦点，`references-partial-e2e.log`为网页详情与断流一次降级／重启。`desktop-final.json`99项通过；`backend-agent-report.md`列实际命令／范围。`stdio-persistence-final.xml`18项包含扫描可见40条后实际kill、3次重启清单／分页一条事实及模型前缀后kill／2次重启同partial ID；`model-success-window.xml`42项、`model-nul-boundary.xml`6项验证保存成功但终态未发、未核验tail及合法字符边界。目录批次／seq／消息分别提交，模型前缀＋seq同UPDATE，不能混称全链原子或所有窗口均实际kill。partial只有未核验文字／警告，无引用／成品，失败LiveResult不重复同流partial。

开发`runtime-parity-development.json`1项52.3秒证明两次自然脚本各自新operation／精准2次continue、真私有解释器／LPAC边界／回收、UIA、可见Chromium动态GET暂停拒绝；不是安装证据。`offline-development-results.md`最终目录25.1秒整项通过，6000中发现5000／50页／撤权／重启；整项耗时含造数据、分页、重启和退出，不能当扫描耗时。真实DOCX／PPTX／PNG OCR、Markdown／JSON引用导出10.7秒及缺凭据／严格IPC4.8秒通过，仅路径选择／保存替身，业务后端未替换，模型／公网0。权限错误注入不冒充全部真实ACL；清理仅合成Temp，UIA仅自有WinForms，浏览器无真实账号／交易；引用一致性不是事实真值。

历史阶段记录（已由最终证据取代）：当时F17三格式、S04安装和P01–P06尚待。现已完成安装三格式、真实Main与完整安装链，保留开发真实失败，见表及末节。

原反馈图`codex-clipboard-a056e09b-6fb8-49aa-9ce4-4951a7b1543f.png`最初项目／产物精确搜索未找到，仅有V2文字记录；该搜索失败作为历史保留。2026-10-03主Agent在当前用户Temp顶层找到原图并实际查看，保存副本`artifacts/test-results/M20/design/reference.png`：旧绿色／序图标、两个资料入口、类型下拉、目录仅折叠卡片和需求重发，与当前四项交互目标对应；实施仍复用已确认M19视觉。模拟选择／批准L3与下列真实原生框、真实OS IME和真实供应商失败分列；不将替身、OS SendInput或mock SSE称为人工物理键盘或完整供应商成功。

`m20-native.spec.ts`和`m20-native-dialog.ps1`已真实运行，最终`native-main-cancel.json`／日志1项通过（22.1秒）：空凭据runtime-parity启动器与真实产品后端，只固定选择器defaultPath至合成树，返回值仍来自真实Windows框。实际主PID／项目Electron路径／隔离profile／所属唯一HWND核对；唯一合成目录与固定synthetic.docx通过SelectionItemPattern选择及IsSelected读回，真实原生返回后分别完成目录回答和DOCX解析。当前Windows UIA provider对原生Button报告Pane且无Invoke，初始AutomationId／准确Name筛选与文件名ValuePattern假设均安全失败，旧诊断报告保留；实际所属子Button的准确标题／ID／文案／enabled被记录后，测试专用固定BM_CLICK在再次核对同PID／dialog-root／class／唯一性后仅发送一次，不重试、不改M18产品UIA。Main准确原生审批的“取消”已实际操作，generate-method调用计数0，父token保留，无成功synthesis。截图仅该所属HWND或本应用页面；`native-C83qsv/native-scope-correction.json`更正初始报告预留的宽泛ValuePattern／Invoke说明，个别事实文件保留原样。测试后自有PID60148已退出。

`m20-ime.spec.ts`／`m20-ime-input.ps1`先只读实际自有UI线程，`ime-prerequisite.json`1项通过：HKL=0x8040804、langID0x0804、自有前台／焦点root／renderer输入焦点均成立，0键／无布局改动。随后`ime-physical.json`目标项保留失败：固定ASCII VK NIHAO的10次下／上键与单独获准Space的2次键事件，收到实际trusted compositionstart及n→ni→ni'h→ni'ha→ni'hao→“你好”的更新，最终草稿“你好”、原自然请求1→1；compositionend出现但isTrusted=false，严格trusted-end验收未成立，不擅称完整候选提交或具体Microsoft拼音profile已确认。全程无Unicode注入／Enter／dispatch／候选窗口读取／语言设置切换，草稿清空恢复，实际PID50956已退出。旧严格trusted-end失败与下列匹配版本的真实OS组合通过分别保留；DOM合成composition／229保护不是物理候选Enter证据。

只读来源排查另记`artifacts/test-results/M20/ime-source-investigation.md`：本地Electron44.4.5与官方DEPS对应Chromium152.0.7977.130；该版本start／update通过EventTarget设置trusted，end沿新建事件默认false的ScopedEventQueue路径分派，未设置trusted。这与本轮真实OS输入的观察相符，不能用end=false单独推断输入来自脚本，也不能用任意untrusted事件证明真实输入。监听后到结果快照期间未调用fill／press／insertText／dispatch，清理发生在快照写入之后；源证据、原失败和版本对应复测分别保留。

主Agent依据该primary源码链准入一次版本对应复测，`ime-physical-versioned.json`／日志1项通过（6.7秒）：直接process.versions为Electron44.4.5／Chromium152.0.7977.130／Node24.21.0；保留全部OS归属守卫和trusted start／update断言，核对ordered end及data“你好”、实际草稿“你好”和请求1→1，end.trusted=false原样记录。`ime-physical-T4t0eX/ime-physical.json`及仅本产品页面截图为实际证据，自有PID13792已退出。该测试用OS SendInput固定ASCII VK共12键，不是人工物理键盘；没有Unicode／Enter／dispatch／候选窗读取／布局设置修改，不确认具体Microsoft拼音profile，也不推定其他IME／Windows环境。物理候选Enter未执行，只有慢mock SSE期间DOM合成composition／229防误发；实际ordered end.trusted=false按匹配Chromium源码原样记录。

文档/接口中文注释/架构/试用说明已按最终证据校正；功能、完整包本机对照、暂缓生产签名/独立Windows三类分别记录。本地commit及待用户手动push状态以PROGRESS和Git事实为准。

2026-10-03最终前端竞态增补：`stream-race-unit-final.json`8项及`race-e2e-corrected.log`3项通过。真实Electron延迟create/pull回包门闩证明切新视图保留草稿/焦点且不发原需求、旧paused与授权接续重叠后全部批次ACK、慢流阅读历史保护。无新增模型调用，模拟网络及原生选择；paused只轮询有界主进程缓存，终态/协议错误不复活。最终renderer为index-DOENNuF8.js，D7中间包归档保留，最终安装证据另记。

## 最终补充证据（此前待验文字为过程记录）

安装离线3项34.8秒、运行时1项30.8秒、三格式1项14.3秒、真实Main1项13.9秒全部通过。两种候选包实际NotSigned、81Python分发/142原许可、3OCR权重、M16/私有Python3.12.6/完整Chromium/UIA/三字体图标核验；22份业务dist与当前build及两种包逐字节一致，59冻结输入hash一致。安装版资源4257文件、凭据检查为true且命中0；普通候选单独资源审计通过。具体差异/合成原生替身/真实供应商失败与成功分列在`artifacts/test-results/M20/development-installed-comparison.md`，不得互相替代。

F17：开发和安装同已核验mock合成seed，真实自然请求生成DOCX/PPTX/PDF并独立重开核对，PDF每份2页已实际查看。S04：另用安装版真实Main回答生成三格式、2引用核验及PDF2页实看成功；只一次模型请求，无额外生成费用。Office未实际渲染，Word页数是规划而非Office分页。

P04的旧基线实际安装、升级exit0，seed/verify各1项passed、其他阶段skip；历史5条及文档引用保留、旧grant失效，无自动重放。卸载exit0且EXE/注册项/快捷方式移除、合成profile/SQLite保留已实测；最终index/敏感检查另在PROGRESS末节记录，P08生产签名/独立Windows仍暂缓。
