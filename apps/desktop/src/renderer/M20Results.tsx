import React,{useState} from 'react';
import {modelPartialSchema,type ChatMessage} from '../main/chat-contracts';
import {scanEntrySchema,type ScanEntry,type ScanPage} from '../main/m20-contracts';
import type {LiveStream} from './m20-state';
import {bytes} from './ChatCards';

function Entries({entries}:{entries:ScanEntry[]}){return <ul className="direct-files">{entries.map(entry=><li key={entry.path}><span>{entry.path}</span><small>{entry.kind==='directory'?'目录':entry.category+' · '+bytes(entry.size)}</small></li>)}</ul>;}
/** 完整入口读取同一已保存扫描快照的固定分页，不重新扫描、不暗中扩展权限。 */
export function DirectoryAnswer({cid,message,disabled}:{cid:string;message:ChatMessage;disabled:boolean}){
  const data=message.data??{},scan_id=typeof data.scan_id==='string'?data.scan_id:undefined;
  const [page,setPage]=useState<ScanPage>(),[loading,setLoading]=useState(false),[error,setError]=useState(''),[offsets,setOffsets]=useState<number[]>([]);
  if(!scan_id)return null;
  const summary=(page?.summary??data.summary??{}) as Record<string,unknown>;
  const initial=Array.isArray(data.entries)?data.entries.map(item=>scanEntrySchema.safeParse(item)).flatMap(item=>item.success?[item.data]:[]):[];
  const entries=page?.entries??initial,discovered=Number(summary.discovered??page?.total??initial.length),offset=page?.offset??0;
  const nextOffset=page?page.next_offset:initial.length<discovered?initial.length:null;
  async function load(targetOffset:number,back=false){setLoading(true);try{const reply=await window.orvia.chatScanPage({id:cid,scan_id:scan_id!,offset:targetOffset});if(reply.ok){setOffsets(values=>targetOffset===0?[]:back?values.slice(0,-1):[...values,offset]);setPage(reply.result);setError('');}else setError(reply.message);}catch{setError('完整清单读取失败，请核对连接和已保存事实。');}finally{setLoading(false);}}
  return <section className="directory-answer" aria-label="目录直接回答"><p>在{String(summary.scope??'选定目录')}中实际发现{discovered}项，当前展示{entries.length}项（条目{entries.length?offset+1:0}–{offset+entries.length}，每批至多100项）。扫描深度{String(summary.depth??1)}；已访问{String(summary.visited??discovered)}项。</p>
    <p className="muted">分类依据仅为扩展名与元数据，没有读取文件正文。{summary.recursive?'包含已声明深度的子目录。':'只扫描第一层。'}</p>
    {summary.truncated===true||summary.complete===false?<p className="warning">本次扫描未覆盖全部范围：{String(summary.reason??'预算或不可访问限制')}。完整清单只包含本次实际发现条目。</p>:null}
    {Array.isArray(summary.errors)&&summary.errors.length>0&&<p className="warning">拒绝或不可访问：{summary.errors.map(item=>{const value=item as Record<string,unknown>;return String(value.code)+' '+String(value.count)+'项';}).join('、')}</p>}
    {Array.isArray(summary.categories)&&<p>{summary.categories.map(item=>{const value=item as Record<string,unknown>;return String(value.name)+' '+String(value.count)+'项';}).join('，')}</p>}
    {entries.length?<Entries entries={entries}/>:<p>本次范围没有发现条目。</p>}
    <div className="row"><button disabled={disabled||loading} onClick={()=>void load(0)}>完整已发现清单（{discovered}项）</button>{offsets.length>0&&<button disabled={disabled||loading} onClick={()=>void load(offsets.at(-1)!,true)}>上一页</button>}{nextOffset!==null&&<button disabled={disabled||loading} onClick={()=>void load(nextOffset)}>下一页</button>}</div>{loading&&<p role="status">正在读取已保存清单…</p>}{error&&<p role="alert">{error}</p>}
  </section>;
}
/** 增量来自真实事件；成功引用尚未核验之前不呈现M16成品入口。 */
export function LiveResult({stream}:{stream:LiveStream}){return <article className="message assistant" aria-label="实时结果"><span className="speaker">序航 · {stream.status}</span><div className="bubble">{stream.entries.length>0&&<><p>已收到{stream.entries.length}个真实扫描条目。当前展示前{Math.min(100,stream.entries.length)}项，终态后可分页查看全部已发现清单。</p><Entries entries={stream.entries.slice(0,100)}/><small>仅按扩展名分类，未读取正文。</small></>}{stream.text&&<><p className="message-text">{stream.text}</p><p className="warning">生成中或未完成的文本；引用待完整结果校验，不可制作成品。</p></>}{stream.error&&<p role="alert" className="warning">{stream.error}</p>}</div></article>;}

/** 重启后的有界前缀是实际已保存文字，不能提升为成功回答、引用或成品来源。 */
export function PartialModelMessage({message}:{message:ChatMessage}){
  const parsed=modelPartialSchema.safeParse(message.data);if(!parsed.success)return <p role="alert">部分模型记录身份或预算无效，请核对已保存事实。</p>;
  const value=parsed.data,status={running:'中断前运行中',paused:'暂停',completed:'终态仍未核验',failed:'失败',cancelled:'已取消',interrupted:'连接中断'}[value.state];
  return <section aria-label="部分模型文字（未核验）"><p className="warning">实际保存的部分模型文字 · {status}。正文尚未完成核验，不能作为成功回答或制作成品。</p><p className="message-text">{value.text}</p><small>已保存至序号{value.last_seq}；不会自动重发模型请求。</small></section>;
}
