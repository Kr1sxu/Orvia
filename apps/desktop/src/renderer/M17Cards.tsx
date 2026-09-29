import React,{useState} from 'react';
import type {ChatMessage,CleanupPlan,DevelopmentContext,DevelopmentDraft,SynthesisSource} from '../main/chat-contracts';

const bytes=(value:number)=>value>=1024*1024?`${(value/1024/1024).toFixed(1)} MiB`:value>=1024?`${(value/1024).toFixed(1)} KiB`:`${value} B`;

/** 结构化页面由 React 转义呈现；绝不把生成的 HTML/JS 注入 Orvia 窗口。 */
function PrototypePreview({draft}:{draft:DevelopmentDraft}){
  const spec=draft.prototype;
  const [active,setActive]=useState(spec?.pages[0]?.id??'');
  const [value,setValue]=useState('');
  const [feedback,setFeedback]=useState('');
  if(!spec)return null;
  const page=spec.pages.find(item=>item.id===active)??spec.pages[0];
  return <section className="m17-prototype" aria-label="原型受限预览"><div className="row between"><strong>{spec.title}</strong><small>演示数据 · 未连接真实业务</small></div>
    <h4>{page.title}</h4><p>{page.body}</p><nav className="row">{page.buttons.map((button,index)=><button key={index} type="button" onClick={()=>{setActive(button.target);setValue('');setFeedback('');}}>{button.label}</button>)}</nav>
    {page.form&&<form onSubmit={event=>{event.preventDefault();if(value.trim())setFeedback(`${page.form!.success}（演示反馈，未发送数据）`);}}><label>{page.form.label}<input required maxLength={100} value={value} onChange={event=>setValue(event.target.value)}/></label><button type="submit">提交演示</button><p role="status">{feedback}</p></form>}
    <small>此预览由固定组件呈现页面导航和表单反馈，不执行生成源码；源码请逐文件查看并确认写入。</small>
  </section>;
}

export function M17Workspace({cid,authorized,disabled,messages,availableSources,notice,refresh}:{cid:string;authorized:boolean;disabled:boolean;messages:ChatMessage[];availableSources:{kind:'document'|'browser';evidence_id:string;title:string}[];notice:(value:string)=>void;refresh:()=>Promise<void>}){
  const [kind,setKind]=useState<'code'|'prototype'>('code');
  const [stack,setStack]=useState<'react-vite'|'web-native'>('react-vite');
  const [requirement,setRequirement]=useState('');
  const [paths,setPaths]=useState('');
  const [selectedSources,setSelectedSources]=useState<SynthesisSource[]>([]);
  const [resultMessageId,setResultMessageId]=useState<string|null>(null);
  const [context,setContext]=useState<DevelopmentContext>();
  const [draft,setDraft]=useState<DevelopmentDraft>();
  const [plan,setPlan]=useState<CleanupPlan>();
  const [selected,setSelected]=useState<number[]>([]);
  const [working,setWorking]=useState(false);
  const blocked=disabled||working;
  const chosenPaths=paths.split(/[\n,]/).map(value=>value.trim()).filter(Boolean);
  async function guard(action:()=>Promise<void>){setWorking(true);try{await action();}catch{notice('本次操作未完成，请刷新草稿或计划并核对现场。');}finally{setWorking(false);}}
  async function previewContext(){await guard(async()=>{
    const reply=await window.orvia.developmentContext({id:cid,requirement:requirement.trim(),paths:chosenPaths,sources:selectedSources,result_message_id:resultMessageId});
    if(reply.ok){setContext(reply.result);setDraft(undefined);}else notice(reply.message);
  });}
  async function generate(){if(!context)return;await guard(async()=>{
    const reply=await window.orvia.developmentGenerate({id:cid,paths:chosenPaths,sources:selectedSources,result_message_id:resultMessageId,kind,stack:kind==='prototype'?'web-native':stack,requirement:requirement.trim(),context_revision:context.revision,request_id:crypto.randomUUID()});
    setContext(undefined);
    if(!reply.ok)notice(reply.message);else if(reply.result.cancelled)notice('已取消发送，未调用 Computer 模型。');
    else if(reply.result.draft){setDraft(reply.result.draft);await refresh();}
  });}
  async function loadDraft(id:string){await guard(async()=>{const reply=await window.orvia.developmentDraft({id:cid,draft_id:id});if(reply.ok)setDraft(reply.result);else notice(reply.message);});}
  async function apply(index:number){if(!draft)return;await guard(async()=>{
    const reply=await window.orvia.developmentApply({id:cid,draft_id:draft.draft_id,revision:draft.revision,index});
    if(!reply.ok)notice(reply.message);else if(reply.result.cancelled)notice('已取消写入。');
    else if(reply.result.draft){setDraft(reply.result.draft);await refresh();}
  });}
  async function scan(){await guard(async()=>{const reply=await window.orvia.cleanupScan({id:cid});if(reply.ok){setPlan(reply.result);setSelected(reply.result.entries.map(item=>item.index));await refresh();}else notice(reply.message);});}
  async function loadPlan(id:string){await guard(async()=>{const reply=await window.orvia.cleanupPlan({id:cid,plan_id:id});if(reply.ok){setPlan(reply.result);setSelected(reply.result.entries.filter(item=>item.status==='pending').map(item=>item.index));}else notice(reply.message);});}
  async function execute(){if(!plan)return;await guard(async()=>{
    const reply=await window.orvia.cleanupExecute({id:cid,plan_id:plan.plan_id,revision:plan.revision,indices:selected});
    if(!reply.ok)notice(reply.message);else if(reply.result.cancelled)notice('已取消隔离；未移动文件。');
    else if(reply.result.plan){setPlan(reply.result.plan);setSelected([]);await refresh();}
  });}
  async function restore(index:number){if(!plan)return;await guard(async()=>{
    const reply=await window.orvia.cleanupRestore({id:cid,plan_id:plan.plan_id,index});
    if(!reply.ok)notice(reply.message);else if(reply.result.cancelled)notice('已取消恢复。');
    else if(reply.result.plan){setPlan(reply.result.plan);await refresh();}
  });}
  const recentDrafts=messages.filter(item=>item.kind==='development'&&typeof item.data?.draft_id==='string');
  const recentPlans=messages.filter(item=>item.kind==='cleanup'&&typeof item.data?.plan_id==='string');
  return <section className="m17-workspace" aria-label="代码、原型和系统清理">
    <details><summary>代码生成与网页原型</summary>
      <p>固定 Computer 模型只生成待审查草稿。支持 TS/React（Vite）与原生网页；最多 12 个文本文件、合计 64 KiB。选择已授权项目中的最多 3 个相对路径作为上下文；目录授权本身不上传正文。</p>
      <label>交付类型<select value={kind} disabled={blocked} onChange={event=>{setKind(event.target.value as typeof kind);setContext(undefined);setDraft(undefined);}}><option value="code">代码文件</option><option value="prototype">可交互网页原型</option></select></label>
      {kind==='code'&&<label>语言与框架<select value={stack} disabled={blocked} onChange={event=>{setStack(event.target.value as typeof stack);setContext(undefined);}}><option value="react-vite">TypeScript / React / Vite</option><option value="web-native">HTML / CSS / JavaScript</option></select></label>}
      <label>需求<textarea aria-label="代码或原型需求" maxLength={1200} value={requirement} disabled={blocked} onChange={event=>{setRequirement(event.target.value);setContext(undefined);}}/></label>
      <label>明确选择的上下文相对路径（逗号或换行分隔，最多 3 个；可留空）<textarea aria-label="代码上下文路径" value={paths} disabled={blocked} onChange={event=>{setPaths(event.target.value);setContext(undefined);}}/></label>
      {!!availableSources.length&&<fieldset><legend>可选当前会话原文证据（最多 2 个，复用 M06 检索定位）</legend>{availableSources.map(item=><label key={item.kind+item.evidence_id}><input type="checkbox" disabled={blocked||selectedSources.length>=2&&!selectedSources.some(value=>value.kind===item.kind&&value.evidence_id===item.evidence_id)} checked={selectedSources.some(value=>value.kind===item.kind&&value.evidence_id===item.evidence_id)} onChange={()=>{setSelectedSources(values=>values.some(value=>value.kind===item.kind&&value.evidence_id===item.evidence_id)?values.filter(value=>value.kind!==item.kind||value.evidence_id!==item.evidence_id):[...values,{kind:item.kind,evidence_id:item.evidence_id}]);setContext(undefined);}}/>{item.kind==='document'?'文档':'网页'} · {item.title} · {item.evidence_id.slice(0,12)}</label>)}</fieldset>}
      {!!messages.filter(item=>item.kind==='synthesis'||item.kind==='publication').length&&<label>可选一条已保存 M15 回答或 M16 引用记录<select aria-label="代码已保存结果" value={resultMessageId??''} disabled={blocked} onChange={event=>{setResultMessageId(event.target.value||null);setContext(undefined);}}><option value="">不使用</option>{messages.filter(item=>item.kind==='synthesis'||item.kind==='publication').map(item=><option key={item.id} value={item.id}>{item.kind==='synthesis'?'M15 回答':'M16 简报引用'} · {item.id.slice(0,8)}</option>)}</select></label>}
      <button disabled={blocked||!authorized||!requirement.trim()||chosenPaths.length>3} onClick={()=>void previewContext()}>预览拟发送上下文</button>
      {!authorized&&<p role="status">请先使用下方“选择目录”授权项目根。</p>}
      {context&&<section className="m17-context" aria-label="拟发送代码上下文"><h4>将向固定 Computer 发送的内容</h4><p>需求：{requirement}</p>
        {context.files.map(file=><details key={file.path}><summary>{file.path} · SHA256 {file.sha256.slice(0,12)}</summary><pre>{file.content}</pre></details>)}
        {context.fragments.map(fragment=><details key={fragment.citation}><summary>{fragment.kind} · {fragment.locator} · {fragment.citation}</summary><pre>{fragment.text}</pre></details>)}
        {context.saved_result&&<details><summary>已保存结果及原始引用（M16 仅追溯其 M15 原回答）</summary><pre>{context.saved_result.answer}{'\n'}{context.saved_result.claims.map(item=>`${item.kind}: ${item.text} [${item.citations.join(', ')}]`).join('\n')}</pre><small>{context.saved_result.note}</small></details>}
        {!context.files.length&&!context.fragments.length&&!context.saved_result&&<p>未选择资料；只发送需求文字。</p>}
        <button className="primary" disabled={blocked||!requirement.trim()} onClick={()=>void generate()}>原生确认后生成草稿</button></section>}
      {!!recentDrafts.length&&<details><summary>已保存草稿</summary>{recentDrafts.map(item=><button key={item.id} disabled={blocked} onClick={()=>void loadDraft(String(item.data?.draft_id))}>查看 {String(item.data?.kind)} 草稿 {String(item.data?.draft_id).slice(0,8)}</button>)}</details>}
      {draft&&<section aria-label="代码草稿差异"><h4>{draft.kind==='prototype'?'网页原型':'代码'}草稿 · {draft.stack} · 版本 {draft.revision.slice(0,12)}</h4><p>生成成功 ≠ 静态检查通过 ≠ 实际运行通过。未自动运行代码、安装依赖或部署。</p>
        {draft.kind==='prototype'&&<PrototypePreview draft={draft}/>}
        {draft.files.map(file=><details key={file.index} open={file.index===0}><summary>{file.operation==='modify'?'修改':'新建'} {file.path} · {file.status}</summary><h5>逐文件差异</h5><pre>{file.diff}</pre><details><summary>完整可编辑源码</summary><pre>{file.content}</pre></details><button disabled={blocked||file.status!=='pending'} onClick={()=>void apply(file.index)}>确认此文件并写入</button></details>)}
      </section>}
    </details>
    <details><summary>系统清理：旧临时文件隔离</summary><p>只看当前用户 Temp 顶层超过 30 天的 .tmp/.log 普通文件；系统目录、注册表、链接和占用文件均不处理。先扫描再逐项审批。</p>
      <button disabled={blocked} onClick={()=>void scan()}>扫描白名单</button>
      {!!recentPlans.length&&<details><summary>已保存清理计划</summary>{recentPlans.map(item=><button key={item.id} disabled={blocked} onClick={()=>void loadPlan(String(item.data?.plan_id))}>查看计划 {String(item.data?.plan_id).slice(0,8)}</button>)}</details>}
      {plan&&<section aria-label="清理逐项计划"><h4>计划版本 {plan.revision.slice(0,12)} · {plan.status}</h4><p>候选逻辑大小 {bytes(plan.logical_bytes)}；已隔离 {bytes(plan.quarantined_bytes)}；实际释放空间 {bytes(plan.released_bytes)}。{plan.truncated?'扫描有上限，结果已截断。':''}</p>
        <p>受限恢复截止：{plan.restore_until}。到期不自动永久删除隔离文件；冲突、占用或内容变化会拒绝恢复。</p>
        <ul>{plan.entries.map(item=><li key={item.index}><label><input type="checkbox" checked={selected.includes(item.index)} disabled={blocked||plan.status!=='planned'||item.status!=='pending'} onChange={()=>setSelected(values=>values.includes(item.index)?values.filter(i=>i!==item.index):[...values,item.index])}/>{item.name}</label> · {bytes(item.size)} · {item.risk==='medium'?'中风险（日志可能仍有用途）':'低风险'} · 修改于 {item.mtime} · {item.status}{item.error&&` · ${item.error}`}{item.status==='moved'&&<button disabled={blocked} onClick={()=>void restore(item.index)}>确认恢复</button>}</li>)}</ul>
        {plan.status==='planned'&&<button className="primary" disabled={blocked||!selected.length} onClick={()=>void execute()}>批准选中项的此版本并隔离</button>}
      </section>}
    </details>
  </section>;
}
