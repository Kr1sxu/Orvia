import React,{useEffect,useState} from 'react';
import type {GraphEntity,GraphList,GraphPreview,GraphQuery,GraphRelation,GraphSource} from '../main/graph-contracts';

const kindLabel={person:'人物',project:'项目',file:'文件'};
const stateLabel={verified:'有原文支持',conflict:'来源冲突，未用于查询路径',revoked:'支持已撤回'};
const relationLabel={responsible_for:'负责',member_of:'参与',documents:'记录',depends_on:'依赖'};
function Sources({sources}:{sources:GraphSource[]}){return <details><summary>精确原文证据</summary>{sources.map(source=><div key={`${source.source_id}:${source.version}`}><p>{source.quote}</p><small>{source.status==='user_statement'?'用户原文':'关联资料原文'} · {source.source_id}</small><p>原文版本：{source.version}</p></div>)}</details>;}
function Entity({item}:{item:GraphEntity}){return <><p>{kindLabel[item.kind]} · {item.name}</p><small>{stateLabel[item.status]}</small><details><summary>实体身份与来源范围</summary><p>会话：{item.conversation_id}</p><p>来源范围：{item.scope}</p><p>实体：{item.id}</p></details><Sources sources={item.sources}/></>;}
function Relation({item,entities}:{item:GraphRelation;entities:GraphEntity[]}){
  const name=(id:string)=>entities.find(entity=>entity.id===id)?.name??'实体未在当前有界列表展示';
  return <><p>{name(item.from_id)} → {relationLabel[item.kind]} → {name(item.to_id)}</p><small>{stateLabel[item.status]}</small><details><summary>关系方向与身份</summary><p>起点：{item.from_id}</p><p>终点：{item.to_id}</p><p>会话：{item.conversation_id}</p></details><Sources sources={item.sources}/></>;
}

/** 图谱是批准原文中的有界证据关系；同名身份由用户明确选择，本地查询不批准外发或执行。 */
export function GraphPanel(){
  const [chats,setChats]=useState<{id:string;title:string}[]>([]),[cid,setCid]=useState('');
  const [listing,setListing]=useState<GraphList>(),[preview,setPreview]=useState<GraphPreview>(),[result,setResult]=useState<GraphQuery>();
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState(''),[query,setQuery]=useState(''),[hops,setHops]=useState<1|2>(2);
  useEffect(()=>{let live=true;void window.orvia.chatList().then(reply=>{if(live&&reply.ok){setChats(reply.result.conversations);setCid(reply.result.conversations[0]?.id??'');}}).catch(()=>{if(live)setNotice('会话列表暂不可用。');});return()=>{live=false;};},[]);
  useEffect(()=>{let live=true;setListing(undefined);setPreview(undefined);if(cid)void window.orvia.graphList({id:cid}).then(reply=>{if(live){if(reply.ok)setListing(reply.result);else setNotice(reply.message);}}).catch(()=>{if(live)setNotice('本地图谱读取未完成，请检查连接。');});return()=>{live=false;};},[cid]);
  async function act(action:()=>Promise<void>){setBusy(true);try{await action();}catch{setPreview(undefined);setNotice('操作未完成或结果未知，请核对现有记录；不会自动重试云请求。');}finally{setBusy(false);}}
  async function localQuery(entity_id?:string){const reply=await window.orvia.graphQuery({query,hops,...(entity_id?{entity_id}:{})});if(reply.ok){setResult(reply.result);setNotice(reply.result.ambiguous?'找到多个身份，请选择准确实体；不会按同名自动合并。':'已在本机查询有效原文支持的关系，未调用云模型。');}else{setResult(undefined);setNotice(reply.message);}}
  return <section aria-label="实体关系与知识图谱" className="skills-panel"><h3>实体关系与知识图谱</h3>
    <p>从批准的会话和关联资料原文抽取人物、项目、文件及关系。图谱表示资料范围内的证据，不保证客观真相，不授予文件、执行或外发权限。</p>
    <label>图谱所属会话<select value={cid} disabled={busy} onChange={event=>setCid(event.target.value)}>{chats.map(chat=><option key={chat.id} value={chat.id}>{chat.title}</option>)}</select></label>
    <button disabled={busy||!cid} onClick={()=>void act(async()=>{const reply=await window.orvia.graphList({id:cid});if(reply.ok)setListing(reply.result);else setNotice(reply.message);})}>刷新本地图谱</button>
    <button disabled={busy||!cid} onClick={()=>void act(async()=>{setPreview(undefined);const reply=await window.orvia.graphPreview({id:cid});if(reply.ok){setPreview(reply.result);setNotice('已准备准确发送原文，请完整查看后再决定。');}else setNotice(reply.message);})}>准备实体关系抽取预览</button>
    {preview&&<article aria-label="图谱发送完整预览"><h4>本批准确发送预览</h4><p>接收：{preview.supplier}。用途：{preview.purpose}，可能产生供应商费用。{preview.truncated?'本批达到预算，未包含全部原文。':''}</p>
      <label>图谱系统说明（完整正文）<textarea readOnly value={preview.instructions} rows={5}/></label>
      <label>图谱本批输入（完整字段与原文）<textarea readOnly value={JSON.stringify(preview.input,null,2)} rows={12}/></label>
      <p>实际系统说明与输入合计 {preview.bytes} 字节。发送采用固定排序、UTF-8、无多余空格的 JSON；上方缩进只用于阅读。</p>
      <button disabled={busy} onClick={()=>void act(async()=>{const approved=preview;setPreview(undefined);const reply=await window.orvia.graphGenerate({id:cid,revision:approved.revision});if(reply.ok){if(reply.result.cancelled)setNotice('已取消，模型未调用。');else{if(reply.result.result)setListing(reply.result.result);setResult(undefined);setNotice('本批抽取已按原文校验，请核对实体、方向和证据。');}}else setNotice(reply.message);})}>原生确认此批图谱发送</button>
    </article>}
    <h4>本地实体</h4>{listing&&<p>当前展示 {listing.entities.length} 个实体、{listing.relations.length} 条关系。{listing.truncated?'列表达到预算，不代表完整覆盖。':''}</p>}
    {listing?.entities.map(item=><article key={item.id}><Entity item={item}/></article>)}
    <h4>本地有向关系</h4>{listing?.relations.map(item=><article key={item.id}><Relation item={item} entities={listing.entities}/></article>)}
    <h4>跨会话本地关系查询</h4><label>实体名称或本地问题<input disabled={busy} maxLength={400} value={query} onChange={event=>{setQuery(event.target.value);setResult(undefined);}}/></label>
    <label>关系路径上限<select disabled={busy} value={hops} onChange={event=>{setHops(event.target.value==='1'?1:2);setResult(undefined);}}><option value={1}>一跳</option><option value={2}>两跳</option></select></label>
    <button disabled={busy||!query.trim()||Array.from(query).length>200} onClick={()=>void act(()=>localQuery())}>在本机查询关系</button>
    {result&&<article aria-label="本地关系查询结果"><p>返回 {result.entities.length} 个实体身份、{result.paths.length} 条路径。{result.truncated?'结果达到预算。':''}</p>
      {result.ambiguous&&<p>同名或匹配到多个实体，请结合会话、原文与身份逐项选择。</p>}
      {result.entities.map(item=><article key={item.id}><Entity item={item}/>{result.ambiguous&&<button disabled={busy} onClick={()=>void act(()=>localQuery(item.id))}>选择实体：{item.name} · {item.id.slice(0,8)}</button>}</article>)}
      {result.paths.map((path,index)=><article key={`${path.entities[0]?.id}:${index}`}><h5>路径{index+1} · {path.relations.length}跳</h5>{path.relations.map(item=><div key={item.id}><Relation item={item} entities={path.entities}/></div>)}</article>)}
      <p>冲突或已撤回关系不用于查询路径；关系箭头表示原文抽取的方向，不能当作执行指令。</p>
    </article>}
    <p role="status">{notice}</p>
  </section>;
}
