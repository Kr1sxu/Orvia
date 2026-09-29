import React from 'react';
import {browserMessageSchema,type BrowserEvidence,type ChatMessage} from '../main/chat-contracts';

const modes:Record<string,string>={search:'搜索请求',search_snippet:'搜索摘要（未读取原网页）',http:'HTTP 网页正文',playwright:'动态网页正文'};
/** 所有网页文字按 React 文本转义；不渲染 HTML、不嵌入页面、不打开任意链接。 */
export function SourceDetail({source}:{source:BrowserEvidence}) {
  return <div className="source-body">
    <strong>{source.title||'来源未提供标题'}</strong><p className="source-url">{source.source_url||'URL 被拒绝或不可用'}</p>
    <p className="muted">{modes[source.mode??'']??'来源'} · 访问时间 {source.accessed_at}</p>
    <p className="muted">引用 {source.evidence_id.slice(0,12)} · 内容 SHA256 <code>{source.content_hash}</code></p>
    {source.truncated&&<p className="warning">原文已截断或部分资源受限，不代表完整页面。</p>}
    {source.preview_truncated&&<p className="muted">当前显示摘录；查看证据可读已保存正文。</p>}
    {source.error&&<p className="warning">{source.error.message}（{source.error.code}）</p>}
    {source.content.length>700?<details><summary>展开已保存正文（{Array.from(source.content).length} 字符）</summary><p className="source-content" tabIndex={0}>{source.content}</p></details>:<p className="source-content">{source.content||'没有可读正文。'}</p>}
  </div>;
}

export function SourceCard({message,disabled,show,read}:{message:ChatMessage;disabled:boolean;show:(id:string)=>void;read:(url:string)=>void}) {
  const data=browserMessageSchema.parse(message.data);
  return <div className="source-card" aria-label="来源与证据">
    {data.error&&<p className="warning">{data.error.message}（{data.error.code}）</p>}
    {!data.items.length&&<p>没有匹配来源；不会编造答案。</p>}
    {data.items.map(item=><details key={item.evidence_id}><summary>引用 {item.evidence_id.slice(0,12)} · {item.title||item.source_url||'错误证据'}</summary>
      <SourceDetail source={item}/><div className="row"><button disabled={disabled} onClick={()=>show(item.evidence_id)}>查看证据</button>
      {item.mode==='search_snippet'&&item.source_url&&<button disabled={disabled} onClick={()=>read(item.source_url!)}>读取此网页</button>}</div>
    </details>)}
  </div>;
}
