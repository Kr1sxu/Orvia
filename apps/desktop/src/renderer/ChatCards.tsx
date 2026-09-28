import React from 'react';
import type { ChatMessage, Conversation, ReadCall } from '../main/chat-contracts';

export function bytes(value: unknown) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '未知';
  if (n < 1024) return n + ' B';
  if (n < 1024 ** 2) return (n / 1024).toFixed(1) + ' KB';
  if (n < 1024 ** 3) return (n / 1024 ** 2).toFixed(1) + ' MB';
  return (n / 1024 ** 3).toFixed(2) + ' GB';
}
function records(value: unknown): Record<string, unknown>[] { return Array.isArray(value) ? value.filter(v => v && typeof v === 'object') : []; }
function obj(value: unknown): Record<string, unknown> { return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}; }

export function EvidenceCard({message}:{message:ChatMessage}) {
  const data=message.data ?? {};
  const verify=obj(data.verify);
  return <details><summary>{message.kind==='plan'?'历史计划（审批以当前版本为准）':'执行 / 核验事实'}</summary>
    {message.kind==='plan' ? <ol>{records(data.actions).map((a,i)=><li key={i}>{a.kind==='mkdir'?'创建目录':a.kind==='rename'?'重命名':'移动'}：{a.source?String(a.source)+' → ':''}{String(a.destination)}</li>)}</ol> : <div>
      <p>{data.success===true?'程序核验通过':'未全部完成，请查看当前任务状态。'}{'completed' in data?' · 完成 '+String(data.completed)+' 步':''}{'undone' in data?' · 撤销 '+String(data.undone)+' 步':''}</p>
      {records(verify.checks).length>0&&<ol>{records(verify.checks).map((check,i)=><li key={i}>步骤 {Number(check.sequence)+1}：目标身份{check.destination_exists?'匹配':'不匹配'}，源位置{check.source_absent?'已清空':'仍存在'}</li>)}</ol>}
    </div>}
  </details>;
}

/** 工具结果只作为文本/表格渲染，不执行文件名、模型文本或 HTML。 */
export function ScanCard({message, inspect, disabled}: {message: ChatMessage; inspect: (call: ReadCall) => void; disabled: boolean}) {
  const envelope = message.data ?? {};
  const data = obj(envelope.data ?? envelope);
  const entries = records(data.entries);
  const large = records(data.large_files);
  const partial = envelope.complete === false || envelope.truncated === true;
  return <div className="result-card">
    <div className="row between"><strong>本地观察结果</strong><span className={partial ? 'warning' : 'badge'}>{partial ? '部分结果' : '已返回'}</span></div>
    <p className="muted">扫描 {String(envelope.scanned_entries ?? '—')} 项 · {String(envelope.scanned_at ?? '')}</p>
    {partial && <p className="warning">扫描预算、输出上限或不可访问项限制了结果，不能视作全部文件。</p>}
    {records(envelope.errors).length > 0 && <p className="warning">不可访问或跳过项：{records(envelope.errors).map(e => String(e.code)).join('、')}</p>}
    {'entries' in data && <><h4>文件列表 / 搜索结果</h4>{entries.length ? <div className="table-wrap"><table><thead><tr><th>相对路径</th><th>类型</th><th>大小</th><th>操作</th></tr></thead><tbody>{entries.map((entry, i) => <tr key={i}><td>{String(entry.path)}</td><td>{entry.kind === 'directory' ? '目录' : '文件'}</td><td>{entry.kind === 'directory' ? '—' : bytes(entry.size)}</td><td><button disabled={disabled} onClick={() => inspect({tool:'get_file_metadata',arguments:{path:String(entry.path)}})}>属性</button>{entry.kind === 'directory' && <button disabled={disabled} onClick={() => inspect({tool:'list_directory',arguments:{path:String(entry.path),limit:100}})}>查看</button>}</td></tr>)}</tbody></table></div> : <p>没有匹配项目。</p>}</>}
    {'total_bytes' in data && <><div className="metric"><strong>{bytes(data.total_bytes)}</strong><span>{String(data.file_count)} 个文件 · 逻辑大小，不代表可释放空间</span></div><h4>大文件（按大小排序）</h4>{large.length ? <ul className="files">{large.map((entry,i) => <li key={i}><span>{String(entry.path)}</span><b>{bytes(entry.size)}</b><button disabled={disabled} onClick={() => inspect({tool:'get_file_metadata',arguments:{path:String(entry.path)}})}>属性</button></li>)}</ul> : <p>没有符合阈值的大文件。</p>}<details><summary>按类型与目录统计</summary>{['extensions','groups'].map(key => <ul key={key}>{records(data[key]).map((g,i) => <li key={i}>{String(g.name)} · {bytes(g.bytes)} · {String(g.file_count)} 个文件</li>)}</ul>)}</details></>}
    {'modified_at' in data && <dl><dt>相对路径</dt><dd>{String(data.path)}</dd><dt>类型</dt><dd>{data.kind === 'directory' ? '目录' : '文件'}</dd><dt>大小</dt><dd>{data.kind === 'directory' ? '目录大小请查看空间统计' : bytes(data.size)}</dd><dt>修改时间</dt><dd>{String(data.modified_at)}</dd></dl>}
  </div>;
}

export function PlanCard({operation, disabled, act}: {operation: NonNullable<Conversation['operation']>; disabled: boolean; act:(kind:'approve'|'resume'|'undo')=>void}) {
  const labels: Record<string,string> = {planned:'等待审批',awaiting_approval:'等待审批',approved:'已批准',running:'执行中',completed:'已完成',failed:'失败',interrupted:'已中断',undone:'已撤销',partially_undone:'部分撤销'};
  return <section className="plan-card" aria-label="当前操作计划"><div className="row between"><h3>当前操作计划</h3><span className="badge">{labels[operation.status] ?? operation.status}</span></div>
    <p className="muted">版本 {operation.revision.slice(0,12)} · {operation.actions.length} 个动作</p>
    <ol>{operation.actions.map((a,i) => <li key={i}><b>{a.kind === 'mkdir' ? '创建目录' : a.kind === 'rename' ? '重命名' : '移动'}</b> {a.source && <><code>{a.source}</code> → </>}<code>{a.destination}</code></li>)}</ol>
    <p>批准将改变上述文件的位置或名称。请核对源和目标；拒绝覆盖、删除和跨卷移动。文本回复“同意”不会执行。</p>
    {operation.error && <p className="error">{operation.error}</p>}
    <div className="row">{['planned','awaiting_approval'].includes(operation.status) && <button className="primary" disabled={disabled} onClick={() => act('approve')}>批准此版本并执行</button>}
    {operation.status === 'interrupted' && <button disabled={disabled} onClick={() => act('resume')}>核验并恢复此任务</button>}
    {operation.status === 'completed' && <button disabled={disabled} onClick={() => act('undo')}>撤销最近一次变更</button>}</div>
    {disabled && <p className="muted">执行前必须具备当前会话有效目录授权，且没有正在处理的请求。</p>}
  </section>;
}
