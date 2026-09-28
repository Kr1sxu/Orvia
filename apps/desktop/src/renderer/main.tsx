import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { HealthReply } from '../shared/api';
import './style.css';

function App() {
  const [reply, setReply] = useState<HealthReply>();
  const [busy, setBusy] = useState(false);
  async function check() {
    setBusy(true);
    try { setReply(await window.orvia.health()); }
    catch { setReply({ ok: false, message: '桌面通信失败，请重新启动应用' }); }
    finally { setBusy(false); }
  }
  // 首次挂载通过唯一业务接口请求真实后端，不在渲染端启动进程。
  useEffect(() => { void check(); }, []);
  return <main>
    <header><span className="mark">序</span><span>序航 <b>Orvia</b></span><span className="tag">M01 · 开发预览</span></header>
    <section className="intro"><p className="eyebrow">从连接开始，循序启航</p><h1>你的本地工作助手</h1><p>工程通信已就绪。桌面整理将在后续模块中逐步开放。</p></section>
    <section className="card"><div className="card-heading"><h2>本地服务</h2><span className={`badge ${reply?.ok ? 'online' : ''}`}>{busy ? '检查中' : reply?.ok ? '已连接' : '未连接'}</span></div>
      <div className="route"><span>Electron 窗口</span><i>→</i><span>受限 IPC</span><i>→</i><span>Python 后端</span></div>
      <p role="status">{busy ? '正在检查本地后端…' : reply?.ok ? '健康检查通过 · orvia-backend' : reply?.message ?? '等待连接'}</p>
      <button disabled={busy} onClick={() => void check()}>重新检查连接</button>
    </section>
    <footer>当前仅验证本地通信 · 不读取用户文件 · 不调用模型</footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<App />);
