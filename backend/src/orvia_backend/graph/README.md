# V4-005 实体关系与本地查询

本模块从当前会话已存储的明确用户原文、已经关联且 `ready` 的文档/网页片段抽取人物、项目、文件及有限关系。预览、本地列举和跨会话查询不会调用模型；只有 Electron 主进程显示准确原生发送确认后才发出一次固定 Main 请求。图谱记录不授予文件权限，不证明任务执行完成。

`service.py` 负责 SQLite 来源版本、批次、模型输出核验和图遍历；`__init__.py` 导出 `GraphService` 与 `GraphError`。复用现有 `chat.store` 事务锁和 `chat.client`，无新增依赖、运行服务、模型下载或用户文件读取。

## 公共接口与输入输出

接口均为 async：`open()` 初始化派生表；`list(cid)` 返回 `{entities,relations,truncated}`；`preview(cid)` 返回 `{id,revision,supplier,purpose,instructions,input:{sources},bytes,truncated}`；`generate(cid,revision)` 在主进程准确批准后发出一次请求并返回最新 list；`query(query,entity_id=None,hops=2)` 返回 `{entities,paths,ambiguous,truncated}`；`revoke_source(cid,origin)` 撤回对应来源；`delete_conversation(cid)` 清理派生数据。Application 固定协议族为 `graph.list/preview/generate/query`，来源撤回与删除由现有可信会话流程接入。revision 只是准确正文版本，不能代表原生批准。

实体字段为 `id/conversation_id/scope/kind/name/status/sources`，kind 为 `person/project/file`，status 为 `verified/revoked`。关系字段为 `id/conversation_id/from_id/to_id/kind/status/sources`，status 为 `verified/conflict/revoked`。Source 为 `source_id/origin/quote/version/status`，status 为 `user_statement/source_excerpt`。Path 为 `{entities:[起点,…终点],relations:[前向关系,…]}`，最多两跳。

ID 同时绑定会话、来源 origin、完整原文版本、实体类型及名字。同一文档不同 unit 可以共享实体；不同来源或会话同名返回候选及 `ambiguous=true`，没有路径，需选择具体 entity_id。文档 version 为全部 unit 编号和完整正文的 SHA256；网页和消息为完整正文 SHA256。不是只对发送的前 2048 字节计算版本。生成前、生成后与最终 SQLite 事务内均重新核验版本、会话未删除、来源存在且资料仍 ready 关联。查询同样定点核验来源，完整正文发生变化、资料撤回或会话删除占位均停止支持，撤销状态不会通过重读自动恢复。

## 支持表达与冲突

Main 仅返回严格 JSON `entities[{key,name,kind,source_ids}]` 和 `relations[{from_key,to_key,kind,source_id,quote}]`。程序逐字核对本批支持，禁止额外字段、陌生来源、跨资料归并、错误方向和未核验实体类型。孤立实体仅接受独立完整句的 `人员名字/姓名名字/项目名字/文件名字`；关联实体类型由核验关系方向支持。

关系只接受完整来源中的独立完整中文句：

- `项目X的负责人是Y` 或 `Y负责项目X`：person → project，responsible_for。
- `Y参与项目X`：person → project，member_of。
- `文件X属于项目Y`：file → project，documents。
- `项目X依赖项目Y`：project → project，depends_on。

句界为中文/英文句末标点、分号或换行，只允许固定 `解释，` 前缀。含否定、假设、条件、可能、计划、短名字匹配长名字、尾部修饰或模型剥离否定的摘录不通过；模型把非事实前缀塞进人物名也不能通过。最后事务用完整未裁剪正文复核句子，避免预览截断恰好隐藏否定尾部。复杂自然语言暂不推断。同一来源版本项目出现不同负责人时保留全部原文并标 conflict，路径排除这些关系。模型遗漏批准原文已明确出现的另一负责人时直接拒绝整批，不能消费来源并留下单方 verified。冲突撤去一方后仍保守保留 conflict，需新来源版本的准确批准生成，不能静默推断。

敏感识别沿用 memory 的有限规则，检查完整正文，明显密码、Key、token、私钥和身份凭据排除。整个文档有明显敏感字段时整份文档不参与抽取。该规则不能识别所有隐私，发送预览和原生确认仍是必要边界。助手、工具事件、旧摘要和模型自述不能成为图谱原始支持。

## SQLite 事实与预算

- `graph_entities/graph_relations`：来源支持的图记录，实体全库 512、关系全库 1024，每条最多 8 个支持、每会话最多 128 个有效支持来源。
- `graph_batches`：最多 20 个正文预览缓存；清理缓存不改变调用事实。
- `graph_attempts`：每会话最多 128 个无正文调用事实，网络前事务持久化 running，完成事务写 completed，失败写 failed，启动将 running 改为 interrupted。旧 revision 从不自动重发。
- `graph_processed`：每会话最多 128 个无正文成功来源版本，成功批次事务内记录。后续预览跳过已成功处理的版本，允许 16 项一批接续；空图结果允许表示本批未抽取到图，不无限重发，但批准原文存在明确互斥负责人时空结果同样拒绝。该表仅证明本批调用及来源版本通过实际校验，不保证全文关系均被完整抽取。同版本 cache 丢失不影响接续或重发拒绝。达到上限拒绝新调用，需新建会话。
- `graph_revocations`：来源撤回标识；撤回只减少对应支持、清除对应 processed 元数据和正文预览。原 origin 恢复关联不会清掉撤回标识，也不会隐式重新批准。

发现范围为最多 3 份资料、每文档前 50 个 unit、最近 128 条明确用户消息，范围外标 truncated；单批最多 16 来源，片段最多 2048 UTF8 字节。任何正文裁剪、来源数量或字节预算不足均在预览标 truncated。实际 instructions + input 总发送最多 24KiB，整包预览最多 32KiB。一次请求 30 秒、max_tokens=1536、无重试，固定 deepseek-flash @ https://api.deepseek.com。

list 每类最多 20 个记录、总 32KiB；query 候选最多 20、前向最多两跳和 20 条路径、总 32KiB。候选从全库最多512实体消歧，选定身份后仅核验/遍历同会话、同来源及同全文版本的512个关系记录，其它会话的边不能挤掉该身份，所选范围额外关系明确 truncated。路径 visited 防止循环。信息过多时结果会先达到字节上限，不能保证一定展示到数量上限。

## 运行、试用与验证

沿用项目 `npm run dev` 启动开发版，打开设置中的实体关系入口，先在会话输入合成句 `解释，合成人甲负责项目合成航线。项目合成航线依赖项目合成导航。`。打开准确发送预览并检查来源和截断提示；原生取消不调用模型，原生批准才抽取。随后本地搜索 `合成人甲`，查看原文与两跳路径；同名候选必须点选。移除关联资料或删除会话后对应支持不可继续查询。

核心 L1/L2 使用真实临时 SQLite、原始会话和资料事实、固定 Main mock。43 个独立测试覆盖四种关系、三种实体、跨 unit 两跳、歧义、冲突及遗漏矛盾（含空输出）拒绝、方向、否定/假设/名字边界、敏感全文、整文尾部版本变化、网络后/最终事务竞态、删除占位、实际失败缓存清理不重发、启动 interrupted、来源撤回、16+4 接续、尝试/processed/UTF8/列表路径预算及其它会话512条边不影响当前准确身份。初次 19 个失败为测试夹具误以为 append 返回消息；修复后 23/24，通过关系严格句界发现缺少句号的夹具并修正；新增预算测试首次 36/37，32KiB 比20路径先触发，修正断言后最小复验通过。随后37项完整通过、3项冲突覆盖/scope新测试通过；非事实前缀藏进姓名的2项新增测试与相关关系集合最小复验通过；空输出隐藏双方负责人1项通过。完整结果与失败历史保留，不读取真实 Key，不调用云模型。具体桌面协议与 Electron 验证由主 Agent 记录 PROGRESS。

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_graph.py -q --basetemp=artifacts/test-results/V4-005/core-final-data --junitxml=artifacts/test-results/V4-005/core-final.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_graph.py::test_list_and_path_budgets_are_bounded_with_real_supported_graph -q --basetemp=artifacts/test-results/V4-005/core-budget-fix-data --junitxml=artifacts/test-results/V4-005/core-budget-fix.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_graph.py -q --basetemp=artifacts/test-results/V4-005/core-scope-data --junitxml=artifacts/test-results/V4-005/core-scope.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_graph.py::test_model_cannot_hide_second_responsible_person_from_approved_source backend/tests/test_v4_graph.py::test_selected_scope_is_not_hidden_by_other_conversations_first_512_edges -q --basetemp=artifacts/test-results/V4-005/core-coverage-scope-data --junitxml=artifacts/test-results/V4-005/core-coverage-scope.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_graph.py::test_negative_conditional_name_boundaries_and_clipped_suffix_are_not_facts backend/tests/test_v4_graph.py::test_four_relationships_three_entities_and_two_hop_document backend/tests/test_v4_graph.py::test_conflicting_responsibility_retains_sources_and_blocks_paths backend/tests/test_v4_graph.py::test_model_cannot_hide_second_responsible_person_from_approved_source -q --basetemp=artifacts/test-results/V4-005/core-prefix-data --junitxml=artifacts/test-results/V4-005/core-prefix.xml
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_v4_graph.py::test_empty_model_result_cannot_consume_explicit_conflicting_source -q --basetemp=artifacts/test-results/V4-005/core-empty-conflict-data --junitxml=artifacts/test-results/V4-005/core-empty-conflict.xml
```

证据均在 Git 忽略的 `artifacts/test-results/V4-005/`。此模块没有真实模型质量或费用实测，复杂表达、人名消歧、跨来源身份归并、语义推理和大型图数据库均未覆盖。有限字符串名字查询与严格模板可使部分资料不产生实体或关系；非事实前缀有限规则也可能保守拒绝特殊姓名。空结果、冲突及 truncated 均按事实显示，不表示整个资料已经理解。
