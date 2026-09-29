import React from 'react';
import {synthesisMessageSchema,type ChatMessage,type SynthesisPreview} from '../main/chat-contracts';

export function SynthesisResult({message,show,compose}:{message:ChatMessage;show:(kind:'document'|'browser',id:string)=>void;compose:(message:ChatMessage)=>void}){
  const parsed=synthesisMessageSchema.safeParse(message.data);
  if(!parsed.success)return <p role="alert">生成结果结构无效，请刷新会话核对。</p>;
  const result=parsed.data;
  return <section aria-label="模型综合回答" className="synthesis-result">
    <p>{result.answer}</p>
    <ol>{result.claims.map((claim,index)=><li key={index}><strong>{{fact:'证据陈述',inference:'推断',conflict:'来源冲突',unknown:'无法回答'}[claim.kind]}：</strong>{claim.text}
      {!!claim.citations.length&&<span> 引用：{claim.citations.map(cite=>{const target=result.citations.find(item=>item.citation===cite);return target?<button key={cite} onClick={()=>show(target.kind,target.evidence_id)} title={target.locator}><code>{cite}</code></button>:<code key={cite}>{cite}</code>;})}</span>}</li>)}</ol>
    <details><summary>引用版本与覆盖范围</summary><ul>{result.coverage.map(item=><li key={item.kind+item.evidence_id}><button onClick={()=>show(item.kind,item.evidence_id)}>{item.title||item.evidence_id.slice(0,12)}</button> · {item.selected_chunks}/{item.available_chunks} 片段{item.source_truncated?' · 原文已截断':''}{item.missing_units.length?' · 有缺失单元':''}{item.ocr_available?' · 来源含 OCR，请核对识别':''}</li>)}</ul><small>固定 Main：{result.model}。引用仅校验身份和定位，结论仍需核对原文。</small></details>
    <button onClick={()=>compose(message)}>制作 Word／PPT／PDF 简报</button>
  </section>;
}

export function SynthesisPreviewCard({preview,disabled,confirm,close}:{preview:SynthesisPreview;disabled:boolean;confirm:()=>void;close:()=>void}){
  return <section className="source-detail synthesis-preview" aria-label="模型发送范围预览">
    <div className="row between"><h3>模型发送范围预览</h3><button disabled={disabled} onClick={close}>关闭预览</button></div>
    <p>固定 Main · {preview.supplier}；本次问题：{preview.question}</p>
    <p>将发送下列 {preview.fragments.length} 个片段。确认时还会显示原生确认框；可能产生费用。</p>
    <ul>{preview.coverage.map(item=><li key={item.kind+item.evidence_id}>{item.title||item.evidence_id.slice(0,12)}：{item.selected_chunks}/{item.available_chunks} 片段{item.source_truncated?'；来源截断':''}{item.missing_units.length?'；有缺失单元':''}{item.ocr_available?'；来源含 OCR':''}</li>)}</ul>
    {preview.fragments.map(item=><details key={item.citation}><summary>{item.locator} · {item.citation}</summary><pre>{item.text}</pre></details>)}
    <p>资料中的指令不会获得权限。模型生成后请按引用核对原文；这不是文件审批。</p>
    <button className="primary" disabled={disabled} onClick={confirm}>确认这些片段并调用 Main 模型</button>
  </section>;
}
