# 查询改写与本地检索（V4-006）

`RewriteService(chat)`保留原问题，最多三个候选仅用于当前会话 ready 资料检索；Main建议必须匹配程序生成的有限白名单。没有新依赖、执行动作、资料授权、自动云调用或模型替换。

## 接口与结构

`await open()`追加SQLite表`rewrite_previews(cid,revision,packet_json)`、`rewrite_attempts(cid,revision,state)`、`rewrite_records(cid,revision,data_json)`。所有会话删除须在既有事实删除事务清除三表。尝试账本无正文、每会话最多128项，网络前持久化；上限拒绝新调用，不淘汰未知事实。预览最多20批、已完成/失败记录最多32条，历史展示最近20条并限制32KiB。重启running转interrupted，不自动重发。

- `preview(cid,query,memory_ids=[])`：准确问题1～200字，用户明确最多选择3项verified记忆；实时核验原文支持与状态，不接受conflict/revoked。返回`id/revision/supplier/purpose/instructions/input/bytes/status/reason`，`input`包含准确original、memories引用、当前问题最多5片段、scope准确标签、scope_revision正文/证据版本签名及allowed_candidates。实际input＋instructions最多24KiB，完整预览32KiB。此阶段零模型调用。
- `generate(cid,revision)`：仅可信原生批准入口使用。固定Main deepseek-flash/https://api.deepseek.com，一次30秒、max_tokens1024，无重试。输出严格JSON仅`candidates:[{query,source_ids}]`最多3；重复字段、未知字段、未支持查询、伪造引用、工具调用或未正常结束均回原问题。公共结果为`{id,original,candidates,status,reason,revision}`；status是rewritten/original/clarification。缺Key/超时/模型失败保留原问题和稳定原因；取消由原生入口直接零调用本地检索。重发同批原问题回ALREADY_ATTEMPTED，不因预览淘汰恢复许可。
- `search(cid,query,memory_ids=[],revision=None)`：没有批准版本只检索原问题；有版本必须原问题准确相等，非空记忆选择必须同批准批次。返回`{id,original,queries,rewrite,evidence,truncated}`；queries[0]永远为原问题。最多4查询、结果最多5、合计32KiB；按来源定位/content_hash去重并合并通道，保留现有引用身份。资料严格当前cid ready scope，跨会话记忆不授予跨会话资料权限。来源撤回、正文或范围变化使批准候选失效；检索过程中变化拒绝旧结果或重新仅用原查询。
- `history(cid)`：`{records:[result]}`。每次重核来源；被撤回支持不由摘要或历史恢复。它是改写事实记录，不是对原需求的覆盖或任务完成证明。

## 改写规则与权限

固定同义词：费用→成本/经费，计划→方案，预算→经费，进度→进展。代词只在明确选择的唯一项目/人物来源支持时替换：项目需key=当前项目，人物名来自其准确key。人物/项目类型不匹配、多主题、无主题，返回clarification，零模型调用；带数字、URL、路径或危险动作的主题保守拒绝。`memory:<sha64>`或`fragment:<chunk_id>`是查询依据，不能生成grant。新数字、否定条件、工具动作、新路径、新URL不会从模型自由输出进入检索。文件/资料代词没有可用的普通主题名时要求用户在原问题明确名称，当前不提供任意文件实体推断。

所有选中记忆及资料原文都作为不可信内容。程序在预览、网络前、最终写入事务和回查时重新检查准确来源、版本及当前范围。明显敏感字段拒绝；有限检测不证明所有敏感数据都能识别，原生完整内容预览仍是外发批准的必要条件。默认记忆投影本地读取，不自动发送跨会话内容。

## 运行、测试与证据

复用项目Python3.12虚拟环境、Pydantic、aiosqlite及V4-004检索；没有新工具/依赖/模型下载。开发版设置的查询改写入口先本地检索，也可选择明确记忆、预览完整固定Main输入并原生确认，再检索原问题＋批准候选；取消只用原问题。

L0：`backend/.venv/Scripts/python.exe -X utf8 -m compileall -q backend/src/orvia_backend/rewrite backend/src/orvia_backend/skills`。

L1/L2：`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_rewrite.py -q --basetemp=artifacts/test-results/V4-006/rewrite-final-data --junitxml=artifacts/test-results/V4-006/rewrite-final.xml`；最终21个不同目标用例及后续最小复核以PROGRESS实际记录为准。初次测试未建立basetemp父目录发生13个setup错误，随后12通过/1记忆冲突fixture失败；正确采用不同支持主题后通过。所有Main都是mock；SQLite/FTS及LangGraph是真实临时服务，未调用真实云模型。固定3合成主题Recall@5原查询1.0，改写1.0，持平；`rewrite-recall.json`记录实际结果，不宣称改善。旧Skills目标回归和桌面原生取消/通信结果由主Agent记录。

已验证代词/同义/歧义、最多3、原问题保留、无依据操作与新数拒绝、模型失败和无重试、预览缓存失效、来源/范围撤回、最终事务竞态、取消等价零调用原检索、128账本上限、真实Skills组合/版本迁移/禁用与零云调用。L3、敏感审计及本地commit见PROGRESS。产物统一`artifacts/test-results/V4-006/`并Git忽略。

当前规则刻意保守，不保证自由语义改写、任意中文代词或任意文件指代；不同模型建议不能扩大白名单。检索分数与召回只用于查找引用，不证明原文结论正确；本机mock云流程不代表供应商质量或真实费用测量。

独立检索180秒总预算覆盖所有表达、来源重核及撤回后的原查询回退；单个本地嵌入沿用V4-004最多30秒且失败关键词降级。Skill组合仍仅10秒，总预算不足时unknown/interrupted而非声明检索完成。query-rewrite内置required revision接受空串明确原查询，或准确64hex批准版本；不自动选择历史。

最新审查复核：代词仅匹配查询开头且符合有限边界，“其他费用／吉他费用”保留原词；预览保存与网络前事务均再次核验alive及来源签名，禁止删除／撤回竞态晚写或外发。多查询超5项明确truncated。Skills执行late-result通过实际删除标记和移除账本用例证明不能恢复会话正文。
