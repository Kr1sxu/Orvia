import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { HealthReply, Settings, ScanEnvelope } from '../shared/api';
import type { Mission } from '../main/contracts';
import './style.css';

type Entry = { path: string; name: string; kind: 'file' | 'directory'; size: number; modified_at: string };
type ScanCall = { tool: 'list_directory' | 'search_files' | 'get_file_metadata' | 'analyze_directory_space'; arguments: Record<string, unknown> };
const emptyReply = <p className="empty">选择一个目录开始只读扫描。文件不会被修改。</p>;

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function App() {
  const [health, setHealth] = useState<HealthReply>();
  const [settings, setSettings] = useState<Settings>();
  const [missions, setMissions] = useState<Mission[]>([]);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [directory, setDirectory] = useState<{ mission_id: string; grant_id: string; root_label: string | null; calls_remaining: number }>();
  const [scan, setScan] = useState<ScanEnvelope>();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Entry>();
  const [detail, setDetail] = useState<Record<string, unknown>>();
  const [space, setSpace] = useState<Record<string, unknown>>();

  async function load() {
    const [configuration, drafts] = await Promise.all([window.orvia.settings(), window.orvia.missions()]);
    if (configuration.ok) setSettings(configuration.result); else setNotice(configuration.message);
    if (drafts.ok) setMissions(drafts.result.missions); else setNotice(drafts.message);
  }
  useEffect(() => { void (async () => { try { setHealth(await window.orvia.health()); await load(); } catch { setNotice('本地服务不可用，请重新启动应用。'); } })(); }, []);

  async function callComputer(call: ScanCall) {
    if (!directory) return;
    setBusy(true); setNotice('正在扫描授权目录，结果会在完成后显示……'); setDetail(undefined);
    try {
      const result = await window.orvia.computerScan({ mission_id: directory.mission_id, grant_id: directory.grant_id, call });
      if (!result.ok) { setNotice(result.message); return; }
      setScan(result.result); setDirectory(value => value && { ...value, calls_remaining: result.result.calls_remaining });
      const data = result.result.data;
      if (Array.isArray(data.entries)) setEntries(data.entries as Entry[]);
      if (call.tool === 'analyze_directory_space') setSpace(data);
      setNotice(result.result.complete ? '扫描完成。' : `已返回部分结果：${result.result.truncated ? '达到扫描预算或输出上限。' : '目录中存在不可访问项。'}`);
    } catch { setNotice('扫描失败：目录可能已失效、无权限或超出授权范围。'); }
    finally { setBusy(false); }
  }
  async function chooseDirectory() {
    setBusy(true); setNotice('等待选择本地目录……'); setEntries([]); setScan(undefined); setSpace(undefined); setSelected(undefined);
    try {
      const result = await window.orvia.chooseDirectory();
      if (!result.ok) { setNotice(result.message); return; }
      if (result.result.cancelled || !result.result.mission_id || !result.result.grant_id) { setNotice('已取消目录选择。'); return; }
      setDirectory({ mission_id: result.result.mission_id, grant_id: result.result.grant_id, root_label: result.result.root_label ?? '已授权目录', calls_remaining: result.result.calls_remaining ?? 0 });
      setNotice('目录已授权，正在读取一级文件列表……');
      const initial = await window.orvia.computerScan({ mission_id: result.result.mission_id, grant_id: result.result.grant_id, call: { tool: 'list_directory', arguments: { path: '.', limit: 100 } } });
      if (initial.ok) { setScan(initial.result); setEntries(Array.isArray(initial.result.data.entries) ? initial.result.data.entries as Entry[] : []); setDirectory(value => value && { ...value, calls_remaining: initial.result.calls_remaining }); setNotice(initial.result.complete ? '扫描完成。' : '已返回部分结果，请留意截断提示。'); }
      else setNotice(initial.message);
    } catch { setNotice('目录授权失败：请重新选择普通本地目录。'); }
    finally { setBusy(false); await load(); }
  }
  async function inspect(entry: Entry) {
    setSelected(entry);
    if (!directory) return;
    const result = await window.orvia.computerScan({ mission_id: directory.mission_id, grant_id: directory.grant_id, call: { tool: 'get_file_metadata', arguments: { path: entry.path } } });
    if (result.ok) setDetail(result.result.data); else setNotice(result.message);
  }
  const largeFiles = useMemo(() => Array.isArray(space?.large_files) ? space.large_files as Entry[] : [], [space]);

  return <main>
    <header><span className="mark">序</span><span>序航 <b>Orvia</b></span><span className="tag">M09 · 桌面整理</span></header>
    <section className="intro"><p className="eyebrow">只读查看 · 明确授权 · 本地处理</p><h1>整理之前，先看清楚文件</h1><p>选择一个目录，查看文件清单、属性和空间占用。当前流程不会移动、重命名或删除任何文件。</p></section>
    <section className="card connection"><div className="card-heading"><h2>本地服务</h2><span className={`badge ${health?.ok ? 'online' : ''}`}>{health?.ok ? '已连接' : '未连接'}</span></div><p role="status">{health?.ok ? '健康检查通过 · orvia-backend' : health?.message ?? '正在连接……'}</p></section>
    <section className="card workspace"><div className="card-heading"><div><h2>授权目录</h2><p className="hint">主进程负责选择和校验目录，授权只在本次应用连接内有效。</p></div><button disabled={busy || !health?.ok} onClick={() => void chooseDirectory()}>选择目录</button></div>
      {directory ? <div className="authorized"><strong>{directory.root_label}</strong><span>剩余只读调用 {directory.calls_remaining}</span><small>任务 {directory.mission_id.slice(0, 8)}…</small></div> : emptyReply}
      {notice && <p aria-live="polite" className="notice">{notice}</p>}
    </section>
    <section className="card results"><div className="card-heading"><div><h2>文件列表</h2><p className="hint">{scan ? `${entries.length} 项 · 已扫描 ${scan.scanned_entries} 项` : '授权后显示目录内容'}</p></div><div className="actions"><input aria-label="文件名搜索" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索文件名" disabled={!directory || busy} /><button disabled={!directory || busy || !query.trim()} onClick={() => void callComputer({ tool: 'search_files', arguments: { path: '.', query: query.trim(), recursive: true, limit: 100 } })}>搜索</button></div></div>
      {entries.length ? <div className="table-wrap"><table><thead><tr><th>名称</th><th>类型</th><th>大小</th><th>修改时间</th></tr></thead><tbody>{entries.map(entry => <tr key={entry.path} onClick={() => void inspect(entry)} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') void inspect(entry); }}><td>{entry.name}</td><td>{entry.kind === 'directory' ? '目录' : '文件'}</td><td>{entry.kind === 'file' ? formatBytes(entry.size) : '—'}</td><td>{new Date(entry.modified_at).toLocaleString()}</td></tr>)}</tbody></table></div> : emptyReply}
      {scan && scan.errors.length > 0 && <p className="error">扫描提示：{scan.errors.map(error => error.code).join('、')}。部分路径可能无权访问。</p>}
    </section>
    <section className="split"><article className="card"><h2>文件属性</h2>{detail ? <dl><dt>相对路径</dt><dd>{String(detail.path)}</dd><dt>类型</dt><dd>{String(detail.kind)}</dd><dt>大小</dt><dd>{formatBytes(Number(detail.size))}</dd><dt>修改时间</dt><dd>{new Date(String(detail.modified_at)).toLocaleString()}</dd></dl> : <p className="empty">点击文件列表中的项目查看属性。</p>}</article><article className="card"><div className="card-heading"><h2>空间统计</h2><button disabled={!directory || busy} onClick={() => void callComputer({ tool: 'analyze_directory_space', arguments: { path: '.', top_n: 10, min_size: 1024 * 1024 } })}>刷新</button></div>{space ? <><div className="metric"><strong>{formatBytes(Number(space.total_bytes))}</strong><span>{String(space.file_count)} 个文件</span></div><h3>大文件</h3>{largeFiles.length ? <ul className="large-list">{largeFiles.map(item => <li key={item.path}><span>{item.name}</span><small>{formatBytes(item.size)}</small></li>)}</ul> : <p className="empty">没有达到 1 MB 的大文件。</p>}</> : <p className="empty">授权后可查看逻辑文件大小统计。</p>}</article></section>
    <details className="card technical"><summary>模型与草稿状态</summary><p className="hint">当前界面只执行 Computer 只读工具，不调用模型，不执行文件动作。</p><div className="profiles">{settings?.profiles.map(profile => <span key={profile.role}>{profile.role}: {profile.configured ? '已配置' : '未配置'} · {profile.model}</span>)}</div><p className="hint">本地草稿 {missions.length} 个；草稿不代表已执行任务。</p></details>
    <footer>只读扫描 · 不移动文件 · 不重命名 · 不删除 · 不自动调用模型</footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<App />);
