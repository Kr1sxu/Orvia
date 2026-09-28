import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { HealthReply, Settings, Role } from '../shared/api';
import type { Mission } from '../main/contracts';
import './style.css';

function App() {
  const [reply, setReply] = useState<HealthReply>();
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState<Settings>();
  const [missions, setMissions] = useState<Mission[]>([]);
  const [title, setTitle] = useState('');
  const [draftId, setDraftId] = useState(() => crypto.randomUUID());
  const [notice, setNotice] = useState('');
  const [role, setRole] = useState<Role>('main');
  const [key, setKey] = useState('');
  const [saving, setSaving] = useState(false);
  async function loadData() {
    const [configuration, drafts] = await Promise.all([window.orvia.settings(), window.orvia.missions()]);
    if (configuration.ok) setSettings(configuration.result); else setNotice(configuration.message);
    if (drafts.ok) setMissions(drafts.result.missions); else setNotice(drafts.message);
  }
  async function check() {
    setBusy(true);
    try { setReply(await window.orvia.health()); await loadData(); }
    catch { setReply({ ok: false, message: '桌面通信失败，请重新启动应用' }); }
    finally { setBusy(false); }
  }
  // 首次挂载通过唯一业务接口请求真实后端，不在渲染端启动进程。
  useEffect(() => { void check(); }, []);
  async function createDraft(event: React.FormEvent) {
    event.preventDefault(); setSaving(true); setNotice('');
    try {
      const result = await window.orvia.createMission({ title, client_request_id: draftId });
      if (result.ok) { setTitle(''); setDraftId(crypto.randomUUID()); await loadData(); setNotice('草稿已保存，三个角色的模型配置已固定。'); }
      else setNotice(result.message);
    } catch { setNotice('保存失败，请检查本地连接。'); }
    finally { setSaving(false); }
  }
  async function changeCredential(remove: boolean) {
    setSaving(true); setNotice('');
    // 发起调用后立即清空输入，不在设置状态、消息或任务中保存明文 Key。
    const pending = remove ? window.orvia.removeCredential(role) : window.orvia.saveCredential({ role, key });
    setKey('');
    try { const result = await pending; setNotice(result.ok ? '凭据已更新。' : result.message); if (result.ok) await loadData(); }
    catch { setNotice('凭据更新失败，请重启应用检查状态。'); }
    finally { setSaving(false); }
  }
  return <main>
    <header><span className="mark">序</span><span>序航 <b>Orvia</b></span><span className="tag">M07 · 开发预览</span></header>
    <section className="intro"><p className="eyebrow">从连接开始，循序启航</p><h1>你的本地工作助手</h1><p>先准备模型配置与任务草稿，桌面整理将在后续模块开放。</p></section>
    <section className="card"><div className="card-heading"><h2>本地服务</h2><span className={`badge ${reply?.ok ? 'online' : ''}`}>{busy ? '检查中' : reply?.ok ? '已连接' : '未连接'}</span></div>
      <div className="route"><span>Electron 窗口</span><i>→</i><span>受限 IPC</span><i>→</i><span>Python 后端</span></div>
      <p role="status">{busy ? '正在检查本地后端…' : reply?.ok ? '健康检查通过 · orvia-backend' : reply?.message ?? '等待连接'}</p>
      <button disabled={busy} onClick={() => void check()}>重新检查连接</button>
    </section>
    <section className="card settings"><h2>模型与凭据</h2><p className="hint">每个草稿固定三个角色的模型配置。模型请求会发送必要文本到对应云服务。</p>
      {settings?.credential_error && <p className="error">{settings.credential_error}</p>}
      <div className="profiles">{settings?.profiles.map(profile => <article key={profile.role}>
        <div><strong>{profile.role === 'main' ? 'Main Agent' : profile.role === 'computer' ? 'Computer Agent' : 'Browser Agent'}</strong><span className="badge">{profile.configured ? '已配置' : '缺少凭据'}</span></div>
        <p>{profile.model}</p><small>{profile.base_url}</small>
      </article>)}</div>
      {settings?.mode === 'development' ? <p className="hint">开发模式：凭据来自项目根目录 .env.local。修改后重启应用；界面不显示或写入密钥。</p> : settings && <div className="credential-form">
        <label>凭据类型<select value={role} onChange={event => setRole(event.target.value as Role)}><option value="main">Main</option><option value="computer">Computer</option><option value="browser">Browser</option><option value="tavily">Tavily 搜索</option></select></label>
        <label>API Key<input type="password" autoComplete="off" value={key} onChange={event => setKey(event.target.value)} maxLength={4096} /></label>
        <button disabled={saving || !key || !settings.encryption_available} onClick={() => void changeCredential(false)}>加密保存</button>
        <button disabled={saving || !settings.encryption_available} onClick={() => void changeCredential(true)}>移除凭据</button>
        {!settings.encryption_available && <p className="error">系统安全存储不可用，不能保存凭据。</p>}
      </div>}
      <p className="hint">{settings?.search_available ? 'Tavily 已配置；搜索与网页读取目前仅提供后端接口。' : '未配置 Tavily，搜索不可用；公开网页读取不需要搜索凭据。'}</p>
    </section>
    <section className="card drafts"><h2>任务草稿</h2><p className="hint">草稿仅在本地保存名称和模型配置。此阶段不会调用模型或执行文件操作。</p>
      <form onSubmit={event => void createDraft(event)}><label htmlFor="mission-title">草稿名称</label><div className="draft-form"><input id="mission-title" value={title} onChange={event => { setTitle(event.target.value); setDraftId(crypto.randomUUID()); }} maxLength={200} placeholder="例如：整理桌面资料" required /><button disabled={saving || !title.trim() || !reply?.ok}>保存草稿</button></div></form>
      <p aria-live="polite" className="notice">{notice}</p>
      <ul className="mission-list">{missions.map(mission => <li key={mission.id}><span>{mission.title}</span><small>草稿 · {mission.models.length} 个固定模型</small></li>)}</ul>
      {!missions.length && <p className="hint">还没有草稿。</p>}
    </section>
    <footer>当前仅保存任务草稿 · 不操作用户文件 · 不自动调用模型</footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<App />);
