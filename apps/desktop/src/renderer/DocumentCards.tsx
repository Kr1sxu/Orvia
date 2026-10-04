import React from 'react';
import {documentExportMessageSchema,documentMessageSchema,type DocumentEvidence,type DocumentPreview,type ChatMessage} from '../main/chat-contracts';

/** 附件中的指令、HTML 和链接仅作为不可信文本展示，不能触发导航或授权。 */
export function DocumentDetail({source}:{source:DocumentEvidence}) {
  return <div className="source-body"><strong>{source.title}</strong><p>{source.format} · {source.total_units} 页/段 · 读取时间 {source.accessed_at}</p>
    <p className="muted">证据 {source.evidence_id} · 文件版本 {source.file_hash}</p>
    {source.preview_truncated&&<p className="muted">以下为短摘录；请查看文档证据获取已保存正文。</p>}
    {source.truncated&&<p className="warning">内容已截断，不代表完整文档。</p>}
    {!!source.missing_units.length&&<p className="warning">缺失页/段：{source.missing_units.join('、')}</p>}
    {source.error&&<p className="warning">{source.error.message}（{source.error.code}）</p>}
    {source.units.map(unit=><details key={unit.number} open={source.units.length===1}><summary>{unit.locator} · {unit.method==='ocr'?'OCR 识别':'文本提取'}{unit.confidence!==null?' · OCR 置信度 '+Math.round(unit.confidence*100)+'%':''}</summary>
      <p className="muted">引用 {source.evidence_id.slice(0,12)} / {unit.locator}</p>{unit.error&&<p className="warning">{unit.error.message}（{unit.error.code}）</p>}<p className="source-content">{unit.text||'未提取到文字。'}</p>
    </details>)}
  </div>;
}
/** 只根据完整性元数据判断可用性；短预览不是读取失败，不能据此推断全文为空。 */
export function documentStatus(source:DocumentEvidence){
  if(source.error)return '无法回答';
  if(source.total_units===0||source.missing_units.length>=source.total_units)return '无法回答';
  return source.truncated||source.missing_units.length?'部分内容无法读取':'已准备回答';
}
export function documentFailure(code:string){
  if(code.includes('ocr'))return '图片中的文字暂时无法识别。请换用含可选中文字的文件，或提供相关文字。';
  if(code==='extraction_timeout')return '读取时间过长。请拆分文件后重试。';
  if(code==='input_size_limit')return '文件过大。请使用不超过 10 MiB 的文件。';
  if(code==='unsupported_format')return '暂不支持此格式。请使用 PDF、DOCX、PPTX、PNG 或 JPEG。';
  if(code==='worker_unavailable'||code==='worker_failed')return '本地文件读取服务不可用。请重启应用后重试。';
  return '未能读取文件内容。请检查文件是否损坏或受密码保护，或换用含可选中文字的文件。';
}
export function DocumentCard({message,disabled,show}:{message:ChatMessage;disabled:boolean;show:(id:string)=>void}) {
  const data=documentMessageSchema.parse(message.data);
  return <div className="source-card" aria-label="文档与引用">{data.error&&!data.items.some(item=>item.error?.code===data.error?.code)&&<p className="warning">{documentFailure(data.error.code)}</p>}{!data.items.length&&!data.error&&<p>没有找到相关内容，请换一个关键词或添加文件。</p>}
    {data.items.map((item,index)=><div key={item.evidence_id+':'+index}><strong>{item.title}</strong><p>{documentStatus(item)}</p>
      {documentStatus(item)==='无法回答'&&<p>{documentFailure(item.error?.code??'no_text')}</p>}
      <details><summary>查看来源详情</summary><DocumentDetail source={item}/><button disabled={disabled} onClick={()=>show(item.evidence_id)}>查看文档证据</button></details></div>)}
  </div>;
}
export function ExportPreview({preview,disabled,save}:{preview:DocumentPreview;disabled:boolean;save:()=>void}) {
  return <section className="source-detail" aria-label="文档导出预览"><h3>导出预览 · {preview.format.toUpperCase()}</h3><p>原文摘录引用覆盖：{preview.coverage.cited}/{preview.coverage.total}。此文件是保存的文档摘录，不是模型总结。</p>
    {preview.truncated&&<p className="warning">内容截断，导出不代表完整文档。</p>}{!!preview.missing_units.length&&<p className="warning">缺失页/段：{preview.missing_units.join('、')}</p>}
    <pre className="source-content" tabIndex={0}>{preview.content}</pre><p className="muted">请核对以上内容，再选择保存位置；已有文件不会覆盖。</p><button disabled={disabled} onClick={save}>选择路径并确认导出</button>
  </section>;
}

/** 导出卡片记录保存当时的核验事实；不把历史记录变成可重放的写授权。 */
export function ExportCard({message,disabled,show}:{message:ChatMessage;disabled:boolean;show:(id:string)=>void}) {
  const data=documentExportMessageSchema.parse(message.data);
  return <section className="source-card" aria-label="文档导出记录"><strong>{data.filename}</strong><p>{data.format.toUpperCase()} · 已核验新建文件 · 引用覆盖 {data.coverage.cited}/{data.coverage.total}</p>
    <p className="muted">导出 SHA256 {data.revision}</p>{data.truncated&&<p className="warning">原文有截断，导出不代表完整文档。</p>}{!!data.missing_units.length&&<p className="warning">缺失单元：{data.missing_units.join('、')}</p>}
    <button disabled={disabled} onClick={()=>show(data.evidence_id)}>查看导出引用</button><p className="muted">此记录不监控文件后续变化，也不授予再次写入权限。</p></section>;
}
