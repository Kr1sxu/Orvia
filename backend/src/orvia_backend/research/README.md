# V4-010 有界只读调研

`ResearchService` 把明确问题、公开站点、网页和已关联资料组成独立调研计划，逐步保存采集、原文引用综合和实际成品保存的事实。SQLite 是事实存储；预览缓存、批次摘要和模型自述不授予权限，也不证明业务完成。

## 结构与依赖

- `service.py`：计划、只读采集、研究范围检索、准确发送预览、固定 Main 生成、实际成品回执和中断处理。
- `__init__.py`：导出 `ResearchService`、`ResearchError`。
- `contracts.py`：主接入维护的严格协议输入，拒绝未知字段；会话身份由可信分发链传入。
- `backend/tests/test_v4_research.py`：实际 SQLite、Browser 解析、FTS 与合成网络/模型适配测试。

复用项目锁定环境，无新增依赖、工具或模型下载。本机 Python 3.12.6、aiosqlite 0.22.1、pydantic 2.13.5、httpx 0.28.1、trafilatura 2.2.0、jieba 0.42.1。固定 Main 为 `deepseek-flash` / `https://api.deepseek.com`，模型凭据仍由既有私有初始化管道注入内存。Tavily 缺失明确记录不可用，失败占搜索轮次，不伪造搜索结果。

## 公共接口与输入输出

构造 `ResearchService(store, chat)` 后 `await open()`；启动只迁移表和标记中断，绝不自动联网、重发或恢复批准。

| 方法 | 行为 |
| --- | --- |
| `create(cid, question, urls=[], queries=[], sites=[], sources=[])` | 保存 `planned` 计划，不访问网络；必须至少有一项 URL、搜索问题或明确资料 |
| `collect(cid, operation_id)` | 准确原生批准后消费单次采集尝试，返回含逐页/搜索事实的任务 |
| `status(cid, operation_id)` / `history(cid)` | 读取真实任务；历史最多十条并受 48KiB 整包预算 |
| `preview(cid, operation_id, stage='batch', sources=None)` | 返回完整 system/input、供应商、用途、原文片段、覆盖统计与 revision，未调用模型 |
| `generate(cid, operation_id, stage, revision)` | 消费准确预览并固定 Main 单次生成；最终保存既有 `synthesis` 消息 |
| `cancel(cid, operation_id)` | 取消并等待实际读取/模型协程结束；不自动重试 |
| `record_publication(cid, message_id, data)` | 仅可信保存成功回调；复查实际 publication 事件及 synthesis 原始版本，再记成品回执 |
| `has_unresolved(cid)` / `forget_previews(cid)` / `close()` | 当前生命周期删除阻塞、撤销预览、等待关闭；中断的只读终态可删除 |

问题 1～500 字符；URL 最多十个、合计 8KiB；搜索问题最多两条、每条 1～200 字符；站点最多五个准确公共 host。URL 按现有 Browser 策略规范化、去重；host 转为规范小写后去重，不隐式允许子域。`sources` 最多三个 `{kind:'browser'|'document', evidence_id:hex64}`，必须仍是当前 M20 明确关联且 ready 的原始资料。问题、搜索和原始全文均检查现有敏感内容规则。

任务返回 `id/operation_id/revision/question/urls/queries/sites/sources/state/pages/searches/batches/final/publications/coverage/error`。网页状态为 `running/ready/failed/duplicate/blocked`，搜索为 `running/completed/failed/unavailable`；错误与取消后不保留运行中的搜索步骤。`coverage` 记录实际网页尝试数、成功数、搜索轮次、不可用搜索、最终 URL 去重数与限制句。

状态顺序为 `planned → collecting → collected|limited`，批次摘要 `generating → 原状态`，最终回答 `generating → ready`。失败、取消、中断分别保留实际步骤。`ready` 表示最终带引用回答已保存；页面失败、来源遗漏、样本偏差或报告尚未保存不能据此视为全部业务完成。报告只在真实原生保存后追加 `publications` 回执，最多三个，保存不由调研服务自行触发。

## 原文、检索与引用

采集复用 Browser 的公开 URL、重定向和静态/动态读取策略。十个**不同 URL 尝试**预算包括失败；同一规范 URL 不重复尝试，最终重定向 URL 重复不增加原始来源。两搜索轮失败也计数。候选结果最多每轮五条、URL/标题合计 8KiB；所选 host 外结果不读取，网页 URL/最终 URL 元数据另限 16KiB。整体采集 120 秒；Browser 既有单次读取 20 秒、搜索 10 秒，不重试。

网页按既有 EvidenceStore 的全文哈希身份与原文 schema 保存。写入原文、研究关联位于同一墓碑检查事务；FTS 使用现有 ContextService，底层存储写前同样核验删除墓碑。研究 `ready` 网页不会占用或扩大全局 M20 的三个有效资料权限。初始资料仍须 M20 ready，研究 `linked` 元数据不能取代该权限。

研究检索代理只把本任务来源映射为准确 `browser:eid` 或 `document:eid:unit` 标签，最多 150 个定位，前后检查原始完整版本与当前关联，再调用现有检索服务。FTS/已激活固定本地向量检索是原文优选辅助；未激活本地向量时保持原有关键词回退，不下载模型、不查未选全局来源。

批摘要最多四批，每批三个原始来源，每源最多三个既有 600 字符片段。已成功批次的处理来源由独立 SQLite 尝试元数据记录；缓存丢失不重发该 revision，后续批次跳过已处理来源。批次摘要显示正文最多 1800 UTF-8 字节，不作为最终引用。

最终最多十个来源、每源一个原文片段，优先准确研究检索命中再回退采样。若有十三个可用来源而默认只选十个，批准包 `input.scope` 明确 `selected_sources=10/available_sources=13/omitted_sources=3` 及排除三来源的限制句；显式子集同样说明遗漏。片段只是原文抽样，coverage 保留可用块数、缺页/OCR/截断状态，不宣称全文或行业覆盖。

完整 CloudPreview 包含 `id/operation_id/stage/revision/supplier/purpose/system/input/bytes/fragments/coverage/source_ids/limits`，固定用途为“调研批次摘要”或“调研最终综合”。实际发送**准确 system/input 两条消息**合计最多 42KiB，含重复可见原文的完整预览最多 48KiB；超量拒绝，需减少来源。每次固定 Main 30 秒、4096 tokens，零自动重试；不接受工具调用。最终须明确比较、冲突、缺口、覆盖四项，复用 `verify_generated` 验证 JSON、只引用本次发送片段、冲突引用两个不同原始证据。该验证不证明自然语言结论的语义真伪，用户仍应核对原文。

## 审批、持久化与删除

Electron 主进程分别原生确认完整采集计划、每批准确 Main 发送包以及每次 Word/PPT/PDF 保存。服务 API 仅供该可信路径调用；来源文本、renderer 参数、Skills 计划和模型不得自行授予这些许可。Skills 的研究创建只保存待审批计划；报告工具只产生既有 publication 预览，实际保存仍另批。

`research_tasks` 保存有界任务正文（每会话最多二十个）；`research_attempts` 保存无正文的 stage/revision/来源身份/状态单消费事实（每会话最多 128 个，独立于缓存）；`research_sources` 绑定证据全文版本和研究关联。预览缓存最多二十个，缓存丢失不恢复批准或自动重放。模型前、后和最终提交事务核验来源；采集消费事务同样重新核验初始资料是否撤回、ready 或原文被更改。

当前 `collecting/generating` 生命周期阻止永久删除。取消/关闭等待实际协程结束；重启将运行记录标为 interrupted，不自动读取网页或重新生成，也不永久阻止只读终态删除。会话墓碑或原始版本变化阻止迟到写入；管理层永久删除三张研究表及原文/消息/索引，保留用户原文件和实际导出成品。

## 运行与验证

从项目根目录执行；证据全部放在忽略的 `artifacts/test-results/V4-010/`。服务累计 **34 个不同 L1/L2 目标通过**，其中真实 SQLite、Browser HTML 解析、Context FTS、原文精确范围检索；网页 HTTP 与 Main 均为合成 fixture，未调用真实网页、Tavily 或真实模型。以下为实际执行的增量命令，后续最小集合复用仍有效的早期结论：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research.py -q --basetemp=artifacts/test-results/V4-010/service-data --junitxml=artifacts/test-results/V4-010/service.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research.py -q --basetemp=artifacts/test-results/V4-010/service-final-data --junitxml=artifacts/test-results/V4-010/service-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research.py::test_collect_rechecks_explicit_source_scope_before_any_web_request -q --basetemp=artifacts/test-results/V4-010/service-collect-guard-data --junitxml=artifacts/test-results/V4-010/service-collect-guard.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research.py::test_empty_scope_rejected_and_source_only_scope_valid backend/tests/test_v4_research.py::test_cancelled_search_has_terminal_step_and_missing_main_does_not_retry backend/tests/test_v4_research.py::test_final_explicit_subset_records_real_coverage_omission_and_batch_processed_fact -q --basetemp=artifacts/test-results/V4-010/service-scope-data --junitxml=artifacts/test-results/V4-010/service-scope.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research.py::test_thirteen_original_sources_default_final_sends_ten_and_approves_exact_omission -q --basetemp=artifacts/test-results/V4-010/service-thirteen-data --junitxml=artifacts/test-results/V4-010/service-thirteen.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_research.py::test_task_and_independent_attempt_caps_reject_before_requests backend/tests/test_v4_research.py::test_full_preview_budget_includes_duplicate_fragments_and_url_metadata -q --basetemp=artifacts/test-results/V4-010/service-budget-data --junitxml=artifacts/test-results/V4-010/service-budget.xml
```

结果依次 20、26、3、3、1、2 passed，重叠目标只计一次。覆盖初始资料撤回/完整版本篡改、网络失败与重定向去重、offsite 拒读、两轮缺 Tavily、不同阶段取消/重启、删除墓碑迟到返回、原文检索、引用/同源冲突拒绝、实际成品事件防伪、13→10覆盖遗漏、任务/尝试/整包预算和缺 Main 凭据单尝试。既有 LangChainPendingDeprecationWarning 不影响结果。

L3 Electron 审批/实际本地 HTTP/成品 DOCX/PPTX/PDF 保存及主协议验证由主 Agent 记录在 PROGRESS；本服务 fixture 成品回执测试不冒充实际文件保存或原生对话框验收。真实网络页面与供应商可用性、动态登录或全面行业调研、自然语言结论真实性不在这些测试的完成证据中。示例试用：明确问题及公开 URL→审查并确认采集→查看逐页事实和覆盖限制→可选逐批摘要→审查最终原文发送→保存带引用回答→选择 Word/PPT/PDF 原生保存成品。
