import React,{useEffect,useState} from 'react';
import type {ShellInterpreter,ShellPreview,ShellRun} from '../main/shell-contracts';
const status={running:'进程运行中',exited:'进程已退出，仍需核对业务结果',timed_out:'执行超时',cancelled:'执行已取消',unknown:'结果未知，不自动重试',failed:'执行失败'};
const checked={passed:'明确列出的核验通过',failed:'明确列出的核验失败',not_requested:'未请求结果核验',unknown:'核验结果未知或受限'};

/** 退出码只代表进程事实；普通账户脚本与隔离Python能力的权限边界分别明确展示。 */
export function ShellPanel(){
  const [chats,setChats]=useState<{id:string;title:string}[]>([]),[cid,setCid]=useState(''),[interpreters,setInterpreters]=useState<ShellInterpreter[]>([]),[interpreter,setInterpreter]=useState('');
  const [script,setScript]=useState('Write-Output "ORVIA_SYNTHETIC"'),[seconds,setSeconds]=useState(20),[expected,setExpected]=useState(''),[outputs,setOutputs]=useState(''),[cwd,setCwd]=useState(false),[inputs,setInputs]=useState(false);
  const [preview,setPreview]=useState<ShellPreview>(),[run,setRun]=useState<ShellRun>(),[active,setActive]=useState<{id:string;run_id:string}>(),[history,setHistory]=useState<ShellRun[]>([]),[historyLimited,setHistoryLimited]=useState(false);
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  async function detect(){const r=await window.orvia.shellDetect();if(r.ok){setInterpreters(r.result.interpreters);setInterpreter(old=>r.result.interpreters.some(item=>item.id===old&&item.available)?old:r.result.interpreters.find(item=>item.available)?.id??'');}else setNotice(r.message);}
  useEffect(()=>{void detect().catch(()=>setNotice('解释器检测未完成。'));void window.orvia.chatList().then(r=>{if(r.ok){setChats(r.result.conversations);setCid(r.result.conversations[0]?.id??'');}}).catch(()=>setNotice('会话列表暂不可用。'));},[]);
  useEffect(()=>{let live=true;setPreview(undefined);setRun(undefined);setHistory([]);if(cid)void window.orvia.shellHistory({id:cid}).then(r=>{if(live&&r.ok){setHistory(r.result.executions);setHistoryLimited(r.result.truncated);}}).catch(()=>{if(live)setNotice('本机Shell历史暂不可用。');});return()=>{live=false;};},[cid]);
  useEffect(()=>{if(!active)return;let live=true,polling=false;
    const timer=setInterval(()=>{if(polling)return;polling=true;void window.orvia.shellStatus(active).then(r=>{if(live&&r.ok)setRun(r.result);}).catch(()=>{if(live)setNotice('运行状态暂时未知，不会自动重新执行。');}).finally(()=>{polling=false;});},500);
    return()=>{live=false;clearInterval(timer);};
  },[active]);
  async function loadHistory(){const r=await window.orvia.shellHistory({id:cid});if(r.ok){setHistory(r.result.executions);setHistoryLimited(r.result.truncated);}}
  async function act(action:()=>Promise<void>){setBusy(true);try{await action();}catch{setPreview(undefined);setNotice('操作未完成或结果未知，请核对运行事实；不会自动重试脚本。');}finally{setBusy(false);}}
  const selected=interpreters.find(item=>item.id===interpreter);
  const clear=()=>{setPreview(undefined);setRun(undefined);};
  return <section aria-label="普通账户 Shell 执行" className="skills-panel"><h3>普通账户 Shell 执行</h3>
    <p>运行本机独立解释器，不接管现有个人终端。以当前普通账户执行，具有该账户文件和网络权限；不是 LPAC 或路径/网络隔离。Job 用于本次进程和自有后代回收。每次完整脚本须另行原生批准。</p>
    <button disabled={busy} onClick={()=>void act(detect)}>重新检测本机 Shell</button>
    {interpreters.map(item=><details key={item.id}><summary>{item.label} · {item.available?'可明确选择':'不可用'}</summary><p>{item.reason??'版本与程序身份已检测。'}</p><p>{item.executable}</p><p>{item.version??'版本未确认'} · {item.sha256??'程序身份未确认'}</p>{item.distro&&<p>准确 WSL 发行版：{item.distro}</p>}</details>)}
    <label>Shell 所属会话<select aria-label="Shell 所属会话" disabled={busy} value={cid} onChange={e=>setCid(e.target.value)}>{chats.map(chat=><option key={chat.id} value={chat.id}>{chat.title}</option>)}</select></label>
    <label>本次 Shell 解释器<select aria-label="本次 Shell 解释器" disabled={busy} value={interpreter} onChange={e=>{setInterpreter(e.target.value);clear();}}>{interpreters.map(item=><option key={item.id} disabled={!item.available} value={item.id}>{item.label}</option>)}</select></label>
    <p>选定解释器：{selected?.label??'暂无可用解释器'}。各Shell语法不同，请完整审查本次脚本。</p>
    <label>完整 Shell 脚本<textarea aria-label="完整 Shell 脚本" disabled={busy} maxLength={16384} rows={8} value={script} onChange={e=>{setScript(e.target.value);clear();}}/></label>
    <label>Shell 超时（秒，1～60）<input aria-label="Shell 超时（秒，1～60）" disabled={busy} type="number" min={1} max={60} value={seconds} onChange={e=>{setSeconds(Number(e.target.value));clear();}}/></label>
    <label>明确核验 stdout 包含文本（可留空）<input aria-label="明确核验 stdout 包含文本（可留空）" disabled={busy} maxLength={1000} value={expected} onChange={e=>{setExpected(e.target.value);clear();}}/></label>
    <label>明确产物文件名（每行一个，最多十个）<textarea aria-label="明确产物文件名（每行一个，最多十个）" disabled={busy} rows={3} maxLength={2100} value={outputs} onChange={e=>{setOutputs(e.target.value);clear();}}/></label>
    <label><input aria-label="原生选择本次工作目录" type="checkbox" checked={cwd} disabled={busy} onChange={e=>{setCwd(e.target.checked);clear();}}/>原生选择本次工作目录；未选时使用本次私有工作目录</label>
    <label><input aria-label="原生选择显式输入文件" type="checkbox" checked={inputs} disabled={busy} onChange={e=>{setInputs(e.target.checked);clear();}}/>原生选择显式输入文件（最多三份、合计30MiB）</label>
    <p>脚本最多16KiB；stdout/stderr各16KiB。输入副本位于 ORVIA_INPUT_DIR，产物位于 ORVIA_OUTPUT_DIR；仅列出的普通文件接受核验，单个1MiB、合计2MiB。这些预算不代表文件访问隔离。</p>
    <button disabled={busy||!cid||!selected?.available||!script.trim()||seconds<1||seconds>60||!Number.isInteger(seconds)||Array.from(expected).length>1000} onClick={()=>void act(async()=>{clear();const output_names=outputs.split(/\r?\n/).filter(Boolean);const r=await window.orvia.shellPreview({id:cid,interpreter_id:interpreter,script,timeout_seconds:seconds,...(expected?{expected_stdout:expected}:{}),output_names,choose_cwd:cwd,choose_inputs:inputs});if(r.ok){if(r.result.cancelled)setNotice('已取消原生选择，脚本未执行。');else if(r.result.result){setPreview(r.result.result);setNotice('准确预览已准备，请审查完整脚本、身份、目录、输入与核验条件。');}}else setNotice(r.message);})}>准备 Shell 完整预览</button>
    {preview&&<article aria-label="Shell 完整执行预览"><h4>本次准确执行预览</h4><label>Shell 完整批准正文<textarea aria-label="Shell 完整批准正文" readOnly rows={16} value={JSON.stringify(preview,null,2)}/></label>
      <button disabled={busy} onClick={()=>void act(async()=>{const saved=preview;setPreview(undefined);setActive({id:cid,run_id:saved.run_id});setNotice('等待本次原生批准及进程结果。');try{const r=await window.orvia.shellExecute({id:cid,run_id:saved.run_id,revision:saved.revision});if(r.ok){if(r.result.cancelled)setNotice('已取消原生批准，脚本未执行。');else if(r.result.result){setRun(r.result.result);setNotice(`${status[r.result.result.status]}；${checked[r.result.result.verification.status]}。退出码0不等于全部业务完成。`);await loadHistory();}}else setNotice(r.message);}finally{setActive(undefined);}})}>原生批准此完整 Shell 脚本</button></article>}
    {active&&<button disabled={run?.status!=='running'} onClick={()=>{void window.orvia.shellCancel(active).then(r=>{if(r.ok){setRun(r.result);setNotice('已请求取消本次进程，请核对Job后代回收与结果事实。');}else setNotice(r.message);}).catch(()=>setNotice('取消结果未知，请核对进程事实；不会自动重试脚本。'));}}>取消当前 Shell 进程</button>}
    {run&&<article aria-label="Shell 进程与核验事实"><h4>{status[run.status]}</h4><p>退出码：{run.exit_code??'未取得'}。自有后代回收：{run.children_reaped?'已核验':'尚未核验'}。</p><p>{checked[run.verification.status]}；仅覆盖下列明确条件，不能据此宣称业务全部完成。</p>{run.verification.details.map((item,index)=><p key={index}>{item}</p>)}{run.error&&<p>{run.error.code} · {run.error.message}</p>}
      <label>Shell stdout<textarea aria-label="Shell stdout" readOnly rows={6} value={run.stdout}/></label>{run.stdout_truncated&&<p>stdout 已截断，未覆盖全部输出。</p>}
      <label>Shell stderr<textarea aria-label="Shell stderr" readOnly rows={4} value={run.stderr}/></label>{run.stderr_truncated&&<p>stderr 已截断，未覆盖全部输出。</p>}
      {run.outputs.map(file=><article key={file.name}><p>产物：{file.name} · {file.bytes} 字节</p><small>SHA256：{file.sha256}</small><button disabled={busy} onClick={()=>void act(async()=>{const r=await window.orvia.shellExport({id:run.id,run_id:run.run_id,name:file.name});setNotice(r.ok?(r.result.cancelled?'已取消产物回传。':r.result.result?`新文件已保存并核验：${r.result.result.filename}`:'回传结果待核对。'):r.message);})}>逐文件批准回传 {file.name}</button></article>)}
    </article>}
    <details><summary>本会话 Shell 事实历史（最多十条）</summary><p>{historyLimited?'历史正文达到展示预算，不能视为完整历史。':''}</p>{history.map(item=><button disabled={busy} key={item.run_id} onClick={()=>{setPreview(undefined);setRun(item);}}>{item.interpreter_id} · {status[item.status]} · {checked[item.verification.status]}</button>)}</details>
    <p role="status">{notice}</p>
  </section>;
}
