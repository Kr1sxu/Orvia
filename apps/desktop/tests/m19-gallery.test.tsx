import {it,expect} from 'vitest';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {ScanCard,PlanCard} from '../src/renderer/ChatCards';
import {SynthesisPreviewCard} from '../src/renderer/SynthesisCards';
import {PublicationResult} from '../src/renderer/PublicationCards';
import {M17Workspace} from '../src/renderer/M17Cards';
import {M18PlanReview,M18RequestReview,M18Workspace} from '../src/renderer/M18Cards';

it('renders actual approval/business components as escaped synthetic text, with disabled approvals preserved',()=>{
  const cid='6f1b7524-1eac-4567-a6b5-c3c9f563052c',revision='a'.repeat(64),noop=()=>{};
  const long='合成中文文件与mixed-text_0123456789'.repeat(18)+'<script>forbidden()</script>';
  const cards=<main className="gallery">
    <h1>M19 实际组件静态状态检查</h1><p>合成数据；SSR不执行事件、IPC、effect或模型，不能替代L3。</p>
    <div className="row"><button id="available">可用按钮</button><button disabled>禁用按钮</button><span className="badge" data-status="completed">程序核验完成</span><span className="badge" data-status="awaiting_approval">待审批</span><span className="badge" data-status="failed">失败</span><span className="progress"><i className="spinner"/>正在加载</span></div>
    <ScanCard message={{data:{data:{entries:[{path:long,kind:'file',size:12345}]},complete:false},text:'合成观察'} as any} disabled={true} inspect={noop}/>
    <PlanCard operation={{status:'awaiting_approval',revision,actions:[{kind:'rename',source:long,destination:'合成/结果.txt'}]} as any} disabled={true} act={noop}/>
    <SynthesisPreviewCard preview={{supplier:'deepseek-flash',question:long,fragments:[{citation:'[D1]',locator:'第1页',text:long}],coverage:[]} as any} disabled={true} confirm={noop} close={noop}/>
    <section className="result-card"><PublicationResult message={{data:{filename:'合成简报.pdf',format:'pdf',revision,message_id:cid,source_revision:revision,pages:2}} as any}/></section>
    <M17Workspace cid={cid} authorized={false} disabled={true} messages={[]} availableSources={[]} notice={noop} refresh={async()=>{}}/>
    <M18Workspace cid={cid} authorized={false} disabled={true} notice={noop} refresh={async()=>{}}/>
    <section className="m18-workspace"><M18PlanReview plan={{operation_id:cid,revision,status:'awaiting_approval',plan:{source:'print("<script>forbidden()</script>")\n# '+long,kind:'script',network:false,inputs:[]}}} label="脚本" blocked={true} approve={noop}/>
    <M18RequestReview pending={{pending_request:{request_id:cid,revision,url:'https://synthetic.example/submit',method:'POST',fields:[{name:'text',value:long}],bytes:1024,sha256:revision,category:'message'},status:'awaiting_approval'} as any} blocked={true} decide={noop}/></section>
  </main>;
  const html=renderToStaticMarkup(cards);
  expect(html).not.toContain('<script>');expect(html).toContain('&lt;script&gt;');
  expect(html).toMatch(/<button[^>]*disabled=""[^>]*>原生确认此/);
  let css=readFileSync('apps/desktop/src/renderer/style.css','utf8');
  css=css.replace(/url\('\.\/assets\/fonts\/([^']+)'\)/g,(_match,name)=>`url('${pathToFileURL(path.resolve('apps/desktop/src/renderer/assets/fonts',name)).href}')`);
  const folder=path.resolve('artifacts/test-results/M19/gallery');mkdirSync(folder,{recursive:true});
  writeFileSync(path.join(folder,'components.html'),`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; font-src file:"><style>${css}\n.gallery{max-width:900px;padding:24px;margin:auto}body{overflow:auto}</style>${html}</html>`);
});
