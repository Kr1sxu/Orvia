# M13 文档内容、引用与受限导出

M20通过统一“＋”主进程原生入口一次最多选择3文件、每个10MiB/合计30MiB，逐个调用本模块既有单文件解析接口；单文件权限没有扩大为父目录或递归读取。当前有效关联和解析/失败/移除状态由`chat/`维护，移除只解绑、历史不可变证据和引用保留。先发总结需求再添加资料时同一自然请求接续，正文仍须M15确切片段和原生上云确认；取消/切会话/重启/断线不自动接续。实际开发/安装解析、OCR与Markdown/JSON原文导出对照见[PROGRESS](../../../../docs/PROGRESS.md)，公共自然接口见[对话README](../chat/README.md)。

M15 在此模块之外复用已保存的文档不可变版本、单元定位和 M06 索引；只有用户另行选择证据、预览片段并确认后，选中的提取正文才会发往固定 Main 云模型。M13 附件选择与本地解析本身仍无上传授权。生成流程、预算与引用核验见 `../chat/README.md`。

M16 另在 `../publication/README.md` 规定：仅从当前会话已保存的 M15 回答制作固定模板 DOCX/PPTX/PDF 简报；本模块的 Markdown/JSON 原文导出接口、上传边界和单附件读取权限不变。

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

## M14 本机打包验证

最新未签名候选版为0.2.0-rc.1，包含对话及文档能力；上文“安装包未重建”描述保留为历史模块状态。PDF/OCR冻结资源、安装包流程、升级/卸载的命令与边界见根目录 packaging/README.md、docs/PROGRESS.md。测试产物统一为 artifacts/test-results/M14/。真实本地组件测试不等于云模型/Tavily验证；生产签名和独立Windows验收经用户确认暂缓。

## V3-005 可读状态
输入输出结构与受限解析预算不变；本地OCR导入依赖缺失返回固定 ocr_unavailable，不泄露模块路径。UI据此建议换用含可选中文字的文件；其它worker故障仍提示重启，不猜测OCR故障原因。图片/PDF/DOCX/PPTX共享展示规则，不扩展解析能力或自动安装依赖。完整证据、原始错误码与OCR置信度仍可在来源详情核对。目标验证：test_v3_document_presentation.py、test_m13_parser.py、test_m13_documents.py；结果在 artifacts/test-results/V3-005。
