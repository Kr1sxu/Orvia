import {describe,it,expect} from 'vitest';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {ModuleKind,transpileModule} from 'typescript';
import {M18Workspace,M18PlanReview,M18RequestReview,M18DesktopControlOptions,pickDesktopControl} from '../src/renderer/M18Cards';
import type {AutomationPlan,AutomationObservation,BrowserPending} from '../src/main/m18-contracts';

const cid='6f1b7524-1eac-4567-a6b5-c3c9f563052c',revision='a'.repeat(64);

describe('M18 三能力审查界面与隔离桥',()=>{
  it('同一模块呈现脚本、桌面和浏览器边界，执行不能从模型或页面内容获得授权',()=>{
    const html=renderToStaticMarkup(React.createElement(M18Workspace,{cid,authorized:false,disabled:false,notice:()=>{},refresh:async()=>{}}));
    for(const label of ['任意脚本：Python隔离执行','桌面点击：准确应用与控件','浏览器写操作：专用会话与实际外发','执行账本与取消','完整Python源码','原生选择并授权桌面应用','原生授权并打开专用浏览器'])expect(html).toContain(label);
    expect(html).toContain('每个写步骤由原生窗口确认');
    expect(html).toContain('不复用个人Cookie');
    expect(html).toContain('可能无法撤销');
    expect(html).not.toContain('<script');
  });
  it('完整源码和实际请求采用转义文本，预览不会伪装为已执行或已发送',()=>{
    const plan:AutomationPlan={operation_id:cid,revision,status:'awaiting_approval',plan:{kind:'script',source:'print("<script>forbidden()</script>")\n# 合成\n',network:false,inputs:[]}};
    const html=renderToStaticMarkup(React.createElement(M18PlanReview,{plan,label:'脚本',blocked:false,approve:()=>{}}));
    expect(html).toContain('等待原生逐步确认');expect(html).toContain('完整Python源码');
    expect(html).toContain('&lt;script&gt;forbidden()&lt;/script&gt;');expect(html).not.toContain('<script>');
    const pending:BrowserPending={status:'awaiting_approval',pending_request:{request_id:cid,revision,url:'https://synthetic.example/submit',method:'POST',fields:[{name:'text',value:'<img src=x onerror=bad()>'},{name:'password',value:'[敏感字段已隐藏]'}],bytes:128,sha256:revision,sensitive_redacted:true,category:'transaction',fields_truncated:true,body_preview_complete:false,preview_notice:'预览不完整，不能视作全量正文',files:[{field:'file',name:'synthetic.txt',bytes:16,sha256:revision}]},observation:null,result:null};
    const request=renderToStaticMarkup(React.createElement(M18RequestReview,{pending,blocked:false,decide:()=>{}}));
    expect(request).toContain('尚未发送');expect(request).toContain('购买或交易');expect(request).toContain('正文SHA256');
    expect(request).toContain('&lt;img');expect(request).not.toContain('<img');expect(request).toContain('不会发送');
    expect(request).toContain('不能视作全量正文');expect(request).toContain('实际待上传文件');expect(request).toContain('synthetic.txt');
  });
  it('preload只暴露固定M18频道，没有通用IPC、任意脚本执行或路径选择参数接口',async()=>{
    let exposed:Record<string,(input:unknown)=>Promise<unknown>>={};const calls:{channel:string;input:unknown}[]=[];
    const source=fs.readFileSync(path.resolve('apps/desktop/src/main/preload.ts'),'utf8');
    const compiled=transpileModule(source,{compilerOptions:{module:ModuleKind.CommonJS}}).outputText;
    vm.runInNewContext(compiled,{exports:{},require:(module:string)=>{if(module!=='electron')throw new Error('unexpected module');return{
      contextBridge:{exposeInMainWorld:(name:string,value:typeof exposed)=>{expect(name).toBe('orvia');exposed=value;}},
      ipcRenderer:{invoke:async(channel:string,input:unknown)=>{calls.push({channel,input});return{ok:true,result:{}};}}
    };}});
    expect(Object.isFrozen(exposed)).toBe(true);
    for(const forbidden of ['invoke','send','execute','evaluate','readFile','initialize','credentials'])expect(exposed).not.toHaveProperty(forbidden);
    const names=['ScriptPreview','ScriptFile','ScriptModelPreview','ScriptModelGenerate','ScriptExecute','ScriptStatus','ScriptExport','DesktopChoose','DesktopObserve','DesktopPreview','DesktopExecute','BrowserOpen','BrowserObserve','BrowserPending','BrowserPreview','BrowserExecute','BrowserRequest','BrowserOrigin','BrowserClose','Cancel','History'];
    const input={id:cid};
    for(const suffix of names){await exposed['m18'+suffix](input);expect(calls.at(-1)?.channel).toBe('orvia:m18-'+suffix.replace(/[A-Z]/g,(c,index)=>(index?'-':'')+c.toLowerCase()));expect(calls.at(-1)?.input).toBe(input);}
    expect(calls).toHaveLength(names.length);
  });
  it('保存框仅给save_new开放已识别Save按钮，重新观察淘汰失效或受保护的旧控件',()=>{
    const observation:AutomationObservation={grant_id:cid,state_hash:revision,file_dialog:true,controls:[
      {control_id:'filename',name:'文件名',patterns:['value'],blocked_reason:'file_dialog'},
      {control_id:'save',name:'保存',patterns:['invoke'],blocked_reason:'file_dialog',save_button:true},
      {control_id:'password',name:'受保护控件',patterns:[],blocked_reason:'password',save_button:true},
      {control_id:'disabled-save',name:'禁用保存',patterns:['invoke'],blocked_reason:'file_dialog',save_button:true,enabled:false}
    ]};
    const options=renderToStaticMarkup(React.createElement(M18DesktopControlOptions,{observation,action:'save_new'})).split('</option>');
    expect(options.find(x=>x.includes('value="save"'))).not.toContain('disabled');
    for(const id of ['filename','password','disabled-save'])expect(options.find(x=>x.includes(`value="${id}"`))).toContain('disabled');
    expect(pickDesktopControl(observation,'old-control','save_new')).toBe('save');
    expect(pickDesktopControl(observation,'password','save_new')).toBe('save');
    expect(pickDesktopControl(observation,'save','invoke')).toBe('');
    expect(pickDesktopControl({...observation,file_dialog:false},'save','save_new')).toBe('');
  });
});
