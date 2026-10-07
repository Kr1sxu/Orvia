# Skills 注册与顺序工作流（V4-002 / V4-006 / V4-010）

提供 Orvia 自有 v1 声明式契约、内置登记、用户主动导入审查、版本启停、版本绑定计划、LangGraph 顺序组合执行及 SQLite 事实账本。它不是任意第三方 Skill 格式的自动兼容层。

`service.py` 包含包读取、受限 schema/引用校验、SQLite 登记、组合计划、执行图和只读历史。仅使用已有 Python 3.12、LangGraph、aiosqlite、Pydantic；Skills核心没有新增依赖或直接模型/网络调用；V4-010适配只创建调研计划、读回事实和创建成品预览，网络、云生成和文件保存经独立业务审批。

## 公共接口与调用流程

`SkillsService(store)` 在已打开的 `Store` 上调用 `await open()`，新增 `skills_registry`、`skills_executions` 而不修改既有 `user_version`。迁移使用 SQLite 事务。

- `await list(offset=0)`：最多10项，返回 `{skills, offset, total}`；每项包含 ID、名称、版本、内容 hash、启用状态、内置标记、依赖与明确不可用原因。
- `await preview_import(absolute_path)`：安全读取原生选择的目录，返回 `{review_id, revision, manifest, documentation, warnings}`；不会注册或执行包。
- `await register(review_id, revision)`：只供原生确认后的可信主进程使用，重新读取全部内容核对 SHA-256，再保存登记；同版本不同内容要求新版本。
- `await set_enabled(skill_id, enabled)`：启停保存到 SQLite；每次实际状态变化增加 generation，禁用后再启用也不能复活旧计划。
- `await plan(skill_id, inputs, mission_id, grant_id)`：核对输入、依赖和现有工具契约，返回不可变的 `{plan_id, revision, skill_id, version, mission_id, grant_id, inputs, steps, bindings, status}`。
- `await execute(plan_id, revision, mission_id, grant_id, dispatcher)`：在准确计划原生确认后消费一次内存计划。`dispatcher(tool, arguments)` 必须是可信异步调度器，文件叶由闭包注入固定 Computer 角色和目录 grant，经既有 `ComputerGateway` 执行；本地业务叶由闭包注入准确会话cid，调用下文固定本地适配器。
- `await cancel(plan_id, revision, mission_id, grant_id)`：原生取消消费计划，保存 `interrupted/SKILL_CANCELLED`；零工具调用。
- `await get_execution(plan_id)`、`await history()`：读回结果或最近20项 ID/版本/状态摘要。结果包含每步实际状态、结构化响应、稳定错误与最终状态。

计划不是权限；导入、启用、说明正文、结果、缓存和模型均不能创建授权。执行前和每步响应后核对所有绑定的 Skill 版本及 generation。计划与 mission/grant/revision 不匹配时保存失败并拒绝，不借用其它任务的审批。原生执行取消后撤销 grant 的责任在主进程。

## 包与预算

目录顶层恰好两个 UTF-8 普通文件：`SKILL.md`（最多8KiB）和 `workflow.json`（最多16KiB）；另有两文件合计64KiB硬限制及完整审查32KiB通信限制。读取至第三个目录项立即拒绝；脚本、子目录、链接、联接、重解析点、敏感路径和读取期间变化均拒绝，使用既有路径策略及原生打开句柄核验。

最多32个导入 Skill，16个未消费审查、64个内存计划。每包1～16节点、最多16依赖；ID为2～64字符的小写字母开头且仅字母/数字/连字符，版本是 `major.minor.patch`。名称/说明拒绝控制字符及无效Unicode，并按桌面UTF-16长度限制，保证分页摘要可解码且有界。依赖缺失标为不可用；循环或超过4层拒绝，禁用节点也不能掩盖拓扑循环。总计最多32个叶工具步骤。输入最多8KiB；单次绑定展开16KiB，包含私有契约校验与输出映射的计划总计40KiB；解析实际结果也先扣32KiB预算再复制，防止重复引用指数膨胀。

输入/输出 schema 仅支持 `object/string/integer/boolean`、对象 properties/required/additionalProperties、字符串长度、整数范围、标量 enum。输入根对象拒绝额外字段；不支持 `$ref`、数组 schema、正则、表达式或任意 schema 扩展。工具结果的开放 object 仅作为有界 JSON 观察，完整性仍由程序依据 `complete/truncated/errors` 判断。schema 最多6层，参数最多8层。

文件工具叶节点只允许 `list_directory`、`search_files`、`get_file_metadata`、`analyze_directory_space`、`read_text_file`；V4-006另允许固定本地 `memory_context`、`query_rewrite`；V4-010增加 `research_create`、`research_status`、`report_build_preview`。全部再次应用各自Pydantic工具契约。文本读取需要额外的既有 grant；默认桌面入口不授予文本权限。没有文件变更、Shell、任意代码或权限节点；原有文件变更仍经既有聊天审批链。

节点参数只支持标量、结构化对象、`{"from_input":"path"}` 与 `{"from_step":"previous","path":["data","path"]}`；步骤引用只能指向之前节点。`skill` 节点必须在 dependencies 中声明，编译时展开成唯一叶节点 ID，子 Skill 输入、输出以及父节点输出均在执行时校验。

整个工作流10秒总预算；结果含执行步骤正文不超过32KiB。超预算、失败、输出不符合 schema、受限结果立即停止后续步骤。LangGraph 完成状态需要所有叶节点真实完整返回、输入输出校验及 SQLite 保存，任何 `complete!=true`、截断、errors、pending_approval/pending_cloud/pending_save/limited/unknown 状态都保存 `limited`；不把部分扫描称为完整成功。超时和取消保留 `interrupted/unknown`，不接受晚到响应或自动重试。重启将旧 planned/running 标为 interrupted，只展示账本，不恢复内存审批或自动继续。

## 内置能力与试用

`file-organize` / File Organize 实际执行一级清单（40项）→空间统计（前5项），输入 `{"path":"."}`；它不生成或执行移动/重命名计划。Memory Context与Query Rewrite在V4-006已接入真实本地业务组合，详见下文；Web Research、Report Build在V4-010迁移为真实1.1.0准备入口；准备返回limited和明确待审批状态，不宣称调研或保存成品已完成。

开发版设置的 Skills 区域可启停、原生选择包、检查完整正文与声明后注册。选择 File Organize 或可用导入包，输入结构化 JSON，原生选择合成目录，在准确目录、业务输入、步骤预览后确认执行。最近执行可查询保存结果；目录模式任务是独立Mission，删除聊天不删除此独立账本；V4-006本地模式属于明确选择的会话，删除该会话清除相应执行正文并拒绝晚到写入。

可导入的最小 `workflow.json` 示例：

```json
{
  "schema_version": 1,
  "id": "observe-file",
  "name": "单文件观察",
  "version": "1.0.0",
  "description": "读取已授权相对路径的文件属性",
  "input_schema": {
    "type": "object",
    "properties": {"path": {"type": "string", "minLength": 1, "maxLength": 1000}},
    "required": ["path"]
  },
  "output_schema": {"type": "object", "additionalProperties": true},
  "dependencies": [],
  "steps": [{
    "id": "observe",
    "tool": "get_file_metadata",
    "arguments": {"path": {"from_input": "path"}},
    "output_schema": {"type": "object", "additionalProperties": true}
  }],
  "output": {"observation": {"from_step": "observe"}}
}
```

配套 `SKILL.md` 仅写用途与说明。组合包将上述 ID 写入 dependencies，并以 `skill:"observe-file"` 节点引用；每次更新包必须重新审查且使用不同版本。

## 验证与限制

L0：`backend/.venv/Scripts/python.exe -m compileall -q backend/src/orvia_backend/skills`。

L1/L2：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_v4_skills.py -q --basetemp=artifacts/test-results/V4-002/skills-tmp --junitxml=artifacts/test-results/V4-002/skills-junit.xml`。

目标测试使用真实临时 SQLite、LangGraph、ComputerGateway 和合成目录，覆盖组合与先前结果引用、审查变化、版本/启停失效、预算与重复展开、分页通信、schema、依赖、只读失败、取消及重启账本。失败与时钟由合成测试注入，没有真实模型调用；Windows普通账户不能创建符号链接的创建用例可能 skip，但本机已使用普通权限实际创建目录联接并验证包被拒绝。桌面 L3/IPC 证据由主 Agent 记录在 PROGRESS，临时产物统一在 `artifacts/test-results/V4-002/` 并忽略。

这是受限顺序只读工作流；没有通用并行节点、条件表达式、自动依赖安装、自动重试、恢复执行或通用撤销。结果不能证明任意文件内容真实，说明和工具输出始终是不可信数据。新增节点种类或能力需对应模块明确实施；本地会话归属与删除由V4-006实际实现。

## V4-006 本地业务组合

Memory Context 与 Query Rewrite 已迁移为真实内置1.1.0，迁移只改内置内容、保留用户禁用状态并增加generation使旧计划失效。Web Research / Report Build已在V4-010迁移为实际准备入口，详见后节。

工具允许清单新增`memory_context({query})`和`query_rewrite({query,revision?})`，均不接受cid、grant、model或generate。Main可信异步dispatcher闭包提供固定会话cid：前者调用实际`chat.memory.context`，后者调用`chat.rewrite.search`。两个只读工具必须返回`{complete,truncated,errors,data}`，不能包装未完成投影为成功。Main将业务data限制8KiB，记忆保留当前状态，依次删末尾命中、最旧轮和超长摘要；检索最多5引用并受8KiB投影预算；截断时complete=false，工作流limited且停止后续节点。完整数据仍通过独立业务入口查看。

内置Memory Context输入`{"query":"费用"}`，本地读取五轮/当前状态/批准摘要/有原文支持记忆；不外发。内置Query Rewrite输入`{"query":"费用","revision":""}`，先组合MemoryContext再读取当前资料；空字符串明确表示仅原查询，不自动挑选历史版本。用户可把已通过独立原生批准的准确sha64改写版本填入revision，原问题必须与批准版本一致、支持来源实时有效；它不从manifest隐式生成或调用Main，也不授予文件权限。声明式参数仍保持原v1格式，没有新增可执行表达式/default绑定语义。

`plan(...,mission_id=当前会话cid,grant_id=None)`只允许展开后全部leaf属于固定本地工具（记忆/检索，以及V4-010调研准备/状态/成品预览）；含任何Computer文件工具必须有真实UUID目录grant。execute再次检查，cancel消费同一None身份。主进程负责核验cid真实存在、固定调度业务；包不能伪造会话或提供另一个cid。文件模式原有ComputerGateway逐叶授权不变。导入组合包也只可调用固定本地工具或已有文件工具，云改写入口不在允许清单。

本地模式账本归属于已明确选择的会话，聊天删除需清除其skills_executions；原独立目录Mission账本仍保留。计划本身不授予隐式云批准或新资料范围。本地检索可能受10秒Skill总预算限制；独立业务检索总预算180秒，不能宣称所有本地索引都可在组合预算内完成。

L1/L2：`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_rewrite.py`验证真实MemoryContext→QueryRewrite LangGraph组合、空版本原查询/批准版本、零云调用、无目录grant文件拒绝、cancel、迁移保留禁用。旧Skills回归48通过/1skip/旧占位期望1失败，期望随实际内置3项更新后，主Agent最终相关集合57通过/1skip，106个不同后端通过/1skip见PROGRESS。证据在`artifacts/test-results/V4-006/`。无新增依赖或真实模型测试。


## V4-010 调研与简报准备组合

内置 `web-research` 和 `report-build` 为真实1.1.0，迁移保留用户禁用状态并增加generation。导入包仍使用Orvia v1 object/scalar schema；没有新增数组、表达式、网络执行或保存节点。

固定工具接口由Main可信dispatcher注入唯一会话cid，字段不能注入其它cid、模型、审批或输出文件路径：

- `research_create({query,urls})`：query 1～200字符，urls为换行分隔的显式1～10个公共HTTP(S)地址、最多5个host，标量最多8000字符且仍受Skill输入8KiB预算。复用Browser地址校验，不在计划时解析DNS；真正读取时仍执行Browser实时网络检查。调用实际`ResearchService.create(cid, query, urls=...)`，不自动扩展查询、发起搜索、collect或云请求。生成的task/operation_id属于真实SQLite计划事实。
- `research_status({task_id})`：UUID字符串，只读实际同cid的`ResearchService.status`；跨会话任务拒绝。计划、正在采集、仅原文已采集、limited/unknown结果不能推进。只有task.state=ready、final.state=saved且message_id为准确UUID，同时实际采集范围完整，才可推进；它仍不证明成品已经保存。采集完整要求coverage.limitations为空、search_unavailable为false、attempted_pages/ready_pages/search_rounds/distinct_final_pages与实际pages/searches非负整数计数一致；所有page为ready且有final_url/evidence_id、无error，所有search为completed且无error。明确urls必须全部有对应成功page，明确queries必须全部有对应成功search，task.error为空。只有sources明确非空的原文任务允许零网页；网址计划的零读取或任何空范围不以0==0当完成。最终综合即使已经保存，也不能抹掉页面失败、搜索不可用、遗漏范围或原有coverage限制，组合将limited并停止。固定预算内的引用片段不证明完整行业覆盖。
- `report_build_preview({message_id,format,title})`：message_id为同cid已保存synthesis UUID，format为docx/pptx/pdf，title 1～40字符。Main从该条保存消息取完整answer和claim texts，调用真实`chat.publication_preview`并复用M16来源与引用校验。不会从包生成新回答、改变引用或调用save；原文超现有M16预算则拒绝，不截断后称为完整成品。

内置Web Research输入例如`{"query":"比较合成资料","urls":"https://example.com/a\nhttps://example.org/b"}`，真实准备结果强制`complete=false,status=pending_approval`，执行保存limited并立即停止后续步骤。用户进入独立Research界面逐阶段核对公共来源采集范围、准确批次发送与最终综合发送后批准。固定Skill计划批准不代替这些许可，十页/两轮只是业务上限。

内置Report Build输入例如`{"message_id":"已保存综合消息的UUID","format":"pdf","title":"合成调研简报"}`，生成准确成品预览，程序强制`complete=false,status=pending_save`并停止。保存须在独立成品入口进行原生新文件确认，写入及读回验证后才有成品事实；Skills中没有任何保存适配器。即使dispatcher误报complete=true，两个准备工具也不能被视为completed。

已完成调研可用导入组合声明 `research_status` → `report_build_preview`，后一节点的message_id引用`{"from_step":"status","path":["data","final","message_id"]}`，保留逐步completed/limited状态。只有实际saved消息身份才可绑定简报，pending或部分结果不会被跳过。当前版本不自动恢复或续跑旧Skill；需要新的准确计划和审批。

与File Organize、授权文本读取或Query Rewrite混合时，mission_id必须是已有真实chatcid；任何文件叶都另需准确目录grant，文本叶另需allow_text。Main逐文件叶调用ComputerGateway，其余固定本地叶只用同cid业务服务。纯本地允许grant=None；混合包不能借本地模式得到文件、云或保存许可。执行记录属于该会话，删除墓碑拒绝迟到正文重建。

dispatcher必须返回`{complete,truncated,errors,status?,data}`。数据仍受整个Skill 10秒/32KiB预算，Main可给业务投影设更小上限，任何截断都complete=false且停止。来源引用、task/消息身份与pending状态必须可见；bounded投影不能代替Research完整原文、引用和保存事实。Skill本身只承担准备与可组合只读观察，独立业务阶段分别完成才达到调研和简报目标。

L0：`backend/.venv/Scripts/python.exe -X utf8 -m py_compile backend/src/orvia_backend/skills/service.py backend/tests/test_v4_research_skills.py`。

L1/L2：`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research_skills.py -q --basetemp artifacts/test-results/V4-010/skills-final-temp --junitxml artifacts/test-results/V4-010/skills-final.xml`，原24个目标通过。测试使用真实SQLite、LangGraph、目录网关、Research create/status和三格式publication preview；synthesis准备为合成已保存消息fixture，Research ready状态链为明确合成阶段fixture，不冒充网络采集、模型生成或保存成品。collect、Main complete和publication_save设为禁止调用，覆盖混合逐叶授权、pending不推进、source归属、URL/站点预算、迁移禁用、重复审批与原生取消。首次4个失败是fixture错误读取repository.messages的(messages,count)元组，修复后最小4项复验通过。

采集覆盖审查后，新增11个目标并修正正向ready阶段fixture的页面计数。按实际改动最小复验：`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research_skills.py -q -k 'status or pending_envelope or source_only' --basetemp artifacts/test-results/V4-010/skills-coverage-temp --junitxml artifacts/test-results/V4-010/skills-coverage.xml`，20通过/15未选；仍有效的原15项结论复用，合计35个不同目标有通过证据。覆盖ready+saved仍有搜索不可用、读取失败、0页未读、遗漏URL/检索、覆盖计数不一致、缺字段、任务错误，以及明确source-only零页与空范围拒绝。Skills相关旧回归、真实采集、模型mock阶段和Electron流程由主Agent在PROGRESS独立记录，真实模型未调用。
