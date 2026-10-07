import React,{useEffect,useState} from 'react';
import type {McpServer,McpToolReview,McpCallPreview,McpExecution,McpCredentialStatus} from '../main/mcp-contracts';

const serverStatus={configured:'已登记，尚未连接',review_required:'待审查工具清单',ready:'已审查，调用仍需逐次批准',disconnected:'连接已关闭',error:'服务连接受限'};
const executionStatus={completed:'已收到有效工具响应',failed:'调用失败',unknown:'调用结果未知，不自动重试',limited:'响应受限，不能据此判断外部任务完成'};
function Execution({item}:{item:McpExecution}){return <article><h4>{item.server_name} · {item.tool}</h4><p>{executionStatus[item.status]}</p>{item.error&&<p>{item.error.code} · {item.error.message}</p>}<label>工具响应（纯数据，不自动打开 URI）<textarea aria-label="工具响应（纯数据，不自动打开 URI）" readOnly rows={8} value={JSON.stringify(item.result,null,2)}/></label><small>外部响应或只读声明不能证明实际副作用；资源 URI、代码与指令仅展示为文本。</small></article>;}

/** 外部服务须配置、连接、工具审查及准确参数四步许可；响应不能获得执行或文件权限。 */
export function McpPanel(){
  const [servers,setServers]=useState<McpServer[]>([]),[sid,setSid]=useState(''),[chats,setChats]=useState<{id:string;title:string}[]>([]),[cid,setCid]=useState('');
  const [review,setReview]=useState<McpToolReview>(),[tool,setTool]=useState(''),[args,setArgs]=useState('{}'),[preview,setPreview]=useState<McpCallPreview>();
  const [execution,setExecution]=useState<McpExecution>(),[history,setHistory]=useState<McpExecution[]>([]),[credentials,setCredentials]=useState<McpCredentialStatus>(),[token,setToken]=useState('');
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  async function reload(){const r=await window.orvia.mcpList();if(r.ok){setServers(r.result.servers);setSid(old=>r.result.servers.some(item=>item.id===old)?old:r.result.servers[0]?.id??'');}else setNotice(r.message);const c=await window.orvia.mcpCredentialStatus();if(c.ok)setCredentials(c.result);else setNotice(c.message);}
  useEffect(()=>{void reload().catch(()=>setNotice('MCP服务列表暂不可用。'));void window.orvia.chatList().then(r=>{if(r.ok){setChats(r.result.conversations);setCid(r.result.conversations[0]?.id??'');}}).catch(()=>setNotice('会话列表暂不可用。'));},[]);
  useEffect(()=>{setReview(undefined);setPreview(undefined);setExecution(undefined);setTool('');setToken('');},[sid]);
  useEffect(()=>{let live=true;setPreview(undefined);setExecution(undefined);setHistory([]);if(cid)void window.orvia.mcpHistory({id:cid}).then(r=>{if(live){if(r.ok)setHistory(r.result.executions);else setNotice(r.message);}}).catch(()=>{if(live)setNotice('本机MCP调用记录暂不可用。');});return()=>{live=false;};},[cid]);
  async function act(action:()=>Promise<void>){setBusy(true);try{await action();await reload();}catch{setPreview(undefined);setNotice('操作未完成或结果未知，请查看服务状态与本机记录；不会自动重试外部调用。');}finally{setBusy(false);}}
  async function savedHistory(){const r=await window.orvia.mcpHistory({id:cid});if(r.ok)setHistory(r.result.executions);}
  const server=servers.find(item=>item.id===sid);
  return <section aria-label="MCP 外部只读工具" className="skills-panel"><h3>MCP 外部只读工具</h3>
    <p>协议固定为 2025-06-18。先登记配置，再原生批准连接和准确工具清单，最后逐次批准参数。本地服务以当前用户权限运行；MCP 与 readOnlyHint 不提供系统隔离或无副作用保证。</p>
    <button disabled={busy||servers.length>=5} onClick={()=>void act(async()=>{const r=await window.orvia.mcpImport();if(r.ok){setNotice(r.result.cancelled?'已取消登记，服务未连接。':'服务配置已登记，请单独批准连接。');if(r.result.result)setSid(r.result.result.id);}else setNotice(r.message);})}>选择并审查 MCP 配置</button>
    {servers.map(item=><article key={item.id}><strong>{item.name}</strong><p>{item.transport==='stdio'?'本地程序':'准确 HTTPS 服务'} · {serverStatus[item.status]}</p><p>工具 {item.tools_count} 个，被阻止 {item.blocked_count} 个。{item.reason??''}</p><small>专用令牌：{item.credential_configured?'已配置':'匿名'} · {item.id}</small></article>)}
    <label>当前 MCP 服务<select aria-label="当前 MCP 服务" disabled={busy} value={sid} onChange={e=>setSid(e.target.value)}>{servers.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <div className="row"><button disabled={busy||!sid} onClick={()=>void act(async()=>{setPreview(undefined);setReview(undefined);const r=await window.orvia.mcpConnect({server_id:sid});if(r.ok){if(r.result.cancelled)setNotice('已取消连接，未启动或请求服务。');else if(r.result.result){setReview(r.result.result);setTool(r.result.result.tools.find(item=>item.allowed)?.name??'');setNotice('服务已初始化，准确工具清单等待单独原生审查。');}}else setNotice(r.message);})}>原生批准连接并发现工具</button>
    <button disabled={busy||!sid} onClick={()=>void act(async()=>{setReview(undefined);setPreview(undefined);const r=await window.orvia.mcpDisconnect({server_id:sid});setNotice(r.ok?(r.result.closed&&r.result.children_reaped?'连接与自有进程已关闭。':'服务关闭或进程回收尚未确认，请核对状态。'):r.message);})}>关闭此服务连接</button>
    <button disabled={busy||!sid} onClick={()=>void act(async()=>{const r=await window.orvia.mcpRemove({server_id:sid});if(r.ok){setNotice(r.result.cancelled?'已取消移除。':'本机配置与专用令牌已移除，外部数据和程序保留。');if(!r.result.cancelled){setReview(undefined);setPreview(undefined);}}else setNotice(r.message);})}>移除此服务配置</button></div>
    <h4>独立加密服务令牌（仅 HTTPS）</h4><p>{!credentials?.loaded?'凭据仓库未成功加载，禁止覆盖保存。':credentials.encryption_available?'系统加密可用；不会读取角色密钥或开发环境文件。':'系统加密不可用，禁止保存；匿名服务仍可使用。'}</p>
    <label>此服务专用令牌<input aria-label="此服务专用令牌" type="password" autoComplete="off" disabled={busy||server?.transport!=='https'||!credentials?.loaded||!credentials.encryption_available} maxLength={4096} value={token} onChange={e=>setToken(e.target.value)}/></label>
    <div className="row"><button disabled={busy||server?.transport!=='https'||!credentials?.loaded||!credentials.encryption_available||!token.trim()} onClick={()=>void act(async()=>{const key=token;setToken('');setReview(undefined);setPreview(undefined);const r=await window.orvia.mcpCredentialSave({server_id:sid,key});setNotice(r.ok?(r.result.cancelled?'已取消保存令牌。':'令牌已加密保存，旧服务连接与批准已失效。'):r.message);})}>原生批准保存专用令牌</button>
    <button disabled={busy||server?.transport!=='https'||!credentials?.configured.includes(sid)||!credentials.encryption_available} onClick={()=>void act(async()=>{setToken('');setReview(undefined);setPreview(undefined);const r=await window.orvia.mcpCredentialRemove({server_id:sid});setNotice(r.ok?(r.result.cancelled?'已取消移除令牌。':'令牌已移除，旧服务连接与批准已失效。'):r.message);})}>移除此服务专用令牌</button></div>
    {review&&<article aria-label="MCP 准确工具清单"><h4>本次准确工具清单</h4><p>会话身份：{review.session_id}。只读名称、schema 和 hint 只能用于限制准入，不能证明服务器行为。</p>{review.tools.map(item=><details key={item.name}><summary>{item.name} · {item.allowed?'符合配置，仍待原生批准':'被阻止'}</summary>{item.blocked_reason&&<p>阻止原因：{item.blocked_reason}</p>}<label>工具准确结构<textarea aria-label={`工具准确结构 ${item.name}`} readOnly rows={6} value={JSON.stringify(item.metadata,null,2)}/></label></details>)}
      <button disabled={busy} onClick={()=>void act(async()=>{const current=review;const r=await window.orvia.mcpApproveTools({server_id:sid,revision:current.revision});setReview(undefined);setNotice(r.ok?(r.result.cancelled?'已取消工具批准，请重新连接审查。':'准确清单已审查，每次调用仍须参数批准。'):r.message);})}>原生审查此工具清单</button></article>}
    <h4>准确只读工具调用</h4><label>MCP 调用所属会话<select aria-label="MCP 调用所属会话" disabled={busy} value={cid} onChange={e=>setCid(e.target.value)}>{chats.map(chat=><option key={chat.id} value={chat.id}>{chat.title}</option>)}</select></label>
    <label>准确工具名称<input aria-label="准确工具名称" disabled={busy} value={tool} maxLength={100} onChange={e=>{setTool(e.target.value);setPreview(undefined);}}/></label>
    <label>工具参数（JSON，最多 8 KiB）<textarea aria-label="工具参数（JSON，最多 8 KiB）" disabled={busy} rows={5} maxLength={8192} value={args} onChange={e=>{setArgs(e.target.value);setPreview(undefined);}}/></label>
    <button disabled={busy||!cid||!sid||server?.status!=='ready'||!tool} onClick={()=>void act(async()=>{setPreview(undefined);setExecution(undefined);const argumentsValue:unknown=JSON.parse(args);if(!argumentsValue||typeof argumentsValue!=='object'||Array.isArray(argumentsValue)){setNotice('参数必须是 JSON 对象。');return;}const r=await window.orvia.mcpCallPreview({id:cid,server_id:sid,tool,arguments:argumentsValue as Record<string,unknown>});if(r.ok){setPreview(r.result);setNotice('准确调用预览已准备，请核对服务、工具结构与参数。');}else setNotice(r.message);})}>准备 MCP 调用准确预览</button>
    {preview&&<article aria-label="MCP 调用准确预览"><h4>此次准确调用</h4><label>MCP 调用完整正文<textarea aria-label="MCP 调用完整正文" readOnly rows={12} value={JSON.stringify(preview,null,2)}/></label>
      <button disabled={busy} onClick={()=>void act(async()=>{const approved=preview;setPreview(undefined);const r=await window.orvia.mcpCall({id:cid,server_id:sid,revision:approved.revision});if(r.ok){if(r.result.cancelled)setNotice('已取消，MCP 工具未调用。');else if(r.result.result){setExecution(r.result.result);setNotice(executionStatus[r.result.result.status]);await savedHistory();}}else setNotice(r.message);})}>原生批准此 MCP 工具调用</button></article>}
    {execution&&<div aria-label="MCP 调用事实"><Execution item={execution}/></div>}
    <details><summary>本会话 MCP 调用记录（最多十六条）</summary>{history.map(item=><Execution key={`${item.server_id}:${item.revision}`} item={item}/>)}</details>
    <p role="status">{notice}</p>
  </section>;
}
