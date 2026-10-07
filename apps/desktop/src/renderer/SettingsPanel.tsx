import React, { useEffect, useRef, useState } from 'react';
import type { Settings, Role } from '../shared/api';
import {AuxiliaryPanel} from './AuxiliaryPanel';
import {SkillsPanel} from './SkillsPanel';
import {RetrievalPanel} from './RetrievalPanel';
import {MemoryPanel} from './MemoryPanel';
import {GraphPanel} from './GraphPanel';
import {RewritePanel} from './RewritePanel';
import {McpPanel} from './McpPanel';

/** 凭据只停留在输入框本轮内存，提交立即清空，不加入会话或通知。 */
export function SettingsPanel({settings, reload, close}: {settings?: Settings; reload: () => Promise<void>; close: () => void}) {
  const [role, setRole] = useState<Role>('main');
  const [key, setKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const panel=useRef<HTMLElement>(null);
  useEffect(()=>{
    const previous=document.activeElement as HTMLElement|null;
    panel.current?.querySelector<HTMLButtonElement>('button')?.focus();
    return ()=>previous?.focus();
  },[]);
  async function change(remove: boolean) {
    setBusy(true);
    const pending = remove ? window.orvia.removeCredential(role) : window.orvia.saveCredential({role, key});
    setKey('');
    try { const reply = await pending; setNotice(reply.ok ? '凭据已更新。' : reply.message); if (reply.ok) await reload(); }
    catch { setNotice('凭据同步失败，请重新启动应用检查状态。'); }
    finally { setBusy(false); }
  }
  return <div className="settings-overlay"><section ref={panel} role="dialog" aria-modal="true" aria-label="设置" className="settings-panel" onKeyDown={e=>{
    if(e.key==='Escape'&&!busy){e.preventDefault();close();}
    if(e.key==='Tab'){
      // 模态设置只在自身可用控件间移动焦点，避免键盘触发背后的会话操作。
      const nodes=panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled)');
      if(!nodes?.length){e.preventDefault();return;}
      const first=nodes[0],last=nodes[nodes.length-1];
      if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
      else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
    }
  }}>
    <div className="row between"><h2>设置</h2><button onClick={close} disabled={busy}>关闭设置</button></div>
    <p>三个角色使用各自固定模型。主动发送需求时，必要对话与已授权目录的文件元数据会发送给 Main 云服务；文件正文不会自动上传。</p>
    {settings?.credential_error && <p className="error">{settings.credential_error}</p>}
    <div className="profiles">{settings?.profiles.map(profile => <article key={profile.role}><strong>{profile.role}</strong><span>{profile.configured ? '已配置' : '缺少凭据'}</span><p>{profile.model}</p><small>{profile.base_url}</small></article>)}</div>
    {settings?.mode === 'development' ? <p>开发凭据来自根目录 .env.local，修改后重启应用。界面不显示密钥。</p> : <div className="credential-form">
      <label>凭据类型<select value={role} onChange={e => setRole(e.target.value as Role)}><option value="main">Main</option><option value="computer">Computer</option><option value="browser">Browser</option><option value="tavily">Tavily 搜索</option><option value="redis">Redis 独立密码</option></select></label>
      <label>API Key<input type="password" autoComplete="off" maxLength={4096} value={key} onChange={e => setKey(e.target.value)}/></label>
      <div className="row"><button disabled={busy || !key || !settings?.encryption_available} onClick={() => void change(false)}>加密保存</button><button disabled={busy || !settings?.encryption_available} onClick={() => void change(true)}>移除凭据</button></div>
      {!settings?.encryption_available && <p className="error">系统安全存储不可用，不能保存凭据。</p>}
    </div>}
    <p>{settings?.search_available ? 'Tavily 已配置；在对话输入框选择搜索网页。' : '未配置 Tavily，搜索不可用；仍可读取已知公开网页。'}</p>
    <AuxiliaryPanel/>
    <SkillsPanel/>
    <RetrievalPanel/>
    <MemoryPanel/>
    <GraphPanel/>
    <RewritePanel/>
    <McpPanel/>
    <p role="status">{notice}</p>
    <button disabled={busy} onClick={() => void reload().catch(() => setNotice('连接检查失败，请重新启动应用。'))}>重新检查连接</button>
  </section></div>;
}
