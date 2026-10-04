import React from 'react';
import {synthesisMessageSchema,type ChatMessage,type SynthesisPreview} from '../main/chat-contracts';

export function SynthesisResult({message,show,compose,disabled=false}:{message:ChatMessage;show:(kind:'document'|'browser',id:string)=>void;compose:(message:ChatMessage)=>void;disabled?:boolean}){
  const parsed=synthesisMessageSchema.safeParse(message.data);
  if(!parsed.success)return <p role="alert">生成结果结构无效，请刷新会话核对。</p>;
  const result=parsed.data;
  return <section aria-label="模型综合回答" className="synthesis-result">
    <p className="source-content">{result.answer}</p>
    {result.coverage.some(item=>item.selected_chunks<item.available_chunks||item.source_truncated)&&<p className="muted">本回答仅依据选用内容，未覆盖文件全文。</p>}
    <ol>{result.claims.map((claim,index)=><li key={index}><strong>{{fact:'要点',inference:'推断',conflict:'来源冲突',unknown:'无法回答'}[claim.kind]}：</strong>{claim.text}
      {!!claim.citations.length&&<span> 引用：{claim.citations.map(cite=>{const target=result.citations.find(item=>item.citation===cite);return target?<button key={cite} disabled={disabled} onClick={()=>show(target.kind,target.evidence_id)} title={target.locator}>{result.coverage.find(source=>source.kind===target.kind&&source.evidence_id===target.evidence_id)?.title||'来源'} · {target.locator}</button>:<span key={cite}>引用暂不可用</span>;})}</span>}</li>)}</ol>
    <details><summary>查看来源详情</summary><ul>{result.coverage.map(item=><li key={item.kind+item.evidence_id}><button disabled={disabled} onClick={()=>show(item.kind,item.evidence_id)}>{item.title||item.evidence_id.slice(0,12)}</button> · {item.selected_chunks}/{item.available_chunks} 片段{item.source_truncated?' · 原文已截断':''}{item.missing_units.length?' · 有缺失单元':''}{item.ocr_available?' · 来源含 OCR，请核对识别':''}</li>)}</ul><small>固定 Main：{result.model}。引用仅校验身份和定位，结论仍需核对原文。</small></details>
    <button disabled={disabled} onClick={()=>compose(message)}>制作 Word／PPT／PDF 简报</button>
  </section>;
}

export function SynthesisPreviewCard({preview,disabled,confirm,close}:{preview:SynthesisPreview;disabled:boolean;confirm:()=>void;close:()=>void}){
  return <section className="source-detail synthesis-preview" aria-label="模型发送范围预览">
    <div className="row between"><h3>将使用以下文件内容回答你的问题</h3><button disabled={disabled} onClick={close}>关闭预览</button></div>
    <p>发送至 DeepSeek（deepseek-flash）；本次问题：{preview.question}</p>
    <p>将发送下列 {preview.fragments.length} 个片段。确认时还会显示原生确认框；可能产生费用。</p>
    <ul>{preview.coverage.map(item=><li key={item.kind+item.evidence_id}>{item.title||'来源'}{item.selected_chunks<item.available_chunks?'：本次仅选用部分内容':''}{item.source_truncated?'；文件内容未全部读取':''}{item.missing_units.length?'；部分内容未能读取，回答不包含这些内容':''}{item.ocr_selected?'；选用内容含图片识别文字，请核对原文':''}</li>)}</ul>
    {preview.fragments.map(item=><details key={item.citation}><summary>{preview.coverage.find(source=>source.kind===item.kind&&source.evidence_id===item.evidence_id)?.title||'来源'} · {item.locator}</summary><pre>{item.text}</pre></details>)}
    <p>确认后将发送以上内容用于回答，结论请结合原文核对。</p>
    <button className="primary" disabled={disabled} onClick={confirm}>确认发送并生成回答</button>
  </section>;
}
