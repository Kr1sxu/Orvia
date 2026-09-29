import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { Conversation, ReadCall, BrowserEvidence } from '../main/chat-contracts';
import type { Reply, Settings } from '../shared/api';
import { SettingsPanel } from './SettingsPanel';
import { PlanCard, ScanCard, EvidenceCard } from './ChatCards';
import { SourceCard, SourceDetail } from './SourceCards';
import { nearBottom, submitsMessage, taskLabels } from './chat-state';
import './style.css';

function App() {
  const [list, setList] = useState<{id:string;title:string;status?:string}[]>([]);
  const [conversation, setConversation] = useState<Conversation>();
  const [text, setText] = useState('');
  const [query, setQuery] = useState('');
  const [intent,setIntent] = useState<'files'|'search'|'read'|'ask'>('files');
  const [source,setSource] = useState<{cid:string;value:BrowserEvidence}>();
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState('');
  const [notice, setNotice] = useState('');
  const [online, setOnline] = useState(false);
  const [settings, setSettings] = useState<Settings>();
  const [showSettings, setShowSettings] = useState(false);
  const [pendingUser, setPendingUser] = useState('');
  const [loadingList, setLoadingList] = useState(true);
  const [unread, setUnread] = useState(false);
  const [remoteBusy, setRemoteBusy] = useState(false);
  const [activeSend, setActiveSend] = useState<{id:string;request_id:string}>();
  const [cancelling, setCancelling] = useState(false);
  const activeId = useRef<string | undefined>(undefined);
  const working = useRef(false);
  const composing = useRef(false);
  const end = useRef<HTMLDivElement>(null);
  const scroll = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const follow = useRef(true);
  const previousRemoteBusy = useRef(false);
  // 同一请求失败后保留请求ID；重发不应导致第二次模型调用或文件计划。
  const submission = useRef<{id:string;text:string;request_id:string} | undefined>(undefined);
  const webSubmission = useRef<{id:string;value:string;intent:string;request_id:string}|undefined>(undefined);
  async function reloadSettings() {
    const health = await window.orvia.health(); setOnline(health.ok);
    const reply = await window.orvia.settings(); if (reply.ok) setSettings(reply.result); else setNotice(reply.message);
  }
  async function refreshList() { try { const reply = await window.orvia.chatList(); if (reply.ok) setList(reply.result.conversations); else setNotice(reply.message); } finally { setLoadingList(false); } }
  useEffect(() => { void (async () => { try {
    const status=await window.orvia.connectionStatus();
    if(status.ok&&status.result.busy)return;
    await reloadSettings(); await refreshList();
  } catch { setLoadingList(false);setNotice('本地连接失败，请使用重新连接。'); } })(); }, []);
  useEffect(() => { if (follow.current) end.current?.scrollIntoView({block:'end'}); else setUnread(true); }, [conversation?.messages, pendingUser, phase]);
  useEffect(() => { if (!busy && !remoteBusy && !showSettings) input.current?.focus(); }, [busy, remoteBusy, showSettings]);
  useEffect(() => {
    let stopped=false, polling=false;
    async function poll() {
      if (polling) return;
      polling=true;
      try {
        const reply=await window.orvia.connectionStatus();
        if (stopped) return;
        if (reply.ok) {
          setOnline(reply.result.state==='ready'); setRemoteBusy(reply.result.busy);
          setActiveSend(reply.result.cancellable ? reply.result.activeSend : undefined);
          // 重载期间只读主进程状态；请求结束后再读取事实，不重放发送或审批。
          if(reply.result.activeSend&&!activeId.current)activeId.current=reply.result.activeSend.id;
          if(previousRemoteBusy.current&&!reply.result.busy&&reply.result.state==='ready'&&!working.current){
            const id=activeId.current;if(id)accept(await window.orvia.chatGet({id}),id);
            await refreshList();await reloadSettings();
          }
          previousRemoteBusy.current=reply.result.busy;
        } else {setOnline(false);setRemoteBusy(false);setActiveSend(undefined);}
      } catch {if(!stopped){setOnline(false);setRemoteBusy(false);setActiveSend(undefined);}}
      finally {polling=false;}
    }
    void poll(); const timer=window.setInterval(()=>void poll(),1000);
    return ()=>{stopped=true;window.clearInterval(timer);};
  }, []);
  async function cancel() {
    if(!activeSend||cancelling)return;
    setCancelling(true);
    try {
      const reply=await window.orvia.chatCancel(activeSend);
      setNotice(reply.ok ? reply.result.cancelled ? '已请求取消规划；请等待确认。不会自动重发。' : '请求已结束或当前阶段不能取消，请刷新任务状态。' : reply.message);
    } catch {setNotice('取消确认失败，请刷新任务状态；不要重复审批。');}
    finally {setCancelling(false);}
  }
  async function reconnect() {
    await run('正在重新连接本地服务…',async()=>{
      const reply=await window.orvia.reconnect(); if(!reply.ok){setNotice(reply.message);return;}
      setOnline(true);setRemoteBusy(false);setActiveSend(undefined);submission.current=undefined;
      await reloadSettings();await refreshList();
      const id=activeId.current;if(id)accept(await window.orvia.chatGet({id}),id);
      setNotice('已重新连接。请核对任务事实并重新授权目录；未自动重发任何请求。');
    });
  }
  function accept(reply: Reply<Conversation>, id?: string) {
    if (!reply.ok) { setNotice(reply.message); return false; }
    // 回包只能更新发起请求时的会话，不能覆盖后来选择的会话。
    if (id && activeId.current !== id) return false;
    activeId.current = reply.result.id; setConversation(reply.result);
    // 快速审批可能在两次轮询之间完成，直接同步侧栏事实，不能依赖轮询捕获 busy。
    setList(items=>items.map(item=>item.id===reply.result.id?{...item,title:reply.result.title,status:reply.result.status}:item));
    return true;
  }
  async function run(label: string, action: () => Promise<void>) {
    if (working.current || remoteBusy) return;
    working.current = true; setBusy(true); setPhase(label); setNotice('');
    try { await action(); }
    catch { setNotice('本地通信失败。请刷新会话核对状态，文件动作不会自动重放。'); }
    finally { working.current = false; setBusy(false); setPhase(''); setPendingUser(''); }
  }
  async function create(title: string) {
    const reply = await window.orvia.chatCreate({client_request_id:crypto.randomUUID(),title:title.slice(0,80) || '新对话'});
    if (!accept(reply)) return undefined;
    return reply.ok ? reply.result.id : undefined;
  }
  function newChat() { if (working.current || remoteBusy) return; activeId.current=undefined; setConversation(undefined);setText('');setQuery('');setNotice('');setSource(undefined);setIntent('files');webSubmission.current=undefined;submission.current=undefined;follow.current=true;setUnread(false);input.current?.focus(); }
  async function open(id:string) { await run('正在读取历史会话…',async () => {activeId.current=id;setConversation(undefined);setText('');setQuery('');setSource(undefined);webSubmission.current=undefined;submission.current=undefined;follow.current=true;setUnread(false);accept(await window.orvia.chatGet({id}),id);}); }
  async function send(retryText?: string) {
    if(!retryText&&intent!=='files'){await sendWeb(intent,text);return;}
    const value = (retryText ?? text).trim(); if (!value || value.length>2000 || composing.current || working.current) return;
    await run('Main 正在理解需求与收集证据…',async () => {
      const id = activeId.current ?? await create(value); if (!id) return;
      if (submission.current?.id!==id || submission.current.text!==value) submission.current={id,text:value,request_id:crypto.randomUUID()};
      setPendingUser(value);
      const reply = await window.orvia.chatSend(submission.current);
      if (accept(reply,id)) {setText('');submission.current=undefined;}
      else if(!reply.ok) {const latest=await window.orvia.chatGet({id});if(latest.ok){accept(latest,id);if(['interrupted','cancelled'].includes(latest.result.status ?? ''))submission.current=undefined;}}
      await refreshList();
    });
  }
  async function choose() {
    await run('等待选择并授权本地目录…',async () => {
      const id=activeId.current ?? await create('本地文件整理'); if (!id) return;
      const reply=await window.orvia.chatChooseDirectory({id});
      if (!reply.ok) {setNotice(reply.message);return;}
      if (reply.result.cancelled) {setNotice('已取消选择，原授权与任务状态保持不变。');return;}
      if(reply.result.conversation) accept({ok:true,result:reply.result.conversation},id);
      setPhase('Computer 正在读取授权目录…');
      accept(await window.orvia.chatInspect({id,tool:'list_directory',arguments:{path:'.',limit:100}}),id);
      await refreshList();
    });
  }
  async function inspect(call:ReadCall) {const id=activeId.current;if(!id)return;await run('Computer 正在执行只读观察…',async()=>{accept(await window.orvia.chatInspect({id,...call}),id);});}
  async function sendWeb(kind:'search'|'read'|'ask',raw:string,clearComposer=true) {
    const value=raw.trim();if(!value||composing.current||value.length>({search:500,read:2048,ask:200}[kind]))return;
    await run(kind==='ask'?'正在检索当前会话来源…':kind==='search'?'正在搜索公开来源…':'正在读取公开网页…',async()=>{
      const id=activeId.current??await create(value);if(!id)return;
      // 同一请求保留标识以避免断线重发；切换类型不能借用旧请求标识。
      if(webSubmission.current?.id!==id||webSubmission.current.value!==value||webSubmission.current.intent!==kind)webSubmission.current={id,value,intent:kind,request_id:crypto.randomUUID()};
      const request={id,request_id:webSubmission.current.request_id};setPendingUser(value);
      const reply=await(kind==='search'?window.orvia.chatBrowserSearch({...request,query:value}):kind==='read'?window.orvia.chatBrowserRead({...request,url:value}):window.orvia.chatBrowserAsk({...request,query:value}));
      if(accept(reply,id)){if(clearComposer)setText('');webSubmission.current=undefined;}
      else {const latest=await window.orvia.chatGet({id});if(latest.ok)accept(latest,id);}
      await refreshList();
    });
  }
  async function showSource(evidence_id:string) {
    const id=activeId.current;if(!id)return;
    await run('正在读取已保存证据…',async()=>{const reply=await window.orvia.chatBrowserSource({id,evidence_id});if(reply.ok&&activeId.current===id)setSource({cid:id,value:reply.result});else if(!reply.ok)setNotice(reply.message);});
  }
  async function act(kind:'approve'|'resume'|'undo') {
    const op=conversation?.operation,id=activeId.current;if(!op||!id)return;
    await run(kind==='approve'?'正在审批、执行并核验此版本…':kind==='resume'?'正在核验中断任务…':'正在核验并撤销最近变更…',async()=>{
      const input={id,operation_id:op.operation_id,revision:op.revision};
      const reply=await (kind==='approve'?window.orvia.chatApprove(input):kind==='resume'?window.orvia.chatResume(input):window.orvia.chatUndo(input));
      accept(reply,id);
      // 即使动作返回错误也重读账本，避免部分完成/撤销仍显示旧状态。
      if(!reply.ok) {const latest=await window.orvia.chatGet({id});if(latest.ok)accept(latest,id);}
    });
  }
  const locked=busy||remoteBusy;
  const inputLimit={files:2000,search:500,read:2048,ask:200}[intent];
  const disabled=locked||!conversation?.grant||!online;
  const lastMessage=conversation?.messages.at(-1);
  const lastUser=conversation?.messages.slice().reverse().find(message=>message.role==='user');
  // 网页请求中断不能让“重试规划”错用更早的文件需求。
  const retryText=lastUser?.kind==='text'?lastUser.text:undefined;
  const retryable=!!retryText&&lastMessage?.kind==='error'&&['MODEL_UNAVAILABLE','MODEL_TIMEOUT','MISSING_CREDENTIAL','INVALID_PROPOSAL','REQUEST_INTERRUPTED','REQUEST_CANCELLED'].includes(String(lastMessage.data?.code));
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><span className="brand-mark">序</span><strong>序航 <small>Orvia</small></strong></div>
      <button className="new-chat" disabled={locked} onClick={newChat}>＋ 新建对话</button><p className="nav-label">最近对话</p>
      <nav aria-label="历史会话" aria-busy={loadingList}>{list.map(item=><button title={item.title} aria-label={item.title} aria-current={conversation?.id===item.id?'page':undefined} className={conversation?.id===item.id?'selected':''} disabled={locked} key={item.id} onClick={()=>void open(item.id)}><span className="history-title">{item.title}</span><small>{taskLabels[item.status ?? 'draft'] ?? item.status}</small></button>)}{loadingList?<p role="status" className="muted">正在读取会话…</p>:!list.length&&<p className="muted">从第一个问题开始。</p>}</nav>
      <div className="sidebar-bottom"><button disabled={locked} onClick={()=>setShowSettings(true)}>⚙ 设置</button><span className="connection"><i className={online?'online':''}/>{online?'本地服务已连接':'本地服务未连接'}</span></div>
    </aside>
    <main className="chat-main"><header className="topbar"><span>{conversation?.title ?? '新对话'}</span><span className="badge" aria-live="polite">{locked?'处理中':taskLabels[conversation?.status ?? 'draft'] ?? '草稿'}</span></header>
      <div className="message-scroll" ref={scroll} tabIndex={0} aria-label="对话消息" onScroll={()=>{const el=scroll.current;if(el){follow.current=nearBottom(el.scrollTop,el.clientHeight,el.scrollHeight);if(follow.current)setUnread(false);}}}><div className="conversation-content">
        {!conversation?.messages.length&&!pendingUser&&!locked&&<section className="welcome"><span className="welcome-mark">序</span><h1>你好，我是序航 Orvia</h1><p>从一个想法开始，把文件整理得井井有条。</p><div className="suggestions">{['看看目录里有哪些文件','找出占用空间较大的文件','帮我拟定分类整理计划'].map(value=><button key={value} disabled={locked} onClick={()=>{setText(value);input.current?.focus();}}>{value}<span>↗</span></button>)}</div></section>}
        {conversation?.messages_truncated&&<p className="muted">为限制通信大小，当前仅显示最近消息；更早记录保留在本地。</p>}
        {conversation?.messages.map(message=><article key={message.id} className={'message '+message.role}><span className="speaker">{message.role==='user'?'你':message.role==='system'?'本地任务状态':'序航'}</span><div className={'bubble '+(message.kind==='error'?'error':'')}>{message.text.length>700?<details className="long-message"><summary>{message.text.slice(0,160)}…（展开全文）</summary><p className="message-text">{message.text}</p></details>:<p className="message-text">{message.text}</p>}
          {message.kind==='scan'&&<ScanCard message={message} disabled={disabled} inspect={call=>void inspect(call)}/>}
          {message.kind==='source'&&message.data&&<SourceCard message={message} disabled={locked||!online} show={id=>void showSource(id)} read={url=>void sendWeb('read',url,false)}/>} {(message.kind==='plan'||message.kind==='result')&&message.data&&<EvidenceCard message={message}/>}
        </div></article>)}
        {pendingUser&&<article className="message user"><span className="speaker">你 · 正在处理</span><div className="bubble"><p>{pendingUser}</p></div></article>}
        {!!conversation?.sources?.length&&<details className="saved-sources"><summary>会话来源（最近 {conversation.sources.length} 项）</summary><ul>{conversation.sources.map(s=><li key={s.evidence_id}><button disabled={locked||!online} onClick={()=>void showSource(s.evidence_id)}>{s.title||s.source_url||'错误证据'} · {s.evidence_id.slice(0,12)}</button></li>)}</ul>{conversation.sources_truncated&&<p>仅展示最近来源，较早记录仍可通过会话检索找到。</p>}<button disabled={locked} onClick={()=>{setIntent('ask');setText('');input.current?.focus();}}>询问已有来源</button></details>}
        {source?.cid===conversation?.id&&source&&<section className="source-detail" aria-label="证据详情"><div className="row between"><h3>证据详情</h3><button onClick={()=>setSource(undefined)}>关闭证据</button></div><SourceDetail source={source.value}/></section>}
        {conversation?.operation&&<PlanCard operation={conversation.operation} disabled={disabled} act={kind=>void act(kind)}/>}
        {!!conversation?.operations?.length&&<details className="operation-history"><summary>任务操作历史（最近 {conversation.operations.length} 项）</summary><ol>{conversation.operations.map(op=><li key={op.operation_id}><span>{taskLabels[op.status] ?? op.status}</span><code>版本 {op.revision.slice(0,12)}</code><time>{op.updated_at}</time>{op.can_undo&&<span>可受限撤销</span>}</li>)}</ol>{conversation.operations_truncated&&<p className="muted">仅显示最近操作；历史记录不构成执行或撤销授权。</p>}</details>}
        {phase&&<p role="status" className="progress"><span className="spinner"/>{phase}</p>}
        {!phase&&remoteBusy&&<p role="status" className="progress">本地任务仍在处理中。页面重载不会取消或重发任务，请等待后刷新状态。</p>}
        <div ref={end}/>
      </div></div>
      <section className="composer-area">
        {unread&&<button className="new-messages" onClick={()=>{follow.current=true;setUnread(false);end.current?.scrollIntoView({block:'end'});}}>↓ 查看最新消息</button>}
        {!online&&<div role="status" className="notice row between"><span>本地服务未连接。重新连接不会自动重试文件操作。</span><button disabled={locked} onClick={()=>void reconnect()}>重新连接</button></div>}
        {activeSend&&<div className="row between cancellation"><span>仅可取消模型规划，文件执行阶段不可取消。</span><button disabled={cancelling} onClick={()=>void cancel()}>{cancelling?'正在取消…':'取消规划'}</button></div>}
        {notice&&<p role="alert" className="notice">{notice}</p>}
        {retryable&&<div className="row cancellation"><span>上次规划未完成。主动重试会发起新的模型请求。</span><button disabled={locked||!online} onClick={()=>{submission.current=undefined;setText(retryText!);void send(retryText);}}>重新尝试规划</button></div>}
        {conversation&&<div className="directory-bar"><span>{conversation.grant ? '已授权：'+conversation.grant.root_label+' · 剩余 '+conversation.grant.calls_remaining+' 次只读调用' : '当前未授权目录；历史记录不会恢复目录权限。'}</span><button disabled={locked} onClick={()=>void run('刷新任务事实…',async()=>{accept(await window.orvia.chatGet({id:conversation.id}),conversation.id);})}>刷新状态</button></div>}
        {conversation?.grant&&<div className="tools-row"><button disabled={disabled} onClick={()=>void inspect({tool:'list_directory',arguments:{path:'.',limit:100}})}>目录列表</button><button disabled={disabled} onClick={()=>void inspect({tool:'analyze_directory_space',arguments:{path:'.',top_n:10,min_size:0}})}>空间与大文件</button><input aria-label="文件名搜索" maxLength={100} value={query} onChange={e=>setQuery(e.target.value)} placeholder="文件名" disabled={locked}/><button disabled={disabled||!query.trim()} onClick={()=>void inspect({tool:'search_files',arguments:{path:'.',query:query.trim(),recursive:true,limit:100}})}>搜索</button></div>}
        <form className="composer" onSubmit={e=>{e.preventDefault();void send();}}><label className="intent-label">本次需求<select aria-label="需求类型" disabled={locked} value={intent} onChange={e=>{setIntent(e.target.value as typeof intent);}}><option value="files">文件任务</option><option value="search">搜索网页</option><option value="read">读取网页</option><option value="ask">询问已有来源</option></select></label>
          <textarea ref={input} aria-label="输入需求" aria-describedby="composer-hint" placeholder={intent==='files'?'描述你想整理的文件…':intent==='read'?'输入一个公开网页 URL，例如 https://example.com/':intent==='ask'?'输入要查找的关键词，例如：许可 条件。仅检索本会话已保存来源。':'输入搜索词；发送后交给 Tavily 搜索'} maxLength={inputLimit} value={text} disabled={locked} onChange={e=>setText(e.target.value)} onCompositionStart={()=>{composing.current=true;}} onCompositionEnd={()=>{composing.current=false;}} onKeyDown={e=>{if(submitsMessage(e.key,e.shiftKey,e.nativeEvent.isComposing||composing.current,e.keyCode)){e.preventDefault();void send();}}}/>
          <div className="row between"><button type="button" disabled={locked||!online} onClick={()=>void choose()}>＋ 选择目录</button><div className="row"><span className="muted">{text.length}/{inputLimit}</span><button className="send primary" aria-label="发送" disabled={locked||!text.trim()||text.length>inputLimit||!online}>↑</button></div></div>
        </form><p id="composer-hint" className="privacy">Enter 发送 · Shift+Enter 换行。{intent==='files'?'必要对话和目录元数据交给固定 Main 模型，文件修改须单独审批。':intent==='search'?(settings?.search_available?'Tavily 已配置；只发送本次搜索词，不自动读取结果网页。':'未配置 Tavily，搜索不可用；可选择读取已知公开网页。'):intent==='read'?'只访问你提交的公开 URL，保存正文与来源；不需要目录授权或搜索凭据。':'本地检索当前会话来源，返回原文引用；不联网、不生成模型结论。'}</p>
      </section>
    </main>{showSettings&&<SettingsPanel settings={settings} reload={reloadSettings} close={()=>setShowSettings(false)}/>}
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
