import React,{useEffect,useState} from 'react';
import type {ProcessIdentity,ProcessPreview,ProcessExecution} from '../main/process-contracts';

const actions={launch:'启动',wait:'等待',close:'温和关闭',terminate:'终止'};
const statuses={running:'操作进行中',exited:'准确进程已退出',still_running:'等待结束，准确进程仍运行',unknown:'结果未知，不自动重试',failed:'操作失败'};
const identityKey=(item:ProcessIdentity)=>`${item.pid}:${item.creation_ticks}`;

/** 进程事实只展示准确身份和有限状态；温和关闭与终止是两次独立原生许可。 */
export function ProcessPanel(){
  const [chats,setChats]=useState<{id:string;title:string}[]>([]),[cid,setCid]=useState(''),[processes,setProcesses]=useState<ProcessIdentity[]>([]),[selected,setSelected]=useState(''),[listLimited,setListLimited]=useState(false);
  const [action,setAction]=useState<'wait'|'close'|'terminate'>('wait'),[seconds,setSeconds]=useState(3),[args,setArgs]=useState('[]'),[cwd,setCwd]=useState(false);
  const [preview,setPreview]=useState<ProcessPreview>(),[execution,setExecution]=useState<ProcessExecution>(),[active,setActive]=useState<{id:string;operation_id:string}>(),[history,setHistory]=useState<ProcessExecution[]>([]),[historyLimited,setHistoryLimited]=useState(false);
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  async function loadList(id=cid){const r=await window.orvia.processList({id});if(r.ok){setProcesses(r.result.processes);setListLimited(r.result.truncated);setSelected(old=>r.result.processes.some(item=>identityKey(item)===old)?old:'');if(r.result.unavailable_reason)setNotice(r.result.unavailable_reason);}else setNotice(r.message);}
  async function loadHistory(id=cid){const r=await window.orvia.processHistory({id});if(r.ok){setHistory(r.result.executions);setHistoryLimited(r.result.truncated);}else setNotice(r.message);}
  useEffect(()=>{void window.orvia.chatList().then(r=>{if(r.ok){setChats(r.result.conversations);setCid(r.result.conversations[0]?.id??'');}}).catch(()=>setNotice('会话列表暂不可用。'));},[]);
  useEffect(()=>{let live=true;setPreview(undefined);setExecution(undefined);setSelected('');setProcesses([]);setHistory([]);if(cid)void Promise.all([window.orvia.processList({id:cid}),window.orvia.processHistory({id:cid})]).then(([list,saved])=>{if(!live)return;if(list.ok){setProcesses(list.result.processes);setListLimited(list.result.truncated);if(list.result.unavailable_reason)setNotice(list.result.unavailable_reason);}else setNotice(list.message);if(saved.ok){setHistory(saved.result.executions);setHistoryLimited(saved.result.truncated);}else setNotice(saved.message);}).catch(()=>{if(live)setNotice('本机进程列表或历史暂不可用。');});return()=>{live=false;};},[cid]);
  useEffect(()=>{if(!active)return;let live=true,polling=false;const timer=setInterval(()=>{if(polling)return;polling=true;void window.orvia.processStatus(active).then(r=>{if(live&&r.ok)setExecution(r.result);}).catch(()=>{if(live)setNotice('进程操作状态暂时未知，不自动重新执行。');}).finally(()=>{polling=false;});},500);return()=>{live=false;clearInterval(timer);};},[active]);
  async function act(run:()=>Promise<void>){setBusy(true);try{await run();}catch{setPreview(undefined);setNotice('操作未完成或结果未知，请核对准确进程与现有事实；不会自动重试或升级动作。');}finally{setBusy(false);}}
  const target=processes.find(item=>identityKey(item)===selected);
  const validWait=Number.isInteger(seconds)&&seconds>=1&&seconds<=15;
  function clear(){setPreview(undefined);setExecution(undefined);}
  function selectFact(item:ProcessIdentity){setProcesses(old=>old.some(p=>identityKey(p)===identityKey(item))?old:[item,...old].slice(0,50));setSelected(identityKey(item));setAction('wait');setPreview(undefined);}
  return <section aria-label="普通用户进程管理" className="skills-panel"><h3>普通用户进程管理</h3>
    <p>仅查看本机同用户普通权限进程的名称、PID、创建时间、程序路径与哈希。服务核验实际账户和权限，拒绝保护、关键或提权目标；不读取命令行、环境或窗口私人正文。</p>
    <label>进程操作所属会话<select aria-label="进程操作所属会话" disabled={busy} value={cid} onChange={e=>setCid(e.target.value)}>{chats.map(chat=><option key={chat.id} value={chat.id}>{chat.title}</option>)}</select></label>
    <button disabled={busy||!cid} onClick={()=>void act(()=>loadList())}>刷新普通用户进程列表</button>
    <p>当前展示 {processes.length} 个准确身份。{listLimited?'达到列表预算，不代表本机全部进程。':''}</p>
    <label>明确选择一个准确进程<select aria-label="明确选择一个准确进程" disabled={busy} value={selected} onChange={e=>{setSelected(e.target.value);clear();}}><option value="">请选择准确目标</option>{processes.map(item=><option key={identityKey(item)} value={identityKey(item)}>{item.name} · PID {item.pid} · 创建 {item.create_time}</option>)}</select></label>
    {target&&<article aria-label="选中进程准确身份"><p>{target.name} · PID {target.pid}</p><p>{target.executable}</p><p>创建时间：{target.create_time}，精确FILETIME：{target.creation_ticks}</p><p>SHA256：{target.sha256}</p></article>}
    <label>此次准确进程动作<select aria-label="此次准确进程动作" disabled={busy} value={action} onChange={e=>{setAction(e.target.value as 'wait'|'close'|'terminate');clear();}}><option value="wait">等待准确进程</option><option value="close">请求温和关闭</option><option value="terminate">单独终止准确进程</option></select></label>
    <label>进程观察等待（秒，1～15）<input aria-label="进程观察等待（秒，1～15）" disabled={busy} type="number" min={1} max={15} value={seconds} onChange={e=>{setSeconds(Number(e.target.value));clear();}}/></label>
    <p>{action==='terminate'?'终止仅限单个准确PID，可能丢失未保存内容且无法撤销；不递归、不批量。':action==='close'?'温和关闭可能触发未保存提示，请自行在应用中处理。仍运行会明确显示，不自动升级为终止。':'只观察所选准确进程，不因超时或仍运行而自动关闭、重试或终止。'}</p>
    <button disabled={busy||!cid||!target||!validWait} onClick={()=>void act(async()=>{clear();if(!target)return;const r=await window.orvia.processActionPreview({id:cid,action,pid:target.pid,create_time:target.create_time,creation_ticks:target.creation_ticks,wait_seconds:seconds});if(r.ok){setPreview(r.result);setNotice('准确进程身份和动作已准备，请完整核对后单独原生批准。');}else setNotice(r.message);})}>准备此准确进程动作预览</button>
    <h4>原生选择并启动普通权限程序</h4><label>启动参数（JSON字符串数组）<textarea aria-label="启动参数（JSON字符串数组）" disabled={busy} rows={4} maxLength={8192} value={args} onChange={e=>{setArgs(e.target.value);clear();}}/></label>
    <label><input aria-label="原生选择此次程序工作目录" type="checkbox" disabled={busy} checked={cwd} onChange={e=>{setCwd(e.target.checked);clear();}}/>原生选择此次程序工作目录；未选时采用程序所在目录</label>
    <p>程序路径只能通过原生单选EXE确定，最多16个参数、合计8KiB。程序以普通账户权限运行，可能访问该账户文件和网络；此入口不接管现有个人终端。</p>
    <button disabled={busy||!cid||!validWait} onClick={()=>void act(async()=>{clear();const value:unknown=JSON.parse(args);if(!Array.isArray(value)||value.some(item=>typeof item!=='string')){setNotice('参数必须是 JSON 字符串数组。');return;}const r=await window.orvia.processLaunchPreview({id:cid,args:value as string[],choose_cwd:cwd,wait_seconds:seconds});if(r.ok){if(r.result.cancelled)setNotice('已取消原生选择，程序未启动。');else if(r.result.result){setPreview(r.result.result);setNotice('准确程序、参数和目录已准备，启动仍须原生批准。');}}else setNotice(r.message);})}>原生选择程序并准备启动预览</button>
    {preview&&<article aria-label="进程完整动作预览"><h4>此次 {actions[preview.action]} 完整预览</h4><label>进程完整批准正文<textarea aria-label="进程完整批准正文" readOnly rows={12} value={JSON.stringify(preview,null,2)}/></label>
      <button disabled={busy} onClick={()=>void act(async()=>{const saved=preview;setPreview(undefined);setActive({id:cid,operation_id:saved.operation_id});setNotice('等待此一步原生批准与准确进程事实。');try{const r=await window.orvia.processExecute({id:cid,operation_id:saved.operation_id,revision:saved.revision});if(r.ok){if(r.result.cancelled)setNotice('已取消原生批准，进程动作未执行。');else if(r.result.result){setExecution(r.result.result);setNotice(`${statuses[r.result.result.status]}。进程事实不等于业务全部完成。`);await loadHistory();if(r.result.result.target)selectFact(r.result.result.target);}}else setNotice(r.message);}finally{setActive(undefined);}})}>原生批准此准确进程动作</button></article>}
    {execution&&<article aria-label="进程操作事实"><h4>{statuses[execution.status]}</h4><p>动作：{actions[execution.action]}。事实核验：{execution.verified?'已核验所列进程事实':'尚未核验'}；进程状态不代表业务目标全部完成。</p>
      {execution.target&&<><p>{execution.target.name} · PID {execution.target.pid}</p><p>{execution.target.executable}</p><p>创建时间：{execution.target.create_time} · 精确FILETIME {execution.target.creation_ticks}</p><p>SHA256：{execution.target.sha256}</p></>}
      <p>退出码：{execution.exit_code??'未取得'}。</p>{execution.action==='close'&&<p>{execution.close_sent?'已实际投递温和关闭请求；请核对未保存提示与退出状态。':'没有实际投递窗口关闭请求；不能称已关闭。'}</p>}{execution.error&&<p>{execution.error.code} · {execution.error.message}</p>}
    </article>}
    <details><summary>本会话进程事实历史（最多十条）</summary><p>{historyLimited?'历史达到展示预算，不代表完整历史。':''}</p>{history.map(item=><button disabled={busy} key={item.operation_id} onClick={()=>{setPreview(undefined);setExecution(item);if(item.target)selectFact(item.target);}}>{actions[item.action]} · {statuses[item.status]} · PID {item.target?.pid??'待核对'}</button>)}</details>
    <p role="status">{notice}</p>
  </section>;
}
