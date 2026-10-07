import React,{useEffect,useState} from 'react';
import type {RetrievalStatus,RetrievalResult} from '../main/retrieval-contracts';

const reasons:Record<string,string>={MODEL_MISSING:'尚未准备本地模型',MODEL_UNAVAILABLE:'模型暂不可用',MODEL_CHECKSUM_FAILED:'模型文件校验失败',MODEL_TIMEOUT:'本地推理超时',MODEL_MEMORY_LIMIT:'模型内存超限',MODEL_RUNTIME_UNAVAILABLE:'嵌入运行库不可用',MODEL_DOWNLOAD_FAILED:'下载未完成，请检查网络和私有目录',INDEX_MISSING:'所选资料尚未建立向量索引',INDEX_VERSION_MISMATCH:'索引版本不匹配，请重建',INDEX_MISSION_LIMIT:'片段超过本次索引预算',INDEX_TEXT_LIMIT:'片段长度超过预算'};
Object.assign(reasons,{SCOPE_EMPTY:'当前会话没有有效资料',MODEL_TOKEN_LIMIT:'片段超过1024 tokens预算',MODEL_PROCESS_LIMIT:'模型工作器进程数量超限',MODEL_RESOURCE_UNAVAILABLE:'无法监测模型进程资源',MODEL_WORKER_FAILED:'模型工作器已退出或通信失败',MODEL_INTERRUPTED:'模型准备被中断',MODEL_SIGNATURE_MISMATCH:'模型版本签名不匹配',MODEL_STATUS_INVALID:'模型就绪状态无效',INDEX_CHANGED:'检索期间资料或索引发生变化',INDEX_VECTOR_INVALID:'索引向量校验失败',INDEX_SOURCE_CHANGED:'索引与当前原文版本不一致',EMBEDDING_TIMEOUT:'本地嵌入请求超时',EMBEDDING_FAILED:'本地嵌入请求失败',RETRIEVAL_VECTOR:'嵌入向量不符合契约',RETRIEVAL_GLOBAL_LIMIT:'全库向量预算已满，请清除旧会话向量',RETRIEVAL_MISSION_LIMIT:'当前会话向量预算已满'});
function reason(value:string|null){return value?(reasons[value]??`本地向量不可用（${value}）`):'';}

/** 本地检索展示原文事实；排序与相似度不能代替资料真实性判断。 */
export function RetrievalPanel(){
  const [state,setState]=useState<RetrievalStatus>(),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  const [chats,setChats]=useState<{id:string;title:string}[]>([]),[cid,setCid]=useState(''),[query,setQuery]=useState(''),[result,setResult]=useState<RetrievalResult>();
  async function reload(){const s=await window.orvia.retrievalStatus();if(s.ok)setState(s.result);else setNotice(s.message);const c=await window.orvia.chatList();if(c.ok){setChats(c.result.conversations);setCid(old=>c.result.conversations.some(x=>x.id===old)?old:c.result.conversations[0]?.id??'');}}
  useEffect(()=>{void reload().catch(()=>setNotice('本地检索连接失败。'));},[]);
  async function act(action:()=>Promise<void>){setBusy(true);setNotice('正在本机处理，请稍候。');try{await action();await reload();}catch{setNotice('本地检索未完成，请检查连接与资料。');}finally{setBusy(false);}}
  return <section aria-label="本地混合检索" className="skills-panel"><h3>本地混合检索</h3><p>仅检索所选会话当前关联的已提取资料。正文在本机生成向量，三个角色仍使用各自固定模型。</p>
    <p role="status">{state?.ready?'本地模型已就绪':`关键词降级：${reason(state?.reason??'MODEL_MISSING')}`}</p>
    <div className="row"><button disabled={busy} onClick={()=>void act(async()=>{const r=await window.orvia.retrievalDownload();setNotice(r.ok?(r.result.cancelled?'已取消下载。':r.result.result?.ready?'模型已核验并加载。':reason(r.result.result?.reason??null)):r.message);})}>确认下载官方模型</button>
    <button disabled={busy} onClick={()=>void act(async()=>{const r=await window.orvia.retrievalChoose();setNotice(r.ok?(r.result.cancelled?'已取消选择。':r.result.result?.ready?'已有模型已核验。':reason(r.result.result?.reason??null)):r.message);})}>选择已有模型</button>
    <button disabled={busy} onClick={()=>void act(async()=>{const r=await window.orvia.retrievalActivate();setNotice(r.ok?(r.result.ready?'已加载此前核验模型。':reason(r.result.reason)):r.message);})}>加载此前模型</button></div>
    <label>资料所属会话<select disabled={busy} value={cid} onChange={e=>{setCid(e.target.value);setResult(undefined);}}>{chats.map(c=><option key={c.id} value={c.id}>{c.title}</option>)}</select></label>
    <div className="row"><button disabled={busy||!cid} onClick={()=>void act(async()=>{const r=await window.orvia.retrievalRebuild({id:cid});setNotice(r.ok?(r.result.status==='completed'?`已建立 ${r.result.indexed_chunks} 个片段的向量索引。`:`索引未完成：${reason(r.result.reason)}`):r.message);})}>建立当前资料索引</button>
    <button disabled={busy||!cid} onClick={()=>void act(async()=>{const r=await window.orvia.retrievalClear({id:cid});setResult(undefined);setNotice(r.ok?'当前会话全部向量已清除，原文保留。':r.message);})}>清除当前会话向量</button></div>
    <label>检索问题<input maxLength={200} value={query} disabled={busy} onChange={e=>setQuery(e.target.value)}/></label><button disabled={busy||!cid||!query.trim()} onClick={()=>void act(async()=>{const r=await window.orvia.retrievalSearch({id:cid,query});if(r.ok){setResult(r.result);setNotice(r.result.status==='hybrid'?'已融合关键词和向量召回。':`关键词降级：${reason(r.result.reason)}`);}else setNotice(r.message);})}>检索关联资料</button>
    <p role="status">{notice}</p>{result&&<><p>本次返回{result.evidence.length}个原文片段；检索范围不等于全文覆盖。{result.coverage.output_limited?'结果达到显示预算。':''}</p>{result.evidence.map(item=><article key={item.content_hash}><p>{item.text}</p><small>{item.channels.map(x=>x==='keyword'?'关键词':'向量').join('、')}</small><details><summary>来源详情</summary><p>{item.source} · 片段{item.chunk_index+1}</p><p>{item.content_hash}</p><p>支持定位{item.provenance_count}项{item.provenance_truncated?'，详情受限':''}</p></details></article>)}</>}
    <details><summary>模型与资源详情</summary><p>Qwen/Qwen3-Embedding-0.6B；1024维，模型约1.12GiB。独立CPU进程4线程、4片段批次、1024 tokens。每0.1秒监测启动器与自有后代的RSS合计，超过6GiB终止；这是监测阈值。缺失、校验失败或超限时保留关键词检索。</p><p>{state?.signature}</p><p>已观察工作器进程树峰值：{Math.round((state?.peak_bytes??0)/1024/1024)} MiB。</p></details>
  </section>;
}
