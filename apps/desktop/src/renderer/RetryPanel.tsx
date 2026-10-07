import React,{useEffect,useRef,useState} from 'react';
import type {RetryHistory,RetryRun,RetryAttempt} from '../main/retry-contracts';

const stateLabels={running:'读取尝试进行中',succeeded:'收到成功结果',failed:'读取尝试失败',unknown:'结果未知，未重试',cancelled:'已取消',timed_out:'原预算已耗尽',interrupted:'重启或断线中断，未重放'};
const toolLabels={'browser.static_read':'公开网页静态读取','context.sqlite_read':'本机SQLite检索读取'};
const reasonLabels={initial:'首次尝试',connect_before_send:'发送前连接失败',http_429:'远端暂时限流',http_503:'远端暂时不可用',sqlite_busy:'本机数据库暂忙',sqlite_locked:'本机数据库暂锁',not_retryable:'错误不符合安全重试条件',budget_exhausted:'剩余预算不足',cancelled:'用户取消',interrupted:'执行中断，不自动恢复',success:'收到成功结果'};

/** 明确区分尝试事实与全目标证据闭环；此面板没有执行、分类修改或重试批准入口。 */
export function RetryRecord({run}:{run:RetryRun}){
  return <article aria-label="安全读取重试事实"><h4>{toolLabels[run.tool]} · {stateLabels[run.state]}</h4>
    <p>业务身份：{run.business_id}。工具：{run.tool}</p><p>尝试 {run.attempts.length}/3。开始：{run.started_at}；结束：{run.finished_at??'尚未记录终态'}。</p>
    <p>{run.state==='running'?'安全读取仍在原请求预算内进行。':'读取尝试已结束，不代表全任务完成。'}目标完成仍须逐项目标证据核验。</p>
    <details><summary>同一准确请求的尝试序号、时间和原因</summary><p>参数摘要：{run.parameter_digest}；不包含URL、正文或凭据。</p>
      {run.attempts.map(attempt=><Attempt key={attempt.sequence} attempt={attempt}/>)}</details>
  </article>;
}
function Attempt({attempt}:{attempt:RetryAttempt}){return <article aria-label={`读取尝试 ${attempt.sequence}`}><p>第 {attempt.sequence} 次 · {stateLabels[attempt.state]}</p><p>开始：{attempt.started_at}；结束：{attempt.finished_at??'尚未记录终态'}。</p><p>有界等待：{attempt.delay_seconds} 秒；原因：{attempt.reason?reasonLabels[attempt.reason]:'暂无原因记录'}；错误码：{attempt.error_code??'无'}。</p></article>;}

export function RetryPanel(){
  const [chats,setChats]=useState<{id:string;title:string}[]>([]),[cid,setCid]=useState(''),[history,setHistory]=useState<RetryHistory>(),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  const requestVersion=useRef(0);
  // 同一会话选择不会触发cid effect；保留原请求版本，避免其finally失效后永久忙碌。
  function changeConversation(id:string){if(id===cid)return;requestVersion.current++;setHistory(undefined);setNotice('');setCid(id);}
  useEffect(()=>{let live=true;void window.orvia.chatList().then(reply=>{if(live){if(reply.ok){setChats(reply.result.conversations);setCid(reply.result.conversations[0]?.id??'');}else setNotice(reply.message);}}).catch(()=>{if(live)setNotice('会话列表暂不可用。');});return()=>{live=false;};},[]);
  useEffect(()=>{let live=true;const version=++requestVersion.current;setHistory(undefined);setNotice('');setBusy(Boolean(cid));if(cid)void window.orvia.retryHistory({id:cid}).then(reply=>{if(!live||version!==requestVersion.current)return;if(reply.ok){setHistory(reply.result);setNotice('已读取本机会话的重试事实。');}else setNotice(reply.message);}).catch(()=>{if(live&&version===requestVersion.current)setNotice('重试账本暂不可用；状态查询不会重新执行原请求。');}).finally(()=>{if(live&&version===requestVersion.current)setBusy(false);});return()=>{live=false;};},[cid]);
  async function refresh(){const id=cid,version=++requestVersion.current;setBusy(true);try{const reply=await window.orvia.retryHistory({id});if(version!==requestVersion.current)return;if(reply.ok){setHistory(reply.result);setNotice('已刷新本机重试事实，未执行新的业务请求。');}else{setHistory(undefined);setNotice(reply.message);}}catch{if(version===requestVersion.current){setHistory(undefined);setNotice('读取账本失败或状态未知，请核对现有任务；不会重放业务请求。');}}finally{if(version===requestVersion.current)setBusy(false);}}
  return <section aria-label="安全读取重试记录" className="skills-panel"><h3>安全读取重试记录</h3>
    <p>程序只对已确认重复安全的静态公开读取与本机检索读取处理允许的暂时性错误，合计最多三次尝试；有界等待和执行都计入原请求总预算。预算不足、取消或不可重试错误即停止。</p>
    <p>模型、Shell、进程、文件变更、浏览器外发及动态请求、MCP和未知结果不自动重试。请求成功只表示收到读取结果，不能替代每个目标的实际证据。</p>
    <label>重试记录所属会话<select aria-label="重试记录所属会话" value={cid} onChange={e=>changeConversation(e.target.value)}>{chats.map(chat=><option key={chat.id} value={chat.id}>{chat.title}</option>)}</select></label>
    <button disabled={busy||!cid} onClick={()=>void refresh()}>刷新安全读取重试记录</button>
    <p>取消运行中的读取请使用所属任务已有取消入口；此处仅查看本机账本，不恢复旧请求或旧审批。</p>
    {history?.id===cid&&<><p>展示最近 {history.runs.length} 个业务读取记录（最多32个）。{history.truncated?'达到条数或运输预算，不代表完整历史。':''}</p>{history.runs.length===0&&<p>此会话尚无安全读取重试记录。</p>}{history.runs.map(run=><RetryRecord key={run.business_id+run.tool+run.started_at} run={run}/>)}</>}
    <p role="status">{notice}</p>
  </section>;
}
