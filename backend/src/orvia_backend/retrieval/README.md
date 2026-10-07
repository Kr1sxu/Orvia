# V4-004 本地向量与混合检索

`RetrievalService` 为已存 SQLite 原文片段建立固定版本本地向量，按准确 Mission/来源范围执行 FTS5 与余弦相似度召回，再用 RRF 融合。模块不扫描目录、读取原文件、下载权重、访问网络或调用三个角色的云模型。模型准备与运行由主进程配置的私有 `embedder` 提供，不在此模块导入重量级运行依赖。

## 结构、依赖与契约

`service.py` 包含 SQLite 迁移、范围校验、模型签名核对、float32 编码、原子重建、有限候选排序与原文结果。`__init__.py` 导出 `RetrievalService`、`RetrievalError`。检索服务本身使用已有 Python 3.12、aiosqlite、jieba/FTS5 及标准库；真实运行器新增可选embeddings依赖（固定版本见下文），延迟导入，不影响缺模型的原有关键词能力。

固定签名是 `Qwen/Qwen3-Embedding-0.6B@97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3:1024:qwen-lasttoken-v1`。工件 revision、1024维、`qwen-lasttoken-v1` 预处理版本均分别入库，任何一项变化不能解释旧索引。向量按 little-endian float32 存为4096字节 BLOB；输入须有限非零数值、拒绝 bool 等伪数值，单位化后存储。读取逐条复核字节长度、有限值与单位范数误差≤`1e-4`。

运行时接口：固定 `signature: str`、同步 `status()->{ready,reason,signature}`、异步 `embed(texts:list[str],query:bool=False)->list[list[float]]`。`query=True` 使用查询预处理；模型工件的首次下载仍须单独原生确认，缺模型不自动下载或换用其它模型。

## 公共接口与输入输出

- `RetrievalService(store, embedder)`，`await open()`：在已打开 Store 上以事务新增 `retrieval_vectors` 与 `retrieval_epochs`，不改变既有数据库 `user_version`。
- `await status(mission_id=None)`：报告运行时可用原因、固定工件/预处理/维度、该 Mission 或全库向量记录数量与预算。向量行数是存储事实，不代表所有原文已覆盖；实际搜索仍逐条核验版本和内容。
- `await rebuild(mission_id, sources=None)`：只对已存在原文建立索引，返回 `{mission_id,status,reason,indexed_chunks,unique_texts,signature}`。只有完整事务提交才返回 `completed`；缺模型和预算超限明确 `keyword_only` 或 `failed`，不把降级称为向量完成。
- `await search(mission_id, query, limit=5, sources=None)`：返回 `{mission_id,query,status,reason,evidence,coverage}`。`status` 为 `hybrid` 或 `keyword_only`；每条 evidence 含准确 `text/source/chunk_index/chunk_id/content_hash/model_revision/channels/score`，另含有界 `supporting_sources/provenance_count/provenance_truncated`。
- `await clear(mission_id, sources=None)`：仅清理派生向量，返回 `{mission_id,removed_vectors}`；保留原文/FTS、原文件与成品。同事务推进 epoch，阻止较早的锁外重建在清理后重新写回。

`sources` 是准确来源标签列表。`None` 表示该 Mission 现存来源全集，也受来源数量上限约束；`[]` 明确为空范围，搜索无正文、重建无模型调用、清理无动作，绝不变成 `None`。标签不是文件权限或外发授权。调用侧必须从当前有效资料构造准确标签，并在异步查询后复核业务关联版本；已解除关联但为历史保留的原文不能通过传 `None` 重新纳入普通资料回答。

## 范围与资源预算

保留已有最多3个附件、单附件50个单元的行为，技术范围调整为最多150个准确来源标签，每个标签≤1000字符、标签合计≤48KiB。该调整用于兼容原有资料数量，不新增附件或读取范围。SQL 在候选阶段同时限定片段 Mission、文档 Mission 和准确 source，禁止向量全库结果回传后才做隔离。

每任务向量最多512段，全库最多4096段；每段原文≤600字符，query≤200字符，limit为1～20。嵌入每批最多8段（运行时可采用更小批次），每批30秒、重建全过程120秒，包含排队与数据库核验；向量每次从 SQLite 读取最多128条。两通道总计最多512个不同片段候选，关键词优先保留，避免两通道各512使总候选扩为1024。

FTS5 使用 jieba 词项，最多32个去重查询词，各项加引号，以 OR 召回，调用方不能提供自由 MATCH 表达式。余弦计算只使用验证通过的固定版本单位向量；RRF 常数60，同一正文 hash 在每通道只占一个排名位，分数为各通道 `1/(60+rank)` 之和。向量相似度不是事实真实性判定。

相同正文只嵌入一次，SQLite 仍为每个片段保存 FK 和来源，不因去重丢失原文定位。结果保留代表片段和最多8个来源定位；超过8项明确 `provenance_truncated`，全部关系仍在原文表与向量 FK 中。返回 JSON 正文控制在32KiB，包含结果来源与定位；不足预算时减少结果并标明 `coverage.output_limited`。覆盖字段报告实际候选数量、可用向量数量及准确范围来源数量，不承诺全文覆盖。

## 并发、权限和失败

重建先在 SQLite 锁内取来源/片段/文档 hash 快照，锁外调用本地模型；提交事务再次核对完整快照与 epoch。替换、删除、新增片段、来源版本变化、会话删除、清理索引、模型签名改变均使旧结果不能写回。失败不提交部分新向量，既有合法索引保持原状态；删除原文通过 `context_chunks` 的 FK 自动级联删除向量；会话purge同时清除epoch，仅留既有随机ID删除标记。

查询先检查是否存在有效当前索引，没有索引、版本错误或模型缺失时直接关键词降级，零查询嵌入。查询嵌入返回后再次读取当前候选和 epoch；变化即使用当前关键词结果并注明原因。聊天删除日志存在时阻止删除身份继续查询或晚到重建。重启只复用持久化向量和原文；不会获取模型、扩大范围或恢复文件授权。

检索不能批准摘要、改写、关系抽取、资料上云或文件访问。精确引用继续回查不可变原文及定位，不用向量、摘要或相似度代替证据。

## 开发试用与验证

### 固定模型与离线运行器

`model.py`记录官方模型、修订和六个文件的大小/摘要；`runtime.py`负责普通路径与工件核验、原生确认后的固定下载、独立进程资源监测与关闭；`worker.py`使用官方query指令、左侧padding、last-token pooling和L2归一化。`integration.py`从当前会话有效资料生成精确定位，异步完成后复核关联；`RetrievalPanel.tsx`提供设置中的实际入口。模型不负责生成回答或授予权限。

开发环境可运行 `C:/Users/18532/.local/bin/uv.exe sync --directory backend --extra embeddings --group dev`。可选embeddings依赖锁定Transformers4.57.6、Safetensors0.7.0及官方CPU PyTorch2.8.0+cpu的Python3.12 Windows x64 wheel；无CUDA/GPU依赖。依赖未安装时工作器明确不可用，现有关键词检索保留。此wheel仅支持当前Windows x64环境，未验收其它系统或发布运行时。

首次下载由桌面原生确认展示准确模型清单；原生取消零下载。也可原生选择已有目录，必须恰好六个普通文件、逐个官方大小和内容摘要相符，拒绝额外配置/脚本、网络目录、链接和联接。固定模型`Qwen/Qwen3-Embedding-0.6B`，修订`97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`，Apache-2.0；[官方来源](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/tree/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3)。模型总1207469240字节；大文件SHA256与小文件Git blob SHA1均来自官方仓库元数据，完整清单由`retrieval.model`与原生确认展示。

`LocalEmbedder(data_directory)`：`status()`返回就绪/稳定原因/固定signature和资源事实；`await prepare(path)`核验、离线预加载并保存应用私有路径配置；`await restore()`重新核验此前目录，失败不联网补文件；`await embed(texts,query=False)`最多8段、每段600码点，内部每批4段，查询指令与文档裸文本分开；`await download()`仅由可信主进程原生确认后调用，固定HTTPS来源/摘要，900秒限时并清理本次普通临时文件，不覆盖已有模型；`await close()`终止自有工作器。

独立CPU进程4线程、float32、1024 tokens，拒绝静默截断；每请求30秒，准备总180秒包含排队、核验和加载，各阶段还有限期限。每0.1秒监测启动器及已识别自有子进程的合计RSS（最多4个子进程），超过6GiB终止并回收工作器树，属于监测阈值，不能承诺OS硬限制或零瞬时越界。超时、取消、断线和失败不自动重试，晚到结果不能用于新请求。子进程不继承Key/代理，HF强制离线、local_files_only、trust_remote_code=False、safetensors；启动应用不加载模型，用户点击加载此前模型后才核验并准备。模型、路径配置、SQLite和报告不入Git或本轮安装包。

设置→本地混合检索→确认下载/选择已有模型/加载此前模型→选资料所属会话→建立当前资料索引→检索关联资料。清除当前会话向量清除该会话全部派生向量（含历史定位），保留FTS/原文/原文件。资料回答使用相同分块和精确单元定位，完整发送范围预览、原生确认和严格引用验证仍保留。

真实本地验收脚本为`backend/tests/live_v4_embedding.py`，必须显式设置`ORVIA_EMBEDDING_MODEL_PATH`后执行项目Python；脚本不下载、不读Key，只用固定16主题/8问题合成集。分别报告相同FTS5 OR通道的keyword、vector和hybrid Recall@5/MRR@5、时间、RSS、SQLite大小，含去重/来源删除/重启/隔离核验。2026-10-07首次下载已获用户批准，六个固定官方文件逐个核验后真实运行通过；不需要重复下载。下载沿用现有HTTPS证书/代理配置且始终校验证书，推理工作器保持离线。

在开发版设置准备并核验本地模型，然后选择当前会话有效资料建立索引，在相同资料范围提问。缺模型仍可用原有关键词路径，并明确显示降级原因。模型下载、资源实测、IPC及桌面试用的实际结果见PROGRESS；本机开发版已经实际验收，模型工件位于项目私有`.orvia/models/qwen3-embedding-0.6b/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`。按用户最新要求完成004后暂停，不实施003。

L0：`backend/.venv/Scripts/python.exe -m compileall -q backend/src/orvia_backend/retrieval`。

L1/L2 初轮：`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_v4_retrieval.py -q --basetemp=artifacts/test-results/V4-004/retrieval-tmp --junitxml=artifacts/test-results/V4-004/retrieval-junit.xml`。

新增或变更边界只重跑最小相关集合，命令与结果分别保存在 `retrieval-audit-junit.xml`、`retrieval-boundary-junit.xml`、`retrieval-scope-junit.xml`、`retrieval-query-junit.xml`，由 PROGRESS 记录实际命令并按 test ID 去重统计。

测试使用真实临时 SQLite、FTS5 和合成正文；嵌入是明确的合成 fixture，语义同义词映射测试仅验证融合通路，不能证明 Qwen 的真实召回提升。覆盖固定维度/finite/norm/BLOB、模型与预处理隔离、重复正文来源保留、Mission/来源隔离、150单元既有预算、512/4096上限、FK删除、替换/删除/新增/清理/会话删除/版本变更并发、超时取消、重启一致性、空资料与 Unicode。上述合成fixture与实际Qwen结果分开记录，不将模拟向量当真实效果。实际模型固定16主题/8问题、17片段16种正文，关键词/向量/混合Recall@5均1.0，MRR@5分别0.7542/1.0/0.9167，平均查询约0.002/0.510/0.510秒；单次小样本无置信区间或普遍收益结论。建立索引3.156秒，工作器树峰值3720794112字节；最终SQLite196608字节包含所有事实/FTS表，向量有效负载65536字节，两者不可混称索引大小。真实8×600码点满批14.109秒/峰值3807604736字节；601码点拒绝、1201tokens在0.141秒拒绝并关闭工作器。6GiB为RSS监测阈值，不是OS硬限制，未跑全库4096段持续负载。

本模块是有限 SQLite 精确余弦检索，不提供 ANN 服务、自动全盘索引、自动模型替换或无限历史检索。候选上限、低质量原文、未索引片段、来源截断或局部匹配会影响覆盖；结果必须结合准确证据范围解释。

真实验收仅用合成资料，无云模型/费用；必要时显式设置已批准目录 `ORVIA_EMBEDDING_MODEL_PATH`，运行 `backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_v4_embedding.py`。`live_v4_prepare.py`为本次已批准固定下载/核验脚本，不属于默认测试；`live_v4_resources.py`为实际8段满批/码点/token预算检查，`--token-only`只复验token阶段。本次复用第一次满批及字符检查通过证据，再修正emoji错误token假设后最小复验token阶段，不重复满批。精确命令、失败历史、结果和硬件见PROGRESS，证据仅保存在忽略的artifacts/test-results/V4-004/。

102个不同后端用例、2个前端契约及关键词/真实模型共2个Electron流程已通过。Electron的原生选择/确认由测试模拟，不能替代人工审批验收；截图已实际查看。尚未验证GPU、其它系统、独立Windows、发布运行时或新安装包；CPU可选wheel限定Python3.12 Windows x64，旧安装包不含本模块。
