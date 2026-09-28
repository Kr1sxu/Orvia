import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { Conversation, ReadCall } from '../main/chat-contracts';
import type { Reply, Settings } from '../shared/api';
import { SettingsPanel } from './SettingsPanel';
import { PlanCard, ScanCard, EvidenceCard } from './ChatCards';
import './style.css';

function App() {
  const [list, setList] = useState<{id:string;title:string}[]>([]);
  const [conversation, setConversation] = useState<Conversation>();
  const [text, setText] = useState('');
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState('');
  const [notice, setNotice] = useState('');
  const [online, setOnline] = useState(false);
  const [settings, setSettings] = useState<Settings>();
  const [showSettings, setShowSettings] = useState(false);
  const [pendingUser, setPendingUser] = useState('');
  const activeId = useRef<string | undefined>(undefined);
  const working = useRef(false);
  const composing = useRef(false);
  const end = useRef<HTMLDivElement>(null);
  // 同一请求失败后保留请求ID；重发不应导致第二次模型调用或文件计划。
  const submission = useRef<{id:string;text:string;request_id:string} | undefined>(undefined);
  async function reloadSettings() {
    const health = await window.orvia.health(); setOnline(health.ok);
    const reply = await window.orvia.settings(); if (reply.ok) setSettings(reply.result); else setNotice(reply.message);
  }
  async function refreshList() { const reply = await window.orvia.chatList(); if (reply.ok) setList(reply.result.conversations); else setNotice(reply.message); }
  useEffect(() => { void (async () => { try { await reloadSettings(); await refreshList(); } catch { setNotice('本地连接失败，请重新启动应用。'); } })(); }, []);
  useEffect(() => { end.current?.scrollIntoView({block:'end'}); }, [conversation?.messages.length, pendingUser, phase]);
  function accept(reply: Reply<Conversation>, id?: string) {
    if (!reply.ok) { setNotice(reply.message); return false; }
    // 回包只能更新发起请求时的会话，不能覆盖后来选择的会话。
    if (id && activeId.current !== id) return false;
    activeId.current = reply.result.id; setConversation(reply.result); return true;
  }
  async function run(label: string, action: () => Promise<void>) {
    if (working.current) return;
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
  function newChat() { if (working.current) return; activeId.current=undefined; setConversation(undefined);setText('');setQuery('');setNotice('');submission.current=undefined; }
  async function open(id:string) { await run('正在读取历史会话…',async () => {activeId.current=id;setConversation(undefined);setText('');submission.current=undefined;accept(await window.orvia.chatGet({id}),id);}); }
  async function send() {
    const value = text.trim(); if (!value || value.length>2000 || composing.current || working.current) return;
    await run('Main 正在理解需求与收集证据…',async () => {
      const id = activeId.current ?? await create(value); if (!id) return;
      if (submission.current?.id!==id || submission.current.text!==value) submission.current={id,text:value,request_id:crypto.randomUUID()};
      setPendingUser(value);
      const reply = await window.orvia.chatSend(submission.current);
      if (accept(reply,id)) {setText('');submission.current=undefined;}
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
  const disabled=busy||!conversation?.grant;
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><span className="brand-mark">序</span><strong>序航 <small>Orvia</small></strong></div>
      <button className="new-chat" disabled={busy} onClick={newChat}>＋ 新建对话</button><p className="nav-label">最近对话</p>
      <nav aria-label="历史会话">{list.map(item=><button title={item.title} className={conversation?.id===item.id?'selected':''} disabled={busy} key={item.id} onClick={()=>void open(item.id)}>{item.title}</button>)}{!list.length&&<p className="muted">从第一个问题开始。</p>}</nav>
      <div className="sidebar-bottom"><button disabled={busy} onClick={()=>setShowSettings(true)}>⚙ 设置</button><span className="connection"><i className={online?'online':''}/>{online?'本地服务已连接':'本地服务未连接'}</span></div>
    </aside>
    <main className="chat-main"><header className="topbar"><span>{conversation?.title ?? '新对话'}</span><span className="muted">本地文件助手</span></header>
      <div className="message-scroll"><div className="conversation-content">
        {!conversation?.messages.length&&!pendingUser&&<section className="welcome"><span className="welcome-mark">序</span><h1>你好，我是序航 Orvia</h1><p>从一个想法开始，把文件整理得井井有条。</p><div className="suggestions">{['看看目录里有哪些文件','找出占用空间较大的文件','帮我拟定分类整理计划'].map(value=><button key={value} disabled={busy} onClick={()=>setText(value)}>{value}<span>↗</span></button>)}</div></section>}
        {conversation?.messages_truncated&&<p className="muted">为限制通信大小，当前仅显示最近消息；更早记录保留在本地。</p>}
        {conversation?.messages.map(message=><article key={message.id} className={'message '+message.role}><span className="speaker">{message.role==='user'?'你':message.role==='system'?'本地任务状态':'序航'}</span><div className={'bubble '+(message.kind==='error'?'error':'')}><p className="message-text">{message.text}</p>
          {message.kind==='scan'&&<ScanCard message={message} disabled={disabled} inspect={call=>void inspect(call)}/>}
          {(message.kind==='plan'||message.kind==='result')&&message.data&&<EvidenceCard message={message}/>}
        </div></article>)}
        {pendingUser&&<article className="message user"><span className="speaker">你 · 正在处理</span><div className="bubble"><p>{pendingUser}</p></div></article>}
        {conversation?.operation&&<PlanCard operation={conversation.operation} disabled={disabled} act={kind=>void act(kind)}/>}
        {phase&&<p role="status" className="progress"><span className="spinner"/>{phase}</p>}
        <div ref={end}/>
      </div></div>
      <section className="composer-area">
        {notice&&<p role="alert" className="notice">{notice}</p>}
        {conversation&&<div className="directory-bar"><span>{conversation.grant ? '已授权：'+conversation.grant.root_label+' · 剩余 '+conversation.grant.calls_remaining+' 次只读调用' : '当前未授权目录；历史记录不会恢复目录权限。'}</span><button disabled={busy} onClick={()=>void run('刷新任务事实…',async()=>{accept(await window.orvia.chatGet({id:conversation.id}),conversation.id);})}>刷新状态</button></div>}
        {conversation?.grant&&<div className="tools-row"><button disabled={disabled} onClick={()=>void inspect({tool:'list_directory',arguments:{path:'.',limit:100}})}>目录列表</button><button disabled={disabled} onClick={()=>void inspect({tool:'analyze_directory_space',arguments:{path:'.',top_n:10,min_size:0}})}>空间与大文件</button><input aria-label="文件名搜索" maxLength={100} value={query} onChange={e=>setQuery(e.target.value)} placeholder="文件名" disabled={busy}/><button disabled={disabled||!query.trim()} onClick={()=>void inspect({tool:'search_files',arguments:{path:'.',query:query.trim(),recursive:true,limit:100}})}>搜索</button></div>}
        <form className="composer" onSubmit={e=>{e.preventDefault();void send();}}><textarea aria-label="输入需求" placeholder="描述你想做的事，例如：帮我看看这个目录有哪些大文件…" maxLength={2000} value={text} disabled={busy} onChange={e=>setText(e.target.value)} onCompositionStart={()=>{composing.current=true;}} onCompositionEnd={()=>{composing.current=false;}} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing&&!composing.current){e.preventDefault();void send();}}}/>
          <div className="row between"><button type="button" disabled={busy||!online} onClick={()=>void choose()}>＋ 选择目录</button><div className="row"><span className="muted">{text.length}/2000</span><button className="send primary" aria-label="发送" disabled={busy||!text.trim()||!online}>↑</button></div></div>
        </form><p className="privacy">发送将把必要对话和授权目录元数据交给固定 Main 模型。文件修改须单独审批；不会自动上传正文。</p>
      </section>
    </main>{showSettings&&<SettingsPanel settings={settings} reload={reloadSettings} close={()=>setShowSettings(false)}/>}
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
