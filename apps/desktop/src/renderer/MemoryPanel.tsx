import React,{useEffect,useState} from 'react';
import type {MemoryCandidate,MemoryContext,MemoryList,MemoryPreview,MemoryRecord} from '../main/memory-contracts';

const statusLabel:Record<string,string>={completed:'已结束',failed:'失败',cancelled:'已取消',interrupted:'已中断',pending:'等待处理',running:'处理中',waiting_approval:'待审批',waiting_input:'等待必要信息',awaiting_approval:'待审批',completed_without_pair:'记录未形成完整交互',candidate:'候选，尚未批准整理',verified:'有原文支持',conflict:'来源冲突，未用于事实检索',revoked:'支持已撤回，未用于上下文'};
const kindLabel={preference:'偏好',person:'人物',project:'项目'};
function Sources({item}:{item:MemoryCandidate|MemoryRecord}){return <details><summary>精确来源详情</summary><p>来自会话 {item.conversation_id}</p>{item.sources.map(source=><div key={source.source_id}><p>{source.quote}</p><small>{source.status==='user_statement'?'用户原文':source.status==='source_excerpt'?'关联资料摘录':'会话原文'} · {source.source_id}</small></div>)}</details>;}

/** 自动发现仅在本地发生；原生批准前展示准确正文，跨会话检索不会自动授予外发许可。 */
export function MemoryPanel(){
  const [chats,setChats]=useState<{id:string;title:string}[]>([]),[cid,setCid]=useState('');
  const [state,setState]=useState<MemoryList>(),[context,setContext]=useState<MemoryContext>(),[preview,setPreview]=useState<MemoryPreview>();
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[query,setQuery]=useState(''),[hits,setHits]=useState<MemoryRecord[]>(),[edits,setEdits]=useState<Record<string,string>>({});
  async function load(id:string){
    const listing=await window.orvia.memoryList({id});if(listing.ok)setState(listing.result);else setNotice(listing.message);
    const recent=await window.orvia.memoryContext({id});if(recent.ok)setContext(recent.result);else setNotice(recent.message);
  }
  useEffect(()=>{let live=true;void window.orvia.chatList().then(r=>{if(live&&r.ok){setChats(r.result.conversations);setCid(r.result.conversations[0]?.id??'');}}).catch(()=>{if(live)setNotice('会话列表暂不可用。');});return()=>{live=false;};},[]);
  useEffect(()=>{setState(undefined);setContext(undefined);setPreview(undefined);setEdits({});if(cid)void load(cid).catch(()=>setNotice('本地记忆读取未完成，请检查连接。'));},[cid]);
  async function act(action:()=>Promise<void>){setBusy(true);try{await action();}catch{setNotice('操作未完成或结果未知，请检查连接与现有记录；不会自动重试云请求。');setPreview(undefined);}finally{setBusy(false);}}
  return <section aria-label="会话上下文与长期记忆" className="skills-panel"><h3>会话上下文与长期记忆</h3>
    <p>本地发现偏好、人物和项目候选。摘要与记忆整理需逐批查看完整内容并原生批准；已有记忆不会授予文件、执行或外发权限。</p>
    <label>记忆所属会话<select disabled={busy} value={cid} onChange={e=>setCid(e.target.value)}>{chats.map(chat=><option key={chat.id} value={chat.id}>{chat.title}</option>)}</select></label>
    <button disabled={busy||!cid} onClick={()=>void act(()=>load(cid))}>刷新本地上下文与候选</button>
    {context&&<article aria-label="最近五轮上下文"><h4>本地最近五轮上下文</h4><p>当前保留 {context.rounds.length} 轮。工具事件归属原轮次，失败、取消和待审批不会视为成功。{context.truncated?'部分正文已排除或达到预算，展示不代表完整覆盖。':''}</p>
      {context.current&&<details><summary>当前未完成轮次：{statusLabel[context.current.status]??'状态待核对'}</summary>{context.current.messages.map(message=><p key={message.source_id}>{message.role==='user'?'用户':'会话记录'}：{message.text}{message.truncated?'（正文受限）':''}</p>)}</details>}
      {context.rounds.map((round,index)=><details key={round.request_id}><summary>第{index+1}轮 · {statusLabel[round.status]??'状态待核对'}{round.truncated?' · 正文受限':''}</summary>{round.messages.map(message=><p key={message.source_id}>{message.role==='user'?'用户':'会话记录'}：{message.text}</p>)}</details>)}
      {context.summary&&<details><summary>已批准的派生摘要（准确原文摘录）</summary>{context.summary.items.map((item,index)=><p key={index}>{item.text}</p>)}<p>摘要不能替代原文引用。较早轮次状态仍由程序保存。</p></details>}
    </article>}
    <h4>本地自动候选</h4><p>{state?.summary_pending?'有较早轮次等待摘要整理。':'暂无较早轮次需要整理。'}候选不等于确认事实。{state?.truncated?'候选与记录展示受预算限制。':''}</p>
    {state?.candidates.map(item=><article key={item.id}><p>{kindLabel[item.kind]} · {item.key}：{item.value}</p><small>候选，尚未批准整理</small><Sources item={item}/></article>)}
    <button disabled={busy||!cid} onClick={()=>void act(async()=>{setPreview(undefined);const r=await window.orvia.memoryPreview({id:cid});if(r.ok){setPreview(r.result);setNotice('已准备准确发送内容，请完整查看后再决定。');}else setNotice(r.message);})}>准备待处理摘要与记忆</button>
    {preview&&<article aria-label="记忆发送完整预览"><h4>本批准确发送预览</h4><p>接收：{preview.supplier}。用途：{preview.purpose}，可能产生供应商费用。只发送下方本批内容，不包含检索到的其它会话记忆。</p>
      <label>系统说明（完整正文）<textarea readOnly value={preview.instructions} rows={5}/></label>
      <label>本批输入（完整字段与原文）<textarea readOnly value={JSON.stringify(preview.input,null,2)} rows={12}/></label>
      <p>实际系统说明与输入合计 {preview.bytes} 字节。上方输入用缩进展示；发送时采用固定排序、UTF-8、无多余空格的 JSON 编码。</p>
      <button disabled={busy} onClick={()=>void act(async()=>{const approved=preview;setPreview(undefined);const r=await window.orvia.memoryGenerate({id:cid,revision:approved.revision});if(r.ok){if(r.result.cancelled)setNotice('已取消，模型未调用。');else{if(r.result.result)setState(r.result.result);setNotice('本批整理结束，结果已按原文校验，请核对记录。');await load(cid);}}else setNotice(r.message);})}>原生确认此批发送</button>
    </article>}
    <h4>已保存的派生记忆</h4>
    {state?.memories.map(item=><article key={item.id}><p>{kindLabel[item.kind]} · {item.key}：{item.value}</p><small>{statusLabel[item.status]}</small><Sources item={item}/>
      <label>修正 {item.key}<input disabled={busy} maxLength={600} value={edits[item.id]??item.value} onChange={e=>setEdits(old=>({...old,[item.id]:e.target.value}))}/></label>
      <div className="row"><button disabled={busy||!((edits[item.id]??item.value).trim())||Array.from(edits[item.id]??item.value).length>300} onClick={()=>void act(async()=>{setPreview(undefined);const r=await window.orvia.memoryCorrect({id:cid,memory_id:item.id,value:edits[item.id]??item.value});setNotice(r.ok?'修正已保存为明确用户原文，其它矛盾来源保留冲突。':r.message);await load(cid);})}>保存此条修正</button>
      <button disabled={busy} onClick={()=>void act(async()=>{setPreview(undefined);const r=await window.orvia.memoryForget({id:cid,memory_id:item.id});setNotice(r.ok?(r.result.cancelled?'已取消忘记。':'此条派生记忆已忘记，原文保留。'):r.message);await load(cid);})}>忘记此条记忆</button></div>
    </article>)}
    <h4>跨会话本地记忆检索</h4><label>本地记忆问题<input disabled={busy} maxLength={400} value={query} onChange={e=>setQuery(e.target.value)}/></label>
    <button disabled={busy||!query.trim()||Array.from(query).length>200} onClick={()=>void act(async()=>{const r=await window.orvia.memorySearch({query});if(r.ok){setHits(r.result.memories);setNotice('已在本机检索有有效原文支持的记忆；冲突与撤回项不会作为事实返回。');}else setNotice(r.message);})}>在本机检索记忆</button>
    {hits&&<p>返回 {hits.length} 条有界结果；不代表全部会话全文覆盖。</p>}{hits?.map(item=><article key={`${item.conversation_id}:${item.id}`}><p>{item.key}：{item.value}</p><small>{statusLabel[item.status]}</small><Sources item={item}/><button disabled={busy} onClick={()=>setCid(item.conversation_id)}>查看来源会话的记忆</button></article>)}
    <p role="status">{notice}</p>
  </section>;
}
