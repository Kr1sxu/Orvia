import React,{useEffect,useState} from 'react';
import type {AuxiliaryStatus} from '../main/auxiliary-contracts';

const reasons={unavailable:'本地服务不可用，请检查部署与端口。',authentication_required:'服务需要独立 Redis 密码。',authentication_failed:'Redis 认证失败，请检查独立凭据。',unsupported:'辅助配置或服务命令不兼容。',timeout:'连接检查超时。',storage_unavailable:'本地状态存储暂不可用，请检查磁盘或稍后重试。'};
const taskStates={pending:'处理中',waiting_input:'等待信息',waiting_approval:'等待批准',completed:'已结束（具体结果见会话）',cancelled:'已取消',failed:'失败',interrupted:'已中断'};
/** 轮询仅读取后端已知状态，绝不以设置页刷新自动重连或重放任务。 */
export function AuxiliaryPanel(){
  const [status,setStatus]=useState<AuxiliaryStatus>();
  const [host,setHost]=useState<'127.0.0.1'|'::1'>('127.0.0.1');
  const [port,setPort]=useState('6379'),[db,setDb]=useState('0');
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  useEffect(()=>{
    let active=true;
    const read=async(initial=false)=>{try{const r=await window.orvia.auxiliaryStatus();if(!active)return;if(r.ok){setStatus(r.result);if(initial){setHost(r.result.host);setPort(String(r.result.port));setDb(String(r.result.db));}}else setNotice(r.message);}catch{if(active)setNotice('辅助状态暂不可用。');}};
    void read(true);const timer=setInterval(()=>void read(),3000);
    return()=>{active=false;clearInterval(timer);};
  },[]);
  async function change(action:'enable'|'disable'|'probe'){
    setBusy(true);setNotice('');
    try{
      const r=action==='probe'?await window.orvia.auxiliaryProbe():await window.orvia.auxiliaryConfigure(action==='disable'&&status?{enabled:false,host:status.host,port:status.port,db:status.db}:{enabled:action==='enable',host,port:Number(port),db:Number(db)});
      if(r.ok)setStatus(r.result);else setNotice(r.message);
    }catch{setNotice('辅助设置未更新，请检查本地连接。');}finally{setBusy(false);}
  }
  const valid=/^\d+$/.test(port)&&Number(port)>=1&&Number(port)<=65535&&/^\d+$/.test(db)&&Number(db)<=15;
  return <section aria-label="Redis 辅助服务" className="auxiliary-panel">
    <h3>Redis 辅助服务（可选）</h3>
    <p>连接用户自行部署的本地服务。缓存与通知仅用于状态刷新；任务、证据和审批事实仍保存在 SQLite。</p>
    <p role="status">{!status?'正在读取辅助状态…':status.state==='disabled'?'未启用；使用 SQLite 本地模式。':status.state==='connected'?'已连接 Redis；SQLite 保留事实。':'Redis 已降级；使用 SQLite 本地通知。'}</p>
    {status?.reason&&<p className="error">{reasons[status.reason]}</p>}
    <div className="row">
      <label>本地地址<select disabled={busy} value={host} onChange={e=>setHost(e.target.value as typeof host)}><option>127.0.0.1</option><option>::1</option></select></label>
      <label>Redis 端口<input type="number" min="1" max="65535" disabled={busy} value={port} onChange={e=>setPort(e.target.value)}/></label>
      <label>数据库编号<input type="number" min="0" max="15" disabled={busy} value={db} onChange={e=>setDb(e.target.value)}/></label>
    </div>
    <p>独立密码：{status?.password_configured?'已配置':'未配置'}。开发版在 .env.local 设置 REDIS_PASSWORD 后重启；发布版在凭据类型中选择 Redis 加密保存。</p>
    <div className="row"><button disabled={busy||!status||!valid} onClick={()=>void change('enable')}>保存并启用连接</button><button disabled={busy||!status?.enabled} onClick={()=>void change('disable')}>关闭辅助连接</button><button disabled={busy||!status?.enabled} onClick={()=>void change('probe')}>检测并恢复连接</button></div>
    <p>这些操作只改变 Orvia 的连接，不启停 Redis 进程。</p>
    {status&&<details><summary>辅助服务详情</summary><p>缓存命中 {status.cache_hits}，未命中 {status.cache_misses}；Redis 通知发布 {status.notifications_published}，核对 {status.notifications_processed}，丢弃 {status.notifications_discarded}；本地通知核对 {status.local_notifications_processed}；本地任务元数据 {status.metadata_count}。</p><p>缓存 30 秒，通知最多 256 条、60 秒；计数仅属于本次后端进程，不表示执行完成。</p><h4>最近核对的任务状态</h4>{status.recent_tasks.length?<ul>{status.recent_tasks.map((task,index)=><li key={task.task_id}>任务 {index+1}：{taskStates[task.status]}</li>)}</ul>:<p>暂无任务状态通知。</p>}</details>}
    {notice&&<p role="status">{notice}</p>}
  </section>;
}
