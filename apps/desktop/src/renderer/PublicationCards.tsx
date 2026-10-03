import React,{useState} from 'react';
import {publicationMessageSchema,synthesisMessageSchema,type ChatMessage,type Conversation,type PublicationPreview} from '../main/chat-contracts';
import type {Reply} from '../shared/api';

export function PublicationResult({message}:{message:ChatMessage}){
  const parsed=publicationMessageSchema.safeParse(message.data);
  if(!parsed.success)return <p role="alert">成品记录结构无效，请刷新会话核对。</p>;
  const value=parsed.data;
  return <section aria-label="成品核验结果"><strong>{value.format.toUpperCase()} 已创建并读回核验</strong><p>文件名：{value.filename} · {value.pages} {value.format==='pptx'?'张幻灯片':'页规划'}</p><small>版本 {value.revision.slice(0,12)}。保存位置仅在原生对话框中显示；不属于整理撤销。</small></section>;
}

export function PublicationComposer({cid,message,initialFormat,disabled,close,saved,notice}:{cid:string;message:ChatMessage;initialFormat?:'docx'|'pptx'|'pdf';disabled:boolean;close:()=>void;saved:(reply:Reply<Conversation>,id:string)=>void;notice:(text:string)=>void}){
  const parsed=synthesisMessageSchema.safeParse(message.data);
  const source=parsed.success?parsed.data:undefined;
  const [format,setFormat]=useState<'docx'|'pptx'|'pdf'>(initialFormat??'docx');
  const [title,setTitle]=useState('资料简报');
  const [answer,setAnswer]=useState(source?.answer??'');
  const [claimTexts,setClaimTexts]=useState(source?.claims.map(item=>item.text)??[]);
  const [preview,setPreview]=useState<PublicationPreview>();
  const [working,setWorking]=useState(false);
  if(!source)return <p role="alert">原回答已失效，无法制作成品。</p>;
  const input={id:cid,message_id:message.id,format,title,answer,claim_texts:claimTexts};
  const blocked=disabled||working;
  async function prepare(){
    setWorking(true);setPreview(undefined);
    try{const reply=await window.orvia.chatPublicationPreview(input);if(reply.ok)setPreview(reply.result);else notice(reply.message);}
    finally{setWorking(false);}
  }
  async function save(){
    if(!preview)return;
    setWorking(true);
    try{
      const reply=await window.orvia.chatPublicationSave({...input,revision:preview.revision,request_id:crypto.randomUUID()});
      setPreview(undefined);
      if(!reply.ok)notice(reply.message);
      else if(reply.result.cancelled)notice('已取消保存，未创建文件；如需保存请重新预览。');
      else if(reply.result.conversation)saved({ok:true,result:reply.result.conversation},cid);
    }finally{setWorking(false);}
  }
  return <section className="source-detail publication-composer" aria-label="简报成品制作">
    <div className="row between"><h3>制作带引用的简报</h3><button disabled={blocked} onClick={close}>关闭</button></div>
    <p>基于这条已保存的 M15 回答。可编辑标题、摘要和结论文字；结论类型与引用沿用原结果。修改事实后请逐条回查来源。</p>
    <label>成品格式<select aria-label="成品格式" disabled={blocked} value={format} onChange={e=>{setFormat(e.target.value as typeof format);setPreview(undefined);}}><option value="docx">Word 报告</option><option value="pptx">PPT 演示</option><option value="pdf">PDF 报告</option></select></label>
    <label>标题<input aria-label="简报标题" maxLength={40} disabled={blocked} value={title} onChange={e=>{setTitle(e.target.value);setPreview(undefined);}}/></label>
    <label>摘要正文<textarea aria-label="简报摘要正文" maxLength={2200} disabled={blocked} value={answer} onChange={e=>{setAnswer(e.target.value);setPreview(undefined);}}/></label>
    {claimTexts.map((value,index)=><label key={index}>结论 {index+1} · {source.claims[index].kind}<textarea aria-label={`结论 ${index+1} 正文`} maxLength={600} disabled={blocked} value={value} onChange={e=>{setClaimTexts(items=>items.map((item,i)=>i===index?e.target.value:item));setPreview(undefined);}}/></label>)}
    <button disabled={blocked||!title.trim()||!answer.trim()||claimTexts.some(value=>!value.trim())} onClick={()=>void prepare()}>预览内容与版面</button>
    {preview&&<section aria-label="简报版式预览" className="publication-preview"><h4>{preview.title} · {preview.format.toUpperCase()} · {preview.pages.length} {preview.format==='pptx'?'张幻灯片':'页规划'}</h4><p>{preview.notice}</p>
      {preview.pages.map((page,index)=><article key={index} className="publication-page"><small>{preview.format==='pptx'?'幻灯片':'页面'} {index+1}</small><h5>{page.heading}</h5><p className="source-content">{page.body||page.references?.map(ref=>`[${ref.number}] ${ref.title} · ${ref.locator}\n${ref.citation}`).join('\n')}</p><small>{page.label} {page.numbers.map(n=>`[${n}]`).join(' ')}</small></article>)}
      <p>Word 的最终分页会随本机字体和编辑器变化；PPT 与 PDF 按上述页面安排。PDF 中文字体内嵌。没有素材上传或新模型请求。</p>
      <button className="primary" disabled={blocked} onClick={()=>void save()}>选择新文件路径并确认保存</button>
    </section>}
  </section>;
}
