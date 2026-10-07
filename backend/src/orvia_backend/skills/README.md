# Skills 注册与顺序工作流（V4-002 / V4-006）

提供 Orvia 自有 v1 声明式契约、内置登记、用户主动导入审查、版本启停、版本绑定计划、LangGraph 顺序组合执行及 SQLite 事实账本。它不是任意第三方 Skill 格式的自动兼容层。

`service.py` 包含包读取、受限 schema/引用校验、SQLite 登记、组合计划、执行图和只读历史。仅使用已有 Python 3.12、LangGraph、aiosqlite、Pydantic；本模块没有新增依赖、真实模型调用或网络访问。

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

文件工具叶节点只允许 `list_directory`、`search_files`、`get_file_metadata`、`analyze_directory_space`、`read_text_file`；V4-006另允许固定本地 `memory_context`、`query_rewrite`。全部再次应用各自Pydantic工具契约。文本读取需要额外的既有 grant；默认桌面入口不授予文本权限。没有文件变更、Shell、任意代码或权限节点；原有文件变更仍经既有聊天审批链。

节点参数只支持标量、结构化对象、`{"from_input":"path"}` 与 `{"from_step":"previous","path":["data","path"]}`；步骤引用只能指向之前节点。`skill` 节点必须在 dependencies 中声明，编译时展开成唯一叶节点 ID，子 Skill 输入、输出以及父节点输出均在执行时校验。

整个工作流10秒总预算；结果含执行步骤正文不超过32KiB。超预算、失败、输出不符合 schema、受限结果立即停止后续步骤。LangGraph 完成状态需要所有叶节点真实完整返回、输入输出校验及 SQLite 保存，任何 `complete!=true`、截断或 errors 都保存 `limited`；不把部分扫描称为完整成功。超时和取消保留 `interrupted/unknown`，不接受晚到响应或自动重试。重启将旧 planned/running 标为 interrupted，只展示账本，不恢复内存审批或自动继续。

## 内置能力与试用

`file-organize` / File Organize 实际执行一级清单（40项）→空间统计（前5项），输入 `{"path":"."}`；它不生成或执行移动/重命名计划。Memory Context与Query Rewrite在V4-006已接入真实本地业务组合，详见下文；Web Research、Report Build仍等待V4-010不可执行。

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

Memory Context 与 Query Rewrite 已迁移为真实内置1.1.0，迁移只改内置内容、保留用户禁用状态并增加generation使旧计划失效。Web Research / Report Build仍明确不可用，等待V4-010。

工具允许清单新增`memory_context({query})`和`query_rewrite({query,revision?})`，均不接受cid、grant、model或generate。Main可信异步dispatcher闭包提供固定会话cid：前者调用实际`chat.memory.context`，后者调用`chat.rewrite.search`。两个只读工具必须返回`{complete,truncated,errors,data}`，不能包装未完成投影为成功。Main将业务data限制8KiB，记忆保留当前状态，依次删末尾命中、最旧轮和超长摘要；检索最多5引用并受8KiB投影预算；截断时complete=false，工作流limited且停止后续节点。完整数据仍通过独立业务入口查看。

内置Memory Context输入`{"query":"费用"}`，本地读取五轮/当前状态/批准摘要/有原文支持记忆；不外发。内置Query Rewrite输入`{"query":"费用","revision":""}`，先组合MemoryContext再读取当前资料；空字符串明确表示仅原查询，不自动挑选历史版本。用户可把已通过独立原生批准的准确sha64改写版本填入revision，原问题必须与批准版本一致、支持来源实时有效；它不从manifest隐式生成或调用Main，也不授予文件权限。声明式参数仍保持原v1格式，没有新增可执行表达式/default绑定语义。

`plan(...,mission_id=当前会话cid,grant_id=None)`只允许展开后全部leaf属于上述两个本地工具；含任何Computer文件工具必须有真实UUID目录grant。execute再次检查，cancel消费同一None身份。主进程负责核验cid真实存在、固定调度业务；包不能伪造会话或提供另一个cid。文件模式原有ComputerGateway逐叶授权不变。导入组合包也只可调用固定本地工具或已有文件工具，云改写入口不在允许清单。

本地模式账本归属于已明确选择的会话，聊天删除需清除其skills_executions；原独立目录Mission账本仍保留。计划本身不授予隐式云批准或新资料范围。本地检索可能受10秒Skill总预算限制；独立业务检索总预算180秒，不能宣称所有本地索引都可在组合预算内完成。

L1/L2：`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_rewrite.py`验证真实MemoryContext→QueryRewrite LangGraph组合、空版本原查询/批准版本、零云调用、无目录grant文件拒绝、cancel、迁移保留禁用。旧Skills回归48通过/1skip/旧占位期望1失败，期望随实际内置3项更新后，主Agent最终相关集合57通过/1skip，106个不同后端通过/1skip见PROGRESS。证据在`artifacts/test-results/V4-006/`。无新增依赖或真实模型测试。
