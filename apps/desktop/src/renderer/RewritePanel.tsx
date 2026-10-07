import React,{useEffect,useState} from 'react';
import type {MemoryRecord} from '../main/memory-contracts';
import type {RewritePreview,RewriteResult,RewriteSearch} from '../main/rewrite-contracts';

const labels={rewritten:'已生成有依据的检索候选',original:'使用原问题',clarification:'需要消歧，使用原问题'};
const reasons:Record<string,string>={ALREADY_ATTEMPTED:'本批已有调用记录，不会重新发送',PREVIEW_EXPIRED:'发送预览已过期，请重新审查',STALE_REWRITE:'查询或选中记忆已变化，使用原问题',MISSING_CREDENTIAL:'固定 Main 凭据未配置',MODEL_UNAVAILABLE:'固定 Main 暂不可用',MODEL_TIMEOUT:'改写请求超时',INVALID_REWRITE:'模型结果未通过结构或依据校验',CANCELLED:'发送已取消',NO_APPROVED_REWRITE:'没有已批准的有效改写，使用原问题',SOURCE_CHANGED:'来源或准确检索范围已变化，使用原问题'};
const reason=(value:string|null)=>value?(reasons[value]??value):'';

/** 跨会话记忆必须逐项选择并完整预览；取消和失败仍保留原问题用于本机检索。 */
export function RewritePanel(){
  const [chats,setChats]=useState<{id:string;title:string}[]>([]),[cid,setCid]=useState(''),[query,setQuery]=useState('');
  const [memories,setMemories]=useState<MemoryRecord[]>([]),[selected,setSelected]=useState<string[]>([]),[memoryQuery,setMemoryQuery]=useState('');
  const [preview,setPreview]=useState<RewritePreview>(),[result,setResult]=useState<RewriteResult>(),[search,setSearch]=useState<RewriteSearch>(),[history,setHistory]=useState<RewriteResult[]>([]);
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  useEffect(()=>{let live=true;void window.orvia.chatList().then(r=>{if(live&&r.ok){setChats(r.result.conversations);setCid(r.result.conversations[0]?.id??'');}}).catch(()=>{if(live)setNotice('会话列表暂不可用。');});return()=>{live=false;};},[]);
  useEffect(()=>{let live=true;setPreview(undefined);setResult(undefined);setSearch(undefined);setSelected([]);setMemories([]);setHistory([]);
    if(cid)void Promise.all([window.orvia.memoryList({id:cid}),window.orvia.rewriteHistory({id:cid})]).then(([m,h])=>{if(!live)return;if(m.ok)setMemories(m.result.memories.filter(item=>item.status==='verified'));else setNotice(m.message);if(h.ok)setHistory(h.result.records);else setNotice(h.message);}).catch(()=>{if(live)setNotice('本地记忆与改写记录暂不可用。');});
    return()=>{live=false;};
  },[cid]);
  async function reloadHistory(){const r=await window.orvia.rewriteHistory({id:cid});if(r.ok)setHistory(r.result.records);}
  async function act(action:()=>Promise<void>){setBusy(true);try{await action();}catch{setPreview(undefined);setNotice('操作未完成或结果未知；保留原问题，可在本机检索，不会自动重试云端请求。');}finally{setBusy(false);}}
  async function localSearch(useRewrite:boolean){
    const r=await window.orvia.rewriteSearch({id:cid,query,...(useRewrite&&result?.revision?{revision:result.revision}:{})});
    if(r.ok){setSearch(r.result);setNotice(`已在当前有效资料范围内检索，原问题始终保留。返回 ${r.result.evidence.length} 个原文片段。${r.result.truncated?'结果达到显示预算。':''}`);}else{setSearch(undefined);setNotice(r.message);}
  }
  const valid=Boolean(cid&&query.trim()&&Array.from(query).length<=200);
  return <section aria-label="查询改写与本地检索" className="skills-panel"><h3>查询改写与本地检索</h3>
    <p>原问题始终保留。改写最多补充三个有依据的检索候选，只检索当前会话有效资料；明确选中的记忆可能随批准内容发送给固定 Main。</p>
    <label>查询所属会话<select disabled={busy} value={cid} onChange={e=>setCid(e.target.value)}>{chats.map(chat=><option key={chat.id} value={chat.id}>{chat.title}</option>)}</select></label>
    <label>原问题<input disabled={busy} maxLength={400} value={query} onChange={e=>{setQuery(e.target.value);setPreview(undefined);setResult(undefined);setSearch(undefined);}}/></label>
    <h4>明确选择允许使用的本地记忆（最多三条）</h4><p>默认不选择跨会话记忆。多个人物或项目存在歧义时，请减少选择并明确问题。</p>
    <label>寻找可选本地记忆<input disabled={busy} maxLength={400} value={memoryQuery} onChange={e=>setMemoryQuery(e.target.value)}/></label>
    <button disabled={busy||!memoryQuery.trim()||Array.from(memoryQuery).length>200} onClick={()=>void act(async()=>{const r=await window.orvia.memorySearch({query:memoryQuery});if(r.ok){setMemories(old=>{const items=new Map([...old.filter(item=>selected.includes(item.id)),...r.result.memories,...old].map(item=>[item.id,item]));return [...items.values()].slice(0,30);});setNotice('已在本机找到有有效来源支持的记忆；仍需明确勾选才进入发送预览。');}else setNotice(r.message);})}>本地查找可选记忆</button>
    {memories.map(item=><article key={item.id}><label><input type="checkbox" disabled={busy||(!selected.includes(item.id)&&selected.length>=3)} checked={selected.includes(item.id)} onChange={e=>{setSelected(old=>e.target.checked?[...old,item.id]:old.filter(id=>id!==item.id));setPreview(undefined);setResult(undefined);setSearch(undefined);}}/>{item.key}：{item.value}</label><details><summary>所选记忆的原文来源</summary><p>来源会话：{item.conversation_id}</p>{item.sources.map(source=><p key={source.source_id}>{source.quote}<small> · {source.source_id}</small></p>)}</details></article>)}
    <div className="row"><button disabled={busy||!valid} onClick={()=>void act(()=>localSearch(false))}>直接在本机检索原问题</button>
    <button disabled={busy||!valid} onClick={()=>void act(async()=>{setPreview(undefined);setResult(undefined);setSearch(undefined);const r=await window.orvia.rewritePreview({id:cid,query,memory_ids:selected});if(r.ok){setPreview(r.result);setNotice(r.result.status==='clarification'?`需要先消歧：${reason(r.result.reason)}；可以直接检索原问题。`:'完整发送内容已准备，请查看原问题、选中记忆、资料片段与准确范围。');}else setNotice(r.message);})}>准备查询改写预览</button></div>
    {preview&&<article aria-label="查询改写准确发送预览"><h4>本批准确发送预览</h4><p>接收方：{preview.supplier}。用途：{preview.purpose}，可能产生供应商费用。</p>
      <label>改写系统说明（完整正文）<textarea readOnly rows={5} value={preview.instructions}/></label>
      <label>改写输入（原问题、明确记忆、资料片段和准确范围）<textarea readOnly rows={12} value={JSON.stringify(preview.input,null,2)}/></label>
      <p>实际系统说明与输入合计 {preview.bytes} 字节。展示采用缩进，发送采用固定排序、UTF-8 紧凑 JSON。资料范围与正文版本仅用于本次检索校验。</p>
      {preview.status==='clarification'?<p>尚未消歧：{reason(preview.reason)}。请调整选择或直接检索原问题。</p>:<button disabled={busy} onClick={()=>void act(async()=>{const approved=preview;setPreview(undefined);const r=await window.orvia.rewriteGenerate({id:cid,revision:approved.revision});if(r.ok){if(r.result.cancelled){setResult(undefined);await localSearch(false);setNotice('已取消发送，模型未调用；已在本机使用原问题检索。');}else if(r.result.result){setResult(r.result.result);setNotice(`${labels[r.result.result.status]}。${reason(r.result.result.reason)} 原问题未改变。`);await reloadHistory();}}else setNotice(`${r.message} 原问题仍可直接在本机检索。`);})}>原生确认此批查询改写</button>}
    </article>}
    {result&&<article aria-label="查询改写结果"><h4>{labels[result.status]}</h4><p>原问题：{result.original}</p>{result.reason&&<p>{reason(result.reason)}</p>}{result.candidates.map((candidate,index)=><details key={index}><summary>候选 {index+1}：{candidate.query}</summary><p>检索依据：{candidate.source_ids.length?candidate.source_ids.join('、'):'受限同义表达，未引入新条件'}</p></details>)}
      <button disabled={busy||!valid} onClick={()=>void act(()=>localSearch(result.status==='rewritten'))}>在本机检索原问题和有效候选</button></article>}
    {search&&<article aria-label="查询改写检索结果"><h4>本机检索结果</h4><p>保留原问题：{search.original}</p><p>实际查询：{search.queries.join('；')}</p><p>{search.evidence.length} 个原文片段。检索结果不代表全文覆盖。{search.truncated?'结果受预算限制。':''}</p>{search.evidence.map(item=><article key={item.content_hash}><p>{item.text}</p><small>{item.channels.map(channel=>channel==='keyword'?'关键词':'向量').join('、')}</small><details><summary>原文定位与支持来源</summary><p>{item.source} · 片段 {item.chunk_index+1}</p>{item.supporting_sources.map(source=><p key={`${source.source}:${source.chunk_id}`}>{source.source} · 片段 {source.chunk_index+1}</p>)}<p>{item.provenance_truncated?'支持来源展示受限。':''}</p></details></article>)}</article>}
    <details><summary>本会话改写记录（最多显示二十条）</summary>{history.map((item,index)=><article key={`${item.revision??'local'}:${index}`}><p>{labels[item.status]} · 原问题：{item.original}</p>{item.reason&&<p>{reason(item.reason)}</p>}{item.candidates.map((candidate,i)=><p key={i}>候选：{candidate.query} · {candidate.source_ids.join('、')||'受限同义表达'}</p>)}</article>)}</details>
    <p role="status">{notice}</p>
  </section>;
}
