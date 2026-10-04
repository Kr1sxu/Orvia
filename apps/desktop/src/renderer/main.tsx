import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { Conversation, ReadCall, BrowserEvidence, DocumentEvidence, DocumentPreview, SynthesisPreview, SynthesisSource } from '../main/chat-contracts';
import type { Reply, Settings } from '../shared/api';
import { SettingsPanel } from './SettingsPanel';
import { PlanCard, ScanCard, EvidenceCard } from './ChatCards';
import { SourceCard, SourceDetail } from './SourceCards';
import { DocumentCard, DocumentDetail, ExportPreview, ExportCard } from './DocumentCards';
import { SynthesisPreviewCard, SynthesisResult } from './SynthesisCards';
import { PublicationComposer,PublicationResult } from './PublicationCards';
import { M17Workspace } from './M17Cards';
import { M18Workspace } from './M18Cards';
import {TaskProgress} from './TaskProgress';
import {ConversationList} from './ConversationList';
import {workspaceVisibility} from './workspace-state';
import { nearBottom, submitsMessage, taskLabels } from './chat-state';
import {BrandMark,Icon} from './Visual';
import {AddMaterialMenu} from './AddMaterialMenu';
import {DirectoryAnswer,LiveResult,PartialModelMessage} from './M20Results';
import {newStream,consumeStream,type LiveStream} from './m20-state';
import {chatSynthesisPreviewSchema,chatPublicationPreviewSchema} from '../main/chat-contracts';
import type {Workflow} from '../main/m20-contracts';
import './style.css';

function App() {
  const [list, setList] = useState<import('../main/chat-contracts').ConversationSummary[]>([]);
  const deletedIds=useRef(new Set<string>());
  const [conversation, setConversation] = useState<Conversation>();
  const [text, setText] = useState('');
  const [query, setQuery] = useState('');
  const [streams,setStreams]=useState<Record<string,LiveStream>>({});
  const [attachmentStatus,setAttachmentStatus]=useState<{cid:string;items:{title:string;status:'pending'|'parsing'|'ready'|'failed'|'cancelled'}[]}>();
  const [source,setSource] = useState<{cid:string;value:BrowserEvidence}>();
  const [document,setDocument] = useState<{cid:string;value:DocumentEvidence}>();
  const [preview,setPreview] = useState<{cid:string;value:DocumentPreview}>();
  const [synthesisMode,setSynthesisMode]=useState<'summary'|'answer'>('summary');
  const [synthesisQuestion,setSynthesisQuestion]=useState('请概括所选资料的主要内容、证据和局限。');
  const [selectedSources,setSelectedSources]=useState<SynthesisSource[]>([]);
  const [synthesisPreview,setSynthesisPreview]=useState<{cid:string;value:SynthesisPreview;sources:SynthesisSource[]}>();
  const [publication,setPublication]=useState<{cid:string;message:Conversation['messages'][number];format?:'docx'|'pptx'|'pdf';request_id?:string}>();
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
  const latestResult=useRef<HTMLElement|null>(null),liveResult=useRef<HTMLDivElement|null>(null);
  const resultNodes=useRef(new Map<string,HTMLElement>()),revealSavedResult=useRef<{cid:string;message_id:string}|undefined>(undefined);
  const sourceDetail=useRef<HTMLElement|null>(null),documentDetail=useRef<HTMLElement|null>(null),revealEvidence=useRef<{cid:string;kind:'browser'|'document'}|undefined>(undefined);
  const scroll = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);
  const follow = useRef(true);
  const readingPositions=useRef(new Map<string,number>()),restoreReading=useRef<{id:string;top:number}|undefined>(undefined),historicalView=useRef(false);
  const previousRemoteBusy = useRef(false);
  const drafts=useRef(new Map<string,string>()),draftText=useRef(''),streamValues=useRef<Record<string,LiveStream>>({}),streamRequest=useRef<{id:string;request_id:string}|undefined>(undefined);
  const streamQueue=useRef<{id:string;request_id:string}[]>([]),requestStreams=useRef(new Map<string,LiveStream>());
  const viewEpoch=useRef(0);
  const continueGate=useRef<{id:string;request_id:string}|undefined>(undefined),preparedWorkflow=useRef('');
  const hasChosenView=useRef(false),pendingCid=useRef<string|undefined>(undefined);
  // 同一请求失败后保留请求ID；重发不应导致第二次模型调用或文件计划。
  const submission = useRef<{id:string;text:string;request_id:string} | undefined>(undefined);
  const webSubmission = useRef<{id:string;value:string;intent:string;request_id:string}|undefined>(undefined);
  async function reloadSettings() {
    const health = await window.orvia.health(); setOnline(health.ok);
    const reply = await window.orvia.settings(); if (reply.ok) setSettings(reply.result); else setNotice(reply.message);
  }
  async function refreshList() { try { const reply = await window.orvia.chatList(); if (reply.ok) setList(reply.result.conversations.filter(item=>!deletedIds.current.has(item.id))); else setNotice(reply.message); } finally { setLoadingList(false); } }
  useEffect(() => { void (async () => { try {
    const status=await window.orvia.connectionStatus();
    if(status.ok&&status.result.busy)return;
    await reloadSettings(); await refreshList();
  } catch { setLoadingList(false);setNotice('本地连接失败，请使用重新连接。'); } })(); }, []);
  // 历史加载在绘制前恢复其阅读位置；异步增量与终态只更新事实，不能重新跟随到底部。
  useLayoutEffect(()=>{const target=restoreReading.current;if(target&&conversation?.id===target.id&&scroll.current){scroll.current.scrollTop=target.top;restoreReading.current=undefined;}},[conversation?.id,conversation?.messages]);
  // 仅响应用户本次引用点击；同会话真实回包绘制后一次滚入详情，不改变输入焦点。
  useLayoutEffect(()=>{const target=revealEvidence.current;if(!target||target.cid!==conversation?.id)return;const node=target.kind==='browser'?sourceDetail.current:documentDetail.current;if(node){revealEvidence.current=undefined;follow.current=false;historicalView.current=true;node.scrollIntoView({block:'start'});}},[source,document,conversation?.id]);
  // 显式保存成功后只呈现本次新核验成品，不恢复后台自动跟随或影响另一会话。
  useLayoutEffect(()=>{const target=revealSavedResult.current;if(!target||target.cid!==conversation?.id)return;const node=resultNodes.current.get(target.message_id);if(node?.isConnected){revealSavedResult.current=undefined;node.scrollIntoView({block:'end'});}},[conversation?.id,conversation?.messages]);
  function showLatestResult(){
    const live=streams[conversation?.id??''];
    const savedPartial=live?.stream_id&&conversation?.messages.some(message=>message.kind==='model_partial'&&message.data?.stream_id===live.stream_id);
    const result=live&&(!live.terminal||live.error&&!savedPartial)?liveResult.current:conversation?.workflow?end.current:latestResult.current;
    (result?.isConnected?result:end.current)?.scrollIntoView({block:'end'});
  }
  // 自动跟随直接结果，避免无关执行表单把已核验回答挤出阅读区；历史位置仍由用户掌握。
  useEffect(() => { if (follow.current&&!historicalView.current) showLatestResult(); else setUnread(true); }, [conversation?.messages, pendingUser, streams[conversation?.id??'']]);
  // 增量只更新所属会话缓存；正在阅读别的会话也持续消费和ACK，防止旧任务堵住stdio。
  useEffect(()=>{let stopped=false,pulling=false;async function pull(){
    const target=streamQueue.current[0];if(stopped||pulling||!target)return;pulling=true;
    try{let current=requestStreams.current.get(target.request_id)??newStream(target.id,target.request_id);const reply=await window.orvia.chatStreamPull({...target,after_seq:current.seq});
      if(stopped||!reply.ok)return;
      current=requestStreams.current.get(target.request_id)??current;
      current=reply.result.gap?{...current,error:'流事件存在缺口，请读取已保存事实；不会自动重试。',terminal:true}:consumeStream(current,reply.result.events);
      requestStreams.current.set(target.request_id,current);
      if(streamRequest.current?.request_id===target.request_id){streamValues.current={...streamValues.current,[target.id]:current};setStreams(streamValues.current);}
      if(reply.result.events.length)await window.orvia.chatStreamAck({...target,seq:current.seq});
      // paused继续轮询本地主进程有界缓存，防止旧paused与新接续同批到达时丢失后续ACK。
      // 只处理本次目标对象；等待pull/ACK期间新建的接续目标不能被旧回包移除。
      if(current.terminal&&(!current.paused||current.error))streamQueue.current=streamQueue.current.filter(item=>item!==target);
      else if(streamQueue.current[0]===target&&streamQueue.current.length>1)streamQueue.current=[...streamQueue.current.slice(1),target];
    }catch{const current=requestStreams.current.get(target.request_id);if(current){streamValues.current={...streamValues.current,[target.id]:{...current,error:'连接中断；部分结果待核对，未自动重试。',terminal:true}};setStreams(streamValues.current);}streamQueue.current=[];}
    finally{pulling=false;}}
    const timer=setInterval(()=>void pull(),50);return()=>{stopped=true;clearInterval(timer);};
  },[]);
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
          if(reply.result.materialProcessing)setAttachmentStatus({cid:reply.result.materialProcessing.id,items:reply.result.materialProcessing.items});
          // 重载期间只读主进程状态；请求结束后再读取事实，不重放发送或审批。
          if(reply.result.activeSend&&!activeId.current&&!hasChosenView.current)activeId.current=reply.result.activeSend.id;
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
    if(conversation?.workflow)beginStream(conversation.id,conversation.workflow.request_id);
    setCancelling(true);
    try {
      const reply=await window.orvia.chatCancel(activeSend);
      setNotice(reply.ok ? reply.result.cancelled ? '已请求取消当前只读或模型步骤；请等待确认。不会自动重发。' : '请求已结束或当前阶段不能取消，请刷新任务状态。' : reply.message);
    } catch {setNotice('取消确认失败，请刷新任务状态；不要重复审批。');}
    finally {setCancelling(false);}
  }
  async function reconnect() {
    viewEpoch.current++;
    continueGate.current=undefined;streamRequest.current=undefined;streamQueue.current=[];
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
    if(deletedIds.current.has(reply.result.id))return false;
    // 回包只能更新发起请求时的会话，不能覆盖后来选择的会话。
    if (id && activeId.current !== id) return false;
    activeId.current = reply.result.id; setConversation(reply.result);
    if(continueGate.current?.id===reply.result.id&&!reply.result.workflow)continueGate.current=undefined;
    // 快速审批可能在两次轮询之间完成，直接同步侧栏事实，不能依赖轮询捕获 busy。
    setList(items=>items.map(item=>item.id===reply.result.id?{...item,title:reply.result.title,status:reply.result.status}:item));
    return true;
  }
  function beginStream(id:string,request_id:string){
    const previous=requestStreams.current.get(request_id),live=previous??newStream(id,request_id);
    requestStreams.current.set(request_id,live);
    if(requestStreams.current.size>20){const oldest=requestStreams.current.keys().next().value;if(oldest){requestStreams.current.delete(oldest);streamQueue.current=streamQueue.current.filter(item=>item.request_id!==oldest);}}
    streamValues.current={...streamValues.current,[id]:live};setStreams(streamValues.current);streamRequest.current={id,request_id};
    streamQueue.current=streamQueue.current.filter(item=>item.request_id!==request_id);
    if(!live.terminal||live.paused&&!live.error)streamQueue.current.push({id,request_id});
  }
  function saveDraft(){drafts.current.set(activeId.current??'new',draftText.current);if(activeId.current&&scroll.current)readingPositions.current.set(activeId.current,scroll.current.scrollTop);}
  function changeText(value:string){draftText.current=value;setText(value);}
  function invalidateContinuation(){const gate=continueGate.current;continueGate.current=undefined;if(gate&&conversation?.workflow&&gate.id===conversation.id){beginStream(gate.id,gate.request_id);void window.orvia.chatCancel(gate);}}
  async function continueWorkflow(answer?:string){const id=activeId.current,wf=conversation?.workflow;if(!id||!wf||working.current)return;await run('正在接续同一需求的已授权步骤…',async()=>{
    beginStream(id,wf.request_id);const reply=await window.orvia.chatContinue({id,request_id:wf.request_id,continuation_id:wf.continuation_id,...(answer?{answer}:{})});accept(reply,id);await refreshList();
  });}
  async function run(label: string, action: () => Promise<void>) {
    if (working.current || remoteBusy) return;
    working.current = true; setBusy(true); setPhase(label); setNotice('');
    try { await action(); }
    catch { setNotice('本地通信失败。请刷新会话核对状态，任务步骤不会自动重放。'); }
    finally { working.current = false; setBusy(false); setPhase(''); setPendingUser(''); }
  }
  async function create(title: string) {
    const epoch=viewEpoch.current;
    const reply = await window.orvia.chatCreate({client_request_id:crypto.randomUUID(),title:title.slice(0,80) || '新对话'});
    // 新会话创建回包不能覆盖后来明确选中的视图，也不能清空其草稿或发起原任务。
    if(epoch!==viewEpoch.current){await refreshList();return undefined;}
    if (!accept(reply)) return undefined;
    return reply.ok ? reply.result.id : undefined;
  }
  async function pinConversation(item:import('../main/chat-contracts').ConversationSummary){await run('正在更新置顶…',async()=>{const reply=await window.orvia.chatPin({id:item.id,pinned:!item.pinned});if(!reply.ok)setNotice(reply.message);await refreshList();});}
  async function renameConversation(id:string,title:string){let success=false;await run('正在保存名称…',async()=>{const reply=await window.orvia.chatRename({id,title});if(!reply.ok)setNotice(reply.message);else{success=true;accept(reply,id);}await refreshList();});return success;}
  async function deleteConversation(id:string){await run('等待永久删除确认…',async()=>{
    const reply=await window.orvia.chatDelete({id});
    if(!reply.ok){setNotice(reply.message);await refreshList();return;}
    if(!reply.result.deleted)return;
    // 先退出已删除视图再刷新列表；晚到的旧快照和轮询不能重新挂载此身份。
    deletedIds.current.add(id);if(activeId.current===id)newChat();
    drafts.current.delete(id);readingPositions.current.delete(id);delete streamValues.current[id];setStreams({...streamValues.current});
    streamQueue.current=streamQueue.current.filter(item=>item.id!==id);
    for(const [key,value] of requestStreams.current)if(value.id===id)requestStreams.current.delete(key);
    setPublication(value=>value?.cid===id?undefined:value);
    setList(items=>items.filter(item=>item.id!==id));await refreshList();setNotice('对话及本地消息、证据已永久删除。用户原文件和导出成品未删除。');
  });}
  function newChat() {viewEpoch.current++;saveDraft();invalidateContinuation();hasChosenView.current=true;activeId.current=undefined;setConversation(undefined);changeText(drafts.current.get('new')??'');setQuery('');setNotice('');setSource(undefined);setDocument(undefined);setPreview(undefined);setSynthesisPreview(undefined);setSelectedSources([]);webSubmission.current=undefined;submission.current=undefined;follow.current=true;historicalView.current=false;restoreReading.current=undefined;setUnread(false);}
  async function open(id:string) {viewEpoch.current++;saveDraft();invalidateContinuation();hasChosenView.current=true;activeId.current=id;setConversation(undefined);changeText(drafts.current.get(id)??'');setQuery('');setSource(undefined);setDocument(undefined);setPreview(undefined);setSynthesisPreview(undefined);setSelectedSources([]);webSubmission.current=undefined;submission.current=undefined;follow.current=false;historicalView.current=true;restoreReading.current={id,top:readingPositions.current.get(id)??0};setUnread(false);try{accept(await window.orvia.chatGet({id}),id);}catch{setNotice('读取会话失败，请核对本地连接。');}}
  async function send(retryText?: string) {
    const value = (retryText ?? text).trim(); if (!value || value.length>2000 || composing.current || working.current) return;
    if(conversation?.workflow?.action==='clarification'){await continueWorkflow(value);if(activeId.current===conversation.id)changeText('');return;}
    await run('Main 正在理解需求与收集证据…',async () => {
      const id = activeId.current ?? await create(value); if (!id) return;
      if (submission.current?.id!==id || submission.current.text!==value) submission.current={id,text:value,request_id:crypto.randomUUID()};
      follow.current=true;historicalView.current=false;restoreReading.current=undefined;continueGate.current={id,request_id:submission.current.request_id};beginStream(id,submission.current.request_id);pendingCid.current=id;setPendingUser(value);changeText('');drafts.current.set(id,'');
      const reply = await window.orvia.chatNatural(submission.current);
      if (accept(reply,id)) {submission.current=undefined;}
      else if(!reply.ok) {const latest=await window.orvia.chatGet({id});if(latest.ok){accept(latest,id);if(['interrupted','cancelled'].includes(latest.result.status ?? ''))submission.current=undefined;}}
      await refreshList();
    });
  }
  async function choose() {
    const gate=continueGate.current;
    await run('等待选择并授权本地目录…',async () => {
      const id=activeId.current ?? await create('新对话'); if (!id) return;
      const reply=await window.orvia.chatChooseDirectory({id});
      if (!reply.ok) {setNotice(reply.message);return;}
      if (reply.result.cancelled) {invalidateContinuation();setNotice('已取消选择；原需求保留，没有自动接续。');return;}
      if(reply.result.conversation) accept({ok:true,result:reply.result.conversation},id);
      const wf=reply.result.conversation?.workflow;
      if(gate&&continueGate.current===gate&&activeId.current===id&&wf?.request_id===gate.request_id&&wf.action==='directory'){
        beginStream(id,wf.request_id);accept(await window.orvia.chatContinue({id,request_id:wf.request_id,continuation_id:wf.continuation_id}),id);
      }
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
      if(accept(reply,id)){if(clearComposer)changeText('');webSubmission.current=undefined;}
      else {const latest=await window.orvia.chatGet({id});if(latest.ok)accept(latest,id);}
      await refreshList();
    });
  }
  async function showSource(evidence_id:string) {
    const id=activeId.current;if(!id)return;
    await run('正在读取已保存证据…',async()=>{const reply=await window.orvia.chatBrowserSource({id,evidence_id});if(reply.ok&&activeId.current===id){revealEvidence.current={cid:id,kind:'browser'};setSource({cid:id,value:reply.result});}else if(!reply.ok)setNotice(reply.message);});
  }
  async function attachDocument() {
    const gate=continueGate.current;
    await run('等待选择附件并提取内容…',async()=>{
      const id=activeId.current??await create('新对话');if(!id)return;
      const reply=await window.orvia.chatAddFiles({id,request_id:crypto.randomUUID()});
      if(!reply.ok){setNotice(reply.message);return;}
      if(reply.result.cancelled){invalidateContinuation();setNotice('已取消附件选择；原需求保留，没有自动接续。');}
      else if(reply.result.conversation)accept({ok:true,result:reply.result.conversation},id);
      setAttachmentStatus({cid:id,items:reply.result.items});
      const wf=reply.result.conversation?.workflow;
      if(!reply.result.cancelled&&reply.result.items.every(item=>item.status==='ready')&&gate&&continueGate.current===gate&&activeId.current===id&&wf?.request_id===gate.request_id&&wf.action==='materials'){
        beginStream(id,wf.request_id);accept(await window.orvia.chatContinue({id,request_id:wf.request_id,continuation_id:wf.continuation_id}),id);
      }
      await refreshList();
    });
  }
  async function askDocument(raw:string) {
    const query=raw.trim();if(!query||query.length>200||composing.current)return;
    await run('正在本地检索文档引用…',async()=>{
      const id=activeId.current;if(!id){setNotice('请先添加文档附件。');return;}
      if(webSubmission.current?.id!==id||webSubmission.current.value!==query||webSubmission.current.intent!=='document')webSubmission.current={id,value:query,intent:'document',request_id:crypto.randomUUID()};
      const reply=await window.orvia.chatDocumentAsk({id,query,request_id:webSubmission.current.request_id});
      if(accept(reply,id)){changeText('');webSubmission.current=undefined;}await refreshList();
    });
  }
  async function showDocument(evidence_id:string) {
    const id=activeId.current;if(!id)return;
    await run('正在读取文档证据…',async()=>{
      const reply=await window.orvia.chatDocumentSource({id,evidence_id});
      if(reply.ok&&activeId.current===id){revealEvidence.current={cid:id,kind:'document'};setDocument({cid:id,value:reply.result});setPreview(undefined);}
      else if(!reply.ok)setNotice(reply.message);
    });
  }
  async function previewDocument(format:'md'|'json') {
    const id=activeId.current;if(!id||document?.cid!==id)return;
    const evidence_id=document.value.evidence_id;
    await run('正在生成只读导出预览…',async()=>{
      const reply=await window.orvia.chatDocumentPreview({id,evidence_id,format});
      if(reply.ok&&activeId.current===id)setPreview({cid:id,value:reply.result});else if(!reply.ok)setNotice(reply.message);
    });
  }
  async function exportDocument() {
    const id=activeId.current;if(!id||preview?.cid!==id)return;
    const {evidence_id,format,revision}=preview.value;
    await run('等待确认保存位置并写入导出…',async()=>{
      const reply=await window.orvia.chatDocumentExport({id,evidence_id,format,revision,request_id:crypto.randomUUID()});
      setPreview(undefined);
      if(!reply.ok){setNotice(reply.message+' 再次导出请重新预览。');return;}
      if(reply.result.cancelled)setNotice('已取消保存，未写入导出文件；再次导出请重新预览。');
      else if(reply.result.conversation)accept({ok:true,result:reply.result.conversation},id);
    });
  }
  function toggleSource(item:SynthesisSource){
    setSynthesisPreview(undefined);
    setSelectedSources(current=>current.some(source=>source.kind===item.kind&&source.evidence_id===item.evidence_id)
      ?current.filter(source=>source.kind!==item.kind||source.evidence_id!==item.evidence_id)
      :current.length<3?[...current,item]:current);
  }
  async function prepareSynthesis(){
    const id=activeId.current,question=synthesisQuestion.trim();
    if(!id||!selectedSources.length||!question||question.length>300)return;
    await run('正在计算拟发送的证据片段…',async()=>{
      const reply=await window.orvia.chatSynthesisPreview({id,mode:synthesisMode,question,sources:selectedSources});
      if(reply.ok&&activeId.current===id)setSynthesisPreview({cid:id,value:reply.result,sources:[...selectedSources]});
      else if(!reply.ok)setNotice(reply.message);
    });
  }
  async function generateSynthesis(){
    const shown=synthesisPreview,id=activeId.current;
    if(!shown||!id||shown.cid!==id)return;
    await run('等待正文发送确认及 Main 模型回答…',async()=>{
      let reply;
      const wf=conversation?.workflow,request_id=crypto.randomUUID();beginStream(id,request_id);
      try{reply=await window.orvia.chatSynthesisGenerate({id,mode:shown.value.mode,question:shown.value.question,sources:shown.sources,revision:shown.value.revision,request_id,stream_mode:wf?.action==='stream_fallback'?'confirmed_nonstream':'stream'});}
      finally{setSynthesisPreview(undefined);}
      if(!reply.ok){setNotice(reply.message);const latest=await window.orvia.chatGet({id});if(latest.ok)accept(latest,id);}
      else if(reply.result.cancelled)setNotice('已取消正文发送；未调用模型。');
      else if(reply.result.conversation){accept({ok:true,result:reply.result.conversation},id);if(wf&&activeId.current===id){beginStream(id,wf.request_id);accept(await window.orvia.chatContinue({id,request_id:wf.request_id,continuation_id:wf.continuation_id}),id);}}
      await refreshList();
    });
  }
  // 统一路由只填充并预览已实现业务；敏感操作仍需业务按钮和原生窗口明确批准。
  useEffect(()=>{const wf=conversation?.workflow,id=conversation?.id;if(!wf||!id||busy||remoteBusy||preparedWorkflow.current===wf.continuation_id)return;preparedWorkflow.current=wf.continuation_id;
    if(wf.action==='synthesis'||wf.action==='stream_fallback'&&wf.input?.purpose==='synthesis'){
      const parsed=chatSynthesisPreviewSchema.safeParse({id,mode:wf.input?.mode,question:wf.input?.question,sources:wf.input?.sources});if(!parsed.success){setNotice('资料回答参数不完整，请补充必要信息。');return;}
      setSynthesisMode(parsed.data.mode);setSynthesisQuestion(parsed.data.question);setSelectedSources(parsed.data.sources);
      void run('正在预览此需求将发送的准确片段…',async()=>{const reply=await window.orvia.chatSynthesisPreview(parsed.data);if(reply.ok&&activeId.current===id)setSynthesisPreview({cid:id,value:reply.result,sources:parsed.data.sources});else if(!reply.ok)setNotice(reply.message);});
    }
    if(wf.action==='publication'){
      const parsed=chatPublicationPreviewSchema.safeParse({id,...wf.input});if(!parsed.success){setNotice('成品所需已保存回答或格式缺失，请补充必要信息。');return;}
      const message=conversation.messages.find(item=>item.id===parsed.data.message_id&&item.kind==='synthesis');if(message)setPublication({cid:id,message,format:parsed.data.format,request_id:wf.request_id});
    }
  },[conversation?.workflow?.continuation_id,busy,remoteBusy]);
  async function removeMaterial(kind:'document'|'browser',evidence_id:string){const id=activeId.current;if(!id)return;invalidateContinuation();setSynthesisPreview(undefined);setPreview(undefined);setPublication(undefined);await run('正在解除本次需求的资料关联…',async()=>acceptVoid(await window.orvia.chatMaterialRemove({id,kind,evidence_id}),id));}
  async function revokeDirectory(){const id=activeId.current;if(!id)return;invalidateContinuation();setSynthesisPreview(undefined);await run('正在撤销目录授权…',async()=>acceptVoid(await window.orvia.chatRevoke({id}),id));}
  function acceptVoid(reply:Reply<Conversation>,id:string){accept(reply,id);}
  async function completeNativeStep(){const id=conversation?.id,wf=conversation?.workflow;if(!id||!wf||activeId.current!==id)return false;beginStream(id,wf.request_id);const reply=await window.orvia.chatContinue({id,request_id:wf.request_id,continuation_id:wf.continuation_id});accept(reply,id);await refreshList();return reply.ok&&reply.result.workflow?.continuation_id!==wf.continuation_id;}
  async function confirmFallback(){const id=activeId.current,wf=conversation?.workflow;if(!id||wf?.action!=='stream_fallback')return;await run('等待明确批准同模型非流式新请求…',async()=>{beginStream(id,wf.request_id);const reply=await window.orvia.chatFallbackConfirm({id,request_id:wf.request_id,continuation_id:wf.continuation_id});if(!reply.ok)setNotice(reply.message);else if(reply.result.cancelled)setNotice('未批准降级，未发新请求。');else if(reply.result.conversation)accept({ok:true,result:reply.result.conversation},id);});}
  async function cancelWorkflow(){const id=conversation?.id,wf=conversation?.workflow;if(!id||!wf)return;continueGate.current=undefined;beginStream(id,wf.request_id);const reply=await window.orvia.chatCancel({id,request_id:wf.request_id});if(!reply.ok)setNotice(reply.message);accept(await window.orvia.chatGet({id}),id);}
  async function act(kind:'approve'|'resume'|'undo') {
    const op=conversation?.operation,id=activeId.current;if(!op||!id)return;
    await run(kind==='approve'?'正在审批、执行并核验此版本…':kind==='resume'?'正在核验中断任务…':'正在核验并撤销最近变更…',async()=>{
      const input={id,operation_id:op.operation_id,revision:op.revision};
      const reply=await (kind==='approve'?window.orvia.chatApprove(input):kind==='resume'?window.orvia.chatResume(input):window.orvia.chatUndo(input));
      accept(reply,id);
      // 即使动作返回错误也重读账本，避免部分完成/撤销仍显示旧状态。
      if(!reply.ok) {const latest=await window.orvia.chatGet({id});if(latest.ok)accept(latest,id);}
      if(reply.ok&&kind==='approve'&&conversation?.workflow?.action==='files'&&reply.result.operation?.status==='completed')await completeNativeStep();
    });
  }
  const locked=busy||remoteBusy;
  const workspaces=workspaceVisibility(conversation);
  const inputLimit=2000;
  const disabled=locked||!conversation?.grant||!online;
  const lastMessage=conversation?.messages.at(-1);
  const lastUser=conversation?.messages.slice().reverse().find(message=>message.role==='user');
  // 网页请求中断不能让“重试规划”错用更早的文件需求。
  const retryText=lastUser?.kind==='text'?lastUser.text:undefined;
  const retryable=!!retryText&&lastMessage?.kind==='error'&&['MODEL_UNAVAILABLE','MODEL_TIMEOUT','MISSING_CREDENTIAL','INVALID_PROPOSAL','REQUEST_INTERRUPTED','REQUEST_CANCELLED'].includes(String(lastMessage.data?.code));
  return <div className="app-shell">
    {/* 原生按钮覆盖在此拖动区右侧；保留42px窗口操作空间，品牌集中在侧栏。 */}
    <header className="window-titlebar" aria-label="窗口拖动区域"/>
    <aside className="sidebar"><div className="brand"><BrandMark/><strong>序航 <small>Orvia</small></strong></div>
      <button className="new-chat" onClick={newChat}><Icon name="plus"/>新建对话</button><p className="nav-label">最近对话</p>
      <ConversationList items={list} current={conversation?.id} loading={loadingList} disabled={locked||!online} open={id=>void open(id)} pin={pinConversation} rename={renameConversation} remove={deleteConversation}/>
      <div className="sidebar-bottom"><button disabled={locked} onClick={()=>setShowSettings(true)}><Icon name="settings"/>设置</button><span className="connection"><i className={online?'online':''}/>{online?'本地服务已连接':'本地服务未连接'}</span></div>
    </aside>
    <main className="chat-main"><header className="topbar"><span>{conversation?.title ?? '新对话'}</span><span className="badge" data-status={locked?'running':conversation?.status??'draft'} aria-live="polite">{locked?'处理中':taskLabels[conversation?.status ?? 'draft'] ?? '草稿'}</span></header>
      <div className="message-scroll" ref={scroll} tabIndex={0} aria-label="对话消息" onScroll={()=>{const el=scroll.current;if(el){if(activeId.current)readingPositions.current.set(activeId.current,el.scrollTop);follow.current=!historicalView.current&&nearBottom(el.scrollTop,el.clientHeight,el.scrollHeight);if(follow.current)setUnread(false);}}}><div className="conversation-content">
        {!conversation?.messages.length&&!pendingUser&&!locked&&<section className="welcome"><BrandMark className="welcome-mark"/><h1>你好，我是序航 Orvia</h1><p>从一个想法开始，清晰安排每一步。</p><div className="suggestions">{['看看目录里有哪些文件','总结这份文档','读取这个网页并提炼重点'].map(value=><button key={value} disabled={locked} onClick={()=>{changeText(value);input.current?.focus();}}>{value}<span><Icon name="arrow"/></span></button>)}</div></section>}
        {conversation?.messages_truncated&&<p className="muted">为限制通信大小，当前仅显示最近消息；更早记录保留在本地。</p>}
        {conversation?.messages.map(message=><article key={message.id} ref={node=>{if(node&&message.role!=='user'&&['directory_result','scan','natural_answer','model_partial','synthesis','publication','result','export'].includes(message.kind)){latestResult.current=node;resultNodes.current.set(message.id,node);}else if(!node)resultNodes.current.delete(message.id);}} className={'message '+message.role}><span className="speaker">{message.role==='user'?'你':message.role==='system'?'本地任务状态':'序航'}</span><div className={'bubble '+(message.kind==='error'?'error':'')}>{message.text.length>700?<details className="long-message"><summary>{message.text.slice(0,160)}…（展开全文）</summary><p className="message-text">{message.text}</p></details>:<p className="message-text">{message.text}</p>}
          {(message.kind==='scan'||message.kind==='directory_result')&&<>{message.data?.scan_id?<DirectoryAnswer cid={conversation.id} message={message} disabled={!online}/>:<ScanCard message={message} disabled={disabled} inspect={call=>void inspect(call)}/>}</>}
          {message.kind==='document'&&message.data&&<DocumentCard message={message} disabled={locked||!online} show={id=>void showDocument(id)}/>}
          {message.kind==='export'&&message.data&&<ExportCard message={message} disabled={locked||!online} show={id=>void showDocument(id)}/>}
          {message.kind==='source'&&message.data&&<SourceCard message={message} disabled={locked||!online} show={id=>void showSource(id)} read={url=>void sendWeb('read',url,false)}/>} {(message.kind==='plan'||message.kind==='result')&&message.data&&<EvidenceCard message={message}/>}
          {message.kind==='synthesis'&&<SynthesisResult message={message} disabled={locked||!online} show={(kind,id)=>void (kind==='document'?showDocument(id):showSource(id))} compose={item=>setPublication({cid:conversation!.id,message:item})}/>}
          {message.kind==='publication'&&<PublicationResult message={message}/>}
          {message.kind==='model_partial'&&<PartialModelMessage message={message}/>}
        </div></article>)}
        {pendingUser&&pendingCid.current===conversation?.id&&<article className="message user"><span className="speaker">你 · 正在处理</span><div className="bubble"><p>{pendingUser}</p></div></article>}
        {conversation&&streams[conversation.id]&&(!streams[conversation.id].terminal||streams[conversation.id].error&&!conversation.messages.some(message=>message.kind==='model_partial'&&message.data?.stream_id===streams[conversation.id].stream_id))&&<div ref={liveResult}><LiveResult stream={streams[conversation.id]}/></div>}
        {conversation?.task_progress&&<TaskProgress progress={conversation.task_progress}/>}
        {conversation?.workflow&&<section className="source-detail" aria-label="当前需求待办"><h3>{conversation.workflow.question}</h3><p>{conversation.workflow.action==='task_decision'?'当前目标需要你选择处理方式，剩余目标仍然保留。':conversation.workflow.reason}</p>{conversation.workflow.choices?.map(choice=><button key={choice.id} disabled={locked} onClick={()=>void continueWorkflow(choice.id)}>{choice.label}</button>)}{['directory','materials'].includes(conversation.workflow.action)&&<p>通过下方“＋”添加必要资料后，将接续这条需求。</p>}{conversation.workflow.action==='task_decision'?<button disabled={locked} onClick={()=>void continueWorkflow('accept_limit')}>接受此项未完成或受限范围，继续</button>:conversation.workflow.action==='stream_fallback'?conversation.workflow.input?.purpose!=='synthesis'&&<button disabled={locked} onClick={()=>void confirmFallback()}>原生确认同模型非流式新请求</button>:<button disabled={locked} onClick={()=>void continueWorkflow()}>明确继续此需求</button>}<button disabled={locked} onClick={()=>void cancelWorkflow()}>取消此需求</button></section>}
        {!!conversation?.sources?.length&&<details className="saved-sources"><summary>会话来源（最近 {conversation.sources.length} 项）</summary><ul>{conversation.sources.map(s=><li key={s.evidence_id}><button disabled={locked||!online} onClick={()=>void showSource(s.evidence_id)}>{s.title||s.source_url||'错误证据'} · {s.evidence_id.slice(0,12)}</button></li>)}</ul>{conversation.sources_truncated&&<p>仅展示最近来源，较早记录仍可通过会话检索找到。</p>}<button onClick={()=>{changeText('在已有来源中查找：');input.current?.focus();}}>询问已有来源</button></details>}
        {source?.cid===conversation?.id&&source&&<section ref={sourceDetail} className="source-detail" aria-label="证据详情"><div className="row between"><h3>证据详情</h3><button onClick={()=>setSource(undefined)}>关闭证据</button></div><SourceDetail source={source.value}/></section>}
        {!!conversation?.documents?.length&&<details className="saved-sources"><summary>会话文档（最近 {conversation.documents.length} 项）</summary><ul>{conversation.documents.map(item=><li key={item.evidence_id}><button disabled={locked||!online} onClick={()=>void showDocument(item.evidence_id)}>{item.title} · {item.evidence_id.slice(0,12)}</button></li>)}</ul>{conversation.documents_truncated&&<p>文档目录已截断，较早文档可通过关键词检索。</p>}<button onClick={()=>{changeText('总结这份文档');input.current?.focus();}}>询问文档</button></details>}
        {document&&document.cid===conversation?.id&&<section ref={documentDetail} className="source-detail" aria-label="文档证据详情"><div className="row between"><h3>文档证据详情</h3><button onClick={()=>{setDocument(undefined);setPreview(undefined);}}>关闭文档证据</button></div><DocumentDetail source={document.value}/><div className="row"><button disabled={locked||!online} onClick={()=>void previewDocument('md')}>预览 Markdown 导出</button><button disabled={locked||!online} onClick={()=>void previewDocument('json')}>预览 JSON 导出</button></div></section>}
        {preview&&preview.cid===conversation?.id&&<ExportPreview preview={preview.value} disabled={locked||!online} save={()=>void exportDocument()}/>}
        {conversation&&!!((conversation.documents?.length??0)+(conversation.sources?.length??0))&&<details className="source-detail synthesis-select" aria-label="生成式文档与来源回答" open={['synthesis','stream_fallback'].includes(conversation.workflow?.action??'')||undefined}><summary>选择资料版本与生成要求</summary>
          <h3>模型理解已保存资料</h3><p>可以直接说出总结或问题；此处也可明确选择当前会话的1–3个版本，先预览实际发送片段。</p>
          <fieldset><legend>选择证据版本</legend>{[
            ...(conversation.documents??[]).map(item=>({kind:'document' as const,evidence_id:item.evidence_id,title:item.title})),
            ...(conversation.sources??[]).filter(item=>!!item.content?.trim()&&!item.error).map(item=>({kind:'browser' as const,evidence_id:item.evidence_id,title:item.title||item.source_url||'网页来源'})),
          ].map(item=><label key={item.kind+item.evidence_id} className="synthesis-choice"><input type="checkbox" disabled={locked||!online||selectedSources.length>=3&&!selectedSources.some(source=>source.kind===item.kind&&source.evidence_id===item.evidence_id)} checked={selectedSources.some(source=>source.kind===item.kind&&source.evidence_id===item.evidence_id)} onChange={()=>toggleSource({kind:item.kind,evidence_id:item.evidence_id})}/>{item.kind==='document'?'文档':'网页'} · {item.title} · {item.evidence_id.slice(0,12)}</label>)}</fieldset>
          <label>生成类型<select aria-label="生成类型" disabled={locked} value={synthesisMode} onChange={e=>{setSynthesisMode(e.target.value as 'summary'|'answer');setSynthesisPreview(undefined);}}><option value="summary">摘要</option><option value="answer">多来源回答</option></select></label>
          <label>摘要要求或问题<textarea aria-label="摘要要求或问题" maxLength={300} disabled={locked} value={synthesisQuestion} onChange={e=>{setSynthesisQuestion(e.target.value);setSynthesisPreview(undefined);}}/></label>
          <button disabled={locked||!online||!selectedSources.length||!synthesisQuestion.trim()} onClick={()=>void prepareSynthesis()}>预览拟发送片段</button>
        </details>}
        {synthesisPreview&&synthesisPreview.cid===conversation?.id&&<SynthesisPreviewCard preview={synthesisPreview.value} disabled={locked||!online} close={()=>setSynthesisPreview(undefined)} confirm={()=>void generateSynthesis()}/>}
        {publication&&publication.cid===conversation?.id&&<PublicationComposer key={publication.message.id+'-'+(publication.format??'docx')} cid={publication.cid} message={publication.message} initialFormat={publication.format} disabled={locked||!online} close={()=>setPublication(undefined)} notice={setNotice} saved={(reply,id)=>{if(reply.ok&&activeId.current===id){const fact=reply.result.messages.slice().reverse().find(message=>message.kind==='publication');if(fact)revealSavedResult.current={cid:id,message_id:fact.id};}accept(reply,id);void refreshList();if(activeId.current===id&&conversation?.workflow?.action==='publication')void completeNativeStep();}}/>}
        {conversation&&(workspaces.development||workspaces.cleanup)&&<M17Workspace key={conversation.id} cid={conversation.id} visible={workspaces} history={conversation.workspace_history} workflow={conversation.workflow??undefined} completed={completeNativeStep} authorized={!!conversation.grant} disabled={locked||!online} messages={conversation.messages} availableSources={[...(conversation.documents??[]).map(item=>({kind:'document' as const,evidence_id:item.evidence_id,title:item.title})),...(conversation.sources??[]).filter(item=>!!item.content&&!item.error).map(item=>({kind:'browser' as const,evidence_id:item.evidence_id,title:item.title||item.source_url||'网页来源'}))]} notice={setNotice} refresh={async()=>{accept(await window.orvia.chatGet({id:conversation.id}),conversation.id);await refreshList();}}/>}
        {conversation&&(workspaces.script||workspaces.desktop||workspaces.browser)&&<M18Workspace key={`m18-${conversation.id}`} cid={conversation.id} visible={workspaces} workflow={conversation.workflow??undefined} completed={completeNativeStep} authorized={!!conversation.grant} disabled={locked||!online} notice={setNotice} refresh={async()=>{accept(await window.orvia.chatGet({id:conversation.id}),conversation.id);await refreshList();}}/>}
        {conversation?.operation&&<PlanCard operation={conversation.operation} disabled={disabled} act={kind=>void act(kind)}/>}
        {!!conversation?.operations?.length&&<details className="operation-history"><summary>任务操作历史（最近 {conversation.operations.length} 项）</summary><ol>{conversation.operations.map(op=><li key={op.operation_id}><span>{taskLabels[op.status] ?? op.status}</span><code>版本 {op.revision.slice(0,12)}</code><time>{op.updated_at}</time>{op.can_undo&&<span>可受限撤销</span>}</li>)}</ol>{conversation.operations_truncated&&<p className="muted">仅显示最近操作；历史记录不构成执行或撤销授权。</p>}</details>}
        {phase&&<p role="status" className="progress"><span className="spinner"/>{phase}</p>}
        {!phase&&remoteBusy&&<p role="status" className="progress">本地任务仍在处理中。页面重载不会取消或重发任务，请等待后刷新状态。</p>}
        <div ref={end}/>
      </div></div>
      <section className="composer-area">
        {unread&&<button className="new-messages" onClick={()=>{historicalView.current=false;follow.current=true;setUnread(false);showLatestResult();}}><Icon name="down"/>查看最新消息</button>}
        {!online&&<div role="status" className="notice row between"><span>本地服务未连接。重新连接不会自动重试任务步骤。</span><button disabled={locked} onClick={()=>void reconnect()}>重新连接</button></div>}
        {activeSend&&<div className="row between cancellation"><span>可取消当前只读、解析或模型步骤；写操作须按各自账本核对。</span><button disabled={cancelling} onClick={()=>void cancel()}>{cancelling?'正在取消…':'取消当前步骤'}</button></div>}
        {notice&&<p role="alert" className="notice">{notice}</p>}
        {retryable&&<div className="row cancellation"><span>上次规划未完成。主动重试会发起新的模型请求。</span><button disabled={locked||!online} onClick={()=>{submission.current=undefined;setText(retryText!);void send(retryText);}}>重新尝试规划</button></div>}
        {conversation&&<div className="directory-bar"><span>{conversation.grant ? '已授权：'+conversation.grant.root_label+' · 剩余 '+conversation.grant.calls_remaining+' 次只读调用' : '当前未授权目录；历史记录不会恢复目录权限。'}</span><div className="row">{conversation.grant&&<button disabled={locked} onClick={()=>void revokeDirectory()}>撤销目录授权</button>}<button onClick={()=>void window.orvia.chatGet({id:conversation.id}).then(reply=>accept(reply,conversation.id))}>刷新状态</button></div></div>}
        {!!conversation?.materials?.length&&<section className="material-strip" aria-label="本次需求资料"><span>本次资料 · 本地添加不等于云端发送</span>{conversation.materials.map(item=><div className="row" key={item.kind+item.evidence_id}><span>{item.title} · {item.status==='ready'?'已解析／保存':'解析失败'}</span><button disabled={locked} onClick={()=>void removeMaterial(item.kind,item.evidence_id)}>从本次需求移除</button></div>)}</section>}
        {attachmentStatus?.cid===conversation?.id&&attachmentStatus&&<p role="status">{attachmentStatus.items.map(item=>item.title+'：'+({ready:'本机解析返回',failed:'失败',pending:'等待解析',parsing:'本机解析中',cancelled:'已取消／未继续解析'}[item.status])).join('；')}</p>}
        {conversation?.grant&&<div className="tools-row"><button disabled={disabled} onClick={()=>void inspect({tool:'list_directory',arguments:{path:'.',limit:100}})}>目录列表</button><button disabled={disabled} onClick={()=>void inspect({tool:'analyze_directory_space',arguments:{path:'.',top_n:10,min_size:0}})}>空间与大文件</button><input aria-label="文件名搜索" maxLength={100} value={query} onChange={e=>setQuery(e.target.value)} placeholder="文件名" disabled={locked}/><button disabled={disabled||!query.trim()} onClick={()=>void inspect({tool:'search_files',arguments:{path:'.',query:query.trim(),recursive:true,limit:100}})}>搜索</button></div>}
        <form className="composer" onSubmit={e=>{e.preventDefault();if(!locked)void send();}}>
          <textarea ref={input} aria-label="输入需求" aria-describedby="composer-hint" placeholder="你想做些什么" maxLength={inputLimit} value={text} onChange={e=>changeText(e.target.value)} onCompositionStart={()=>{composing.current=true;}} onCompositionEnd={()=>{composing.current=false;}} onKeyDown={e=>{if(!locked&&submitsMessage(e.key,e.shiftKey,e.nativeEvent.isComposing||composing.current,e.keyCode)){e.preventDefault();void send();}}}/>
          <div className="row between"><AddMaterialMenu disabled={locked||!online} files={()=>void attachDocument()} directory={()=>void choose()}/><div className="row"><span className="muted">{text.length}/{inputLimit}</span><button className="send primary" aria-label="发送" disabled={locked||!text.trim()||text.length>inputLimit||!online}><Icon name="send"/></button></div></div>
        </form><p id="composer-hint" className="privacy">Enter 发送 · Shift+Enter 换行。资料在本机解析；正文上云先预览并原生确认。写入、执行和实际外发各有独立审批。</p>
      </section>
    </main>{showSettings&&<SettingsPanel settings={settings} reload={reloadSettings} close={()=>setShowSettings(false)}/>}
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
