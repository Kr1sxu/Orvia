# M13 文档内容、引用与受限导出

本模块处理用户在当前对话显式选择的单个附件，提供本地原文提取、关键词检索、版本引用及 Markdown/JSON 导出。不调用云模型，不上传文件，不生成总结、Office/PDF 成品或标书。

## 结构与依赖

- `parser.py`：PDF 文本与扫描页、PNG/JPEG 本地 OCR、DOCX 段落、PPTX 幻灯片文本提取。
- `worker.py`：固定子进程入口，只接收有界 stdin 字节；不接收文件路径或脚本，不继承凭据环境。
- `service.py`：复用 M12 `EvidenceStore.save_version/get/list` 的不可变版本与会话隔离；复用 M06 `ContextService` 的分块/FTS5；生成带引用的导出预览。
- Computer gateway 负责单文件读取/独占创建，复用 `PathPolicy`；ChatService/Application 负责请求幂等、会话事件和分级错误，Electron main 负责原生选择器与预览身份。

Python 3.12，锁定 pypdfium2 4.30.0、rapidocr-onnxruntime 1.4.4、defusedxml 0.7.1、Pillow 11.3.0，传递依赖见 `backend/uv.lock`。RapidOCR 的中文/英文 ONNX 权重来自安装 wheel，运行不下载模型。这里的 OCR 是本地识别器，不是 Main/Computer/Browser 三个固定云模型。

## 输入、预算与生命周期

| 项目 | 边界 |
|---|---|
| 输入 | `.pdf/.docx/.pptx/.png/.jpg/.jpeg`，每次一个普通本地文件，最多10 MiB |
| 提取 | 最多50个页/幻灯片/段落，合计8000个 Unicode 码点，序列化解析输出最多44 KiB |
| Office 容器 | 最多4096项、解压后合计32 MiB；不落盘解压；拒绝宏、加密、外部关系、实体和路径穿越 |
| 图像 | 最多1600万像素，最长边缩至2400；PDF扫描页最多2倍渲染、最长边2400 |
| 时间 | 父进程45秒硬超时后 kill/wait；worker自身45秒上限与父进程存活监测 |
| 会话 | 与已有文件/网页请求共享100次预算；附件目录最多20版本/8 KiB，整体快照46 KiB |
| 导出 | 一个已保存文档版本；Markdown/JSON预览序列化正文最多48 KiB，超过明确拒绝 |

原文件始终只读，没有附件副本、解压目录或原始图像临时文件。字节/位图随解析子进程退出释放；有界提取文字、文件与内容哈希、引用、失败和时间保存在本地 app.sqlite 与 FTS，随会话跨重启保留。本轮没有自动清理历史/附件删除入口，也不自动重读原路径。

扫描页只有无文本层时才尝试 OCR，普通文本 `confidence=null`；OCR 显示0–1识别器平均分的百分比，不是事实正确率。`missing_units` 仅枚举前50单元内缺失/空内容，尾部省略由 `total_units` 与 `truncated` 表示。DOCX 采用段落序号（包含表格段落），不宣称实际页码。PPTX 按 presentation 中的实际顺序记录幻灯片号。

## 公共接口与证据

由既有私有 stdio 进入 `chat.document.*`，没有新监听端口。所有方法先验证会话归属与 strict 参数，renderer 的固定接口没有 path 字段。

- `attach({id,request_id,path})`：path仅来自主进程选择器，一次性只读该文件，返回会话快照。不会建立或扩大目录 grant。
- `source({id,evidence_id})`：获取该会话的一个完整有界文档版本。
- `ask({id,request_id,query})`：最多200字的本地关键词检索，最多5个带单元引用的原文命中；不做生成式问答。
- `preview({id,evidence_id,format})`：返回内容、SHA256 revision、引用覆盖、缺失与截断。覆盖表示已导出非空单元都有证据引用，不代表全文无缺失或内容已核实。
- `export({id,request_id,evidence_id,format,revision,path})`：主进程必须匹配最近成功预览并消耗一次性确认，随后原生保存框提供新路径；后端重算预览版本，经网关 `x+b` 独占创建、flush/fsync、句柄/路径身份及读回字节核验。既有文件绝不覆盖；此新建导出不属于 M04 整理账本，不能用“撤销最近整理”删除。

证据包括 `evidence_id/file_hash/content_hash/title/format/accessed_at/total_units/units/missing_units/truncated/error`。单元包含 `number/locator/text/method/confidence/error`，引用为版本ID和单元号。相同字节、标题及提取结果去重且保留首次时间；任一变化生成独立版本。M12网页和M13文档使用同一版本存储机制但分表/索引前缀，查询与详情都复核会话，不能混成网页正文。

正文、标题、OCR结果、外部链接均为不可信数据；不进入 Main 文件规划历史，不得授予权限、触发审批、读取其他文件或联网。UI只作纯文本，Markdown外部内容用动态代码围栏封装，避免导出文本成为可执行 HTML/远程图片。DOCX/PPTX中的外部关系直接拒绝而非联网跟随。

请求先落 pending，完成再落终态；重启将未完请求标为 interrupted，不重放读取或导出。证据与 FTS 分别提交；失败可能留下可查看版本但未完成索引，用户显式重选同一附件可以重建索引。导出写入中断可能留下新建的部分文件，重试同路径仍拒绝覆盖，需要先人工核对并选择新名称。

## 运行、示例与验证

根目录先运行 `.venv/Scripts/uv.exe sync --project backend --locked`、`npm run build`，再 `npm start`。点击“＋ 添加附件”选人工构造 DOCX/扫描 PDF → 展开文档卡片 → 查看文档证据 → 输入区“询问文档”输入关键词 → 查看引用 → “预览 Markdown 导出”或 JSON → 核对覆盖/缺失/截断 → “选择路径并确认导出”。取消不写入，再次导出需重新预览。

测试仅使用人工合成内容：

```powershell
backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m13_parser.py backend/tests/test_m13_documents.py -q --basetemp=artifacts/test-results/M13/temp --junitxml=artifacts/test-results/M13/backend.xml
npx vitest run apps/desktop/tests/m13-contracts.test.ts tests/integration/m13.test.ts
$env:ORVIA_TEST_MODULE='M13'
$env:ORVIA_TEST_RESULTS='artifacts/test-results/M13'
npx playwright test tests/e2e/m13.spec.ts
```

精确已执行命令、定向重跑与结果见根 PROGRESS；真实OCR、Python、SQLite、Electron与原生选择器mock分开记录。报告/截图/合成文档只在忽略的 `artifacts/test-results/M13/`。

## 限制

不支持旧 `.doc/.ppt`、加密/宏/含外部关系的Office文档、复杂表格结构、公式语义、图片理解、布局重建或混合页中图片区域的额外OCR。OCR质量和阅读顺序需用户复核；50单元/8000字仅为受限提取。M06检索为任务内AND关键词、候选前20条再筛选文档，可能漏掉结果，无语义检索或分页。单文档导出不合并网页、多个附件或生成式结论；导出Office/PDF为计划可选项，本轮不实现。

程序不是OS级沙箱，路径检查不能消除外部进程竞态；本轮没有新增任意脚本、系统操作或浏览器写入能力。M08历史安装器不包含本模块，新增解析/OCR依赖的冻结收集及独立Windows安装验收留到M14，本轮只验证开发版。
