# M16 本地简报成品

## 用途与范围

从当前会话一条已保存的 M15 结构化回答制作 Word 报告、PowerPoint 演示或 PDF 报告。首批场景是带来源引用的短简报：用户可编辑标题、摘要及每条结论文字；结论类型、引用身份、来源定位始终取自原回答。M16 本身不调用模型、不重新读取附件，也不发送正文到云端。完整行业调研、标书、任意模板、宏、图片、图表和公式不在本模块首批范围。

## 结构、输入输出与公共接口

- `service.py`：`prepare_publication(message, request)` 将已保存 M15 消息映射成有 revision 的纯文本页面计划；`render_publication(packet)` 生成实际 DOCX/PPTX/PDF 字节并做结构读回。
- `assets/NotoSansSC.ttf` 与 `OFL.txt`：PDF 离线嵌入的简体中文字体及原许可；字体 SHA256 `A3041811A78C361B1DE50F953C805E0244951C21C5BD412F7232EF0D899AF0DA`。
- `chat.publication.preview({id,message_id,format,title,answer,claim_texts})`：会话归属复核后读取一条 M15 结果，返回页面/幻灯片内容、完整引用列表、来源 revision 与成品 revision。最多 40 字标题、2200 字摘要、8 条各 600 字结论。
- `chat.publication.save({...preview_args,revision,request_id,path})`：仅主进程原生保存框可提供绝对路径；再次计算预览并匹配 revision，按 format 生成后通过 M13 Computer gateway 独占新建、fsync、句柄身份与读回字节核验。重复请求标识不重复写入，保存事件只记文件名/版本/格式/页规划数，不保存绝对路径。

页面计划由短段落和完整引用附录组成。PPT 每个计划页为一张幻灯片；PDF 每个计划页为 A4 页，使用 Noto Sans SC 并在溢出时拒绝生成；Word 有编辑器字体替换和自动分页，预览展示内容/分段计划而非保证逐像素一致。正文使用纯文本，引用编号映射到原证据 ID、标题与页/段/网页定位；用户编辑后的事实仍需手工复核，程序不做语义验证。

DOCX/PPTX 由 `python-docx` 1.2.0 / `python-pptx` 1.0.2 生成并读回，PDF 由 ReportLab 4.5.1 排版、pypdfium2 读回及渲染。依赖固定于 `backend/uv.lock`；本地离线可用，不依赖已安装的商业 Office 或在线字体服务。前两者库的包元数据为 MIT，ReportLab 为 BSD 类许可；字体原文件随 OFL 1.1 许可一同分发。发布冻结规格需收集 `publication/assets`；M14 已有未签名安装包尚不包含 M15/M16 源码。

## 权限边界与运行

renderer 只有固定预览/保存 API，不可传路径、模板、素材、模型、供应商或改写引用。主进程记录最近一次后端预览输入及 revision；保存前重新取预览并经原生保存框确认，取消不写入。后端继续复核消息归属与版本，Computer gateway 拒绝不安全父目录、已有目标和扩展名不符，最多写 2 MiB。文件保存不属于 M04 整理撤销；中断写入可能留下部分新文件，用户需核对后另选名称。外部文档、网页和模型文本永远只是内容，不能授权、执行宏或触发本地/网络动作。

根目录运行 `.venv/Scripts/uv.exe sync --project backend --locked`、`npm run build`、`npm start`。在已生成的 M15 回答卡片点“制作 Word／PPT／PDF 简报”，选择格式，编辑文字，预览页面和引用，选择新文件路径确认保存。字体未安装时 Word/PPT 可由目标软件替换字形；PDF 自带字体。复杂布局、图像、表格跨页、已有模板、实时内容编辑预览和 Word 精确分页未实现。页面计划不是 Office 实际渲染截图。

## 测试

`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_m16_publication.py -q --basetemp=artifacts/test-results/M16/backend-temp --junitxml=artifacts/test-results/M16/backend.xml`：真实 DOCX/PPTX/PDF 生成、重开、PDF 渲染、SQLite/版本/会话/新建写入；M15 模型使用 mock。

`npx vitest run apps/desktop/tests/m16-contracts.test.ts apps/desktop/tests/m15-contracts.test.ts`：固定 IPC 契约与纯文本卡片。`ORVIA_TEST_MODULE=M16`、`ORVIA_TEST_RESULTS=artifacts/test-results/M16` 下运行 `npx playwright test tests/e2e/m16.spec.ts`：真实 Electron/Python/保存网关，模型及系统对话框由测试启动器 mock。逐页 PDF/PowerPoint 本机渲染检查与冻结构建结果见 `docs/PROGRESS.md`；所有临时文件位于 Git 忽略的 M16 产物目录。

按需显式运行 `backend/.venv/Scripts/python.exe -X utf8 backend/tests/live_m16_publication.py --run-live`：仅本进程读取开发 Main Key，一次真实 `deepseek-flash` 请求使用两条短合成来源；随后在本地用该已保存结果生成并读回三格式。HTTP 超时20秒、总等待30秒、最多1024输出token、零自动重试；只报告计数、状态和供应商 token 用量，不打印原始请求/响应或凭据。常规测试不触发此脚本的真实调用。
