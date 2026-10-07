import React,{useEffect,useState} from 'react';
import type {SkillSummary,SkillExecution} from '../main/skills-contracts';
const statusLabel={completed:'已完成只读工作流',limited:'结果受限，后续步骤已停止',failed:'执行失败',interrupted:'执行中断',planned:'计划待执行',running:'运行中'};
const toolLabel:Record<string,string>={list_directory:'文件清单',search_files:'搜索文件',get_file_metadata:'文件属性',analyze_directory_space:'空间统计',read_text_file:'读取文本',memory_context:'本地记忆上下文',query_rewrite:'原问题与已批准候选检索'};

/** 展示注册与真实执行事实；Skill 声明和“可用”状态不能代替原生授权。 */
export function SkillsPanel(){
  const [skills,setSkills]=useState<SkillSummary[]>([]),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  const [selected,setSelected]=useState('file-organize'),[inputs,setInputs]=useState('{"path":"."}');
  const [local,setLocal]=useState(false),[cid,setCid]=useState(''),[chats,setChats]=useState<{id:string;title:string}[]>([]);
  const [result,setResult]=useState<SkillExecution>();
  const [history,setHistory]=useState<Pick<SkillExecution,'plan_id'|'skill_id'|'version'|'status'>[]>([]);
  const [offset,setOffset]=useState(0),[total,setTotal]=useState(0);
  async function reload(next=offset){const reply=await window.orvia.skillsList({offset:next});if(reply.ok){setSkills(reply.result.skills);setOffset(reply.result.offset);setTotal(reply.result.total);
    if(!reply.result.skills.some(s=>s.id===selected))setSelected(reply.result.skills.find(s=>s.enabled&&s.available)?.id??reply.result.skills[0]?.id??'');
  }else setNotice(reply.message);
    const saved=await window.orvia.skillsHistory();if(saved.ok)setHistory(saved.result.executions);
  }
  useEffect(()=>{void window.orvia.chatList().then(r=>{if(r.ok){setChats(r.result.conversations);setCid(r.result.conversations[0]?.id??'');}}).catch(()=>setNotice('会话列表暂不可用。'));void reload().catch(()=>setNotice('工作流列表暂不可用。'));},[]);
  async function act(action:()=>Promise<void>){setBusy(true);try{await action();}catch{setNotice('工作流操作未完成，请检查输入与连接。');}finally{setBusy(false);}}
  return <section aria-label="Skills 工作流" className="skills-panel"><h3>Skills 工作流</h3>
    <p>导入声明式工作流，逐步调用已授权工具。文件盘点只读；后续业务按依赖显示准备状态。</p>
    <button disabled={busy} onClick={()=>void act(async()=>{const r=await window.orvia.skillsImport();setNotice(r.ok?(r.result.cancelled?'已取消导入。':'此版本已登记。'):r.message);await reload();})}>选择并审查 Skill 包</button>
    <div className="skills-list">{skills.map(skill=><article key={skill.id}><div className="row between"><strong>{skill.name}</strong><button disabled={busy} onClick={()=>void act(async()=>{
      const r=await window.orvia.skillsToggle({skill_id:skill.id,enabled:!skill.enabled});setNotice(r.ok?'启用状态已更新，旧计划已失效。':r.message);await reload();
    })}>{skill.enabled?'禁用':'启用'} {skill.name}</button></div><p>{skill.description}</p>
      <small>{!skill.enabled?'已禁用':skill.available?'可用':`未就绪：${skill.unavailable_reason}`}</small><details><summary>工作流版本</summary><p>{skill.id} / {skill.version}</p><p>{skill.revision}</p></details></article>)}</div>
    {total>10&&<div className="row"><button disabled={busy||offset===0} onClick={()=>void act(()=>reload(Math.max(0,offset-10)))}>上一页工作流</button><span>{offset+1}–{Math.min(offset+10,total)} / {total}</span><button disabled={busy||offset+10>=total} onClick={()=>void act(()=>reload(offset+10))}>下一页工作流</button></div>}
    <label>运行工作流<select aria-label="运行工作流" disabled={busy} value={selected} onChange={e=>{const id=e.target.value;setSelected(id);setResult(undefined);const isLocal=['memory-context','query-rewrite'].includes(id);setLocal(isLocal);setInputs(isLocal?(id==='query-rewrite'?'{"query":"合成问题","revision":""}':'{"query":"合成问题"}'):'{"path":"."}');}}>{skills.map(s=><option key={s.id} value={s.id} disabled={!s.enabled||!s.available}>{s.name}</option>)}</select></label>
    <label><input type="checkbox" checked={local} disabled={busy} onChange={e=>setLocal(e.target.checked)}/>只读本机会话与资料</label>
    {local&&<label>本地工作流所属会话<select aria-label="本地工作流所属会话" disabled={busy} value={cid} onChange={e=>setCid(e.target.value)}>{chats.map(chat=><option key={chat.id} value={chat.id}>{chat.title}</option>)}</select></label>}
    <p>{local?'本地运行只读取该会话与已有有效资料；不生成云端改写。Query Rewrite 的 revision 留空时使用原问题。':'文件工作流将原生选择本次目录。'}</p>
    <label>工作流输入（JSON）<textarea aria-label="工作流输入（JSON）" disabled={busy} maxLength={8000} value={inputs} onChange={e=>setInputs(e.target.value)}/></label>
    <button disabled={busy||(local&&!cid)||!skills.some(s=>s.id===selected&&s.enabled&&s.available)} onClick={()=>void act(async()=>{
      const value:unknown=JSON.parse(inputs);if(!value||typeof value!=='object'||Array.isArray(value)){setNotice('输入必须是 JSON 对象。');return;}
      const r=await window.orvia.skillsRun({skill_id:selected,inputs:value as Record<string,unknown>,...(local?{conversation_id:cid}:{})});
      if(!r.ok)setNotice(r.message);else if(r.result.cancelled)setNotice('已取消，工具未执行。');else {setResult(r.result.result);setNotice('执行已结束，请核对逐步事实。');}await reload();
    })}>{local?'预览本地工作流':'选择目录并预览执行'}</button>
    <p role="status">{notice}</p>
    {history.length>0&&<details><summary>最近工作流记录</summary>{history.map(item=><button disabled={busy} key={item.plan_id} onClick={()=>void act(async()=>{
      const r=await window.orvia.skillsExecution({plan_id:item.plan_id});if(r.ok)setResult(r.result);else setNotice(r.message);
    })}>{skills.find(s=>s.id===item.skill_id)?.name??item.skill_id} · {statusLabel[item.status]}</button>)}</details>}
    {result&&<article aria-label="Skill 执行结果"><strong>{statusLabel[result.status]}</strong>
      <ol>{result.steps.map(step=><li key={step.id}>{toolLabel[step.tool]??step.tool}：{({completed:'已核验',limited:'受限',failed:'失败',unknown:'结果未知'})[step.status]}{step.error&&`（${step.error.code}）`}</li>)}</ol>
      <details><summary>查看工具事实</summary><pre>{JSON.stringify(result,null,2)}</pre></details></article>}
  </section>;
}
