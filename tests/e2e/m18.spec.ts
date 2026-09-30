import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,writeFile,readFile} from 'node:fs/promises';
import {execFile,spawn} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';

test('M18 Electron原生审批与真实LPAC/UIA/Chromium闭环（外网和模型合成）',async()=>{
  test.setTimeout(180000);
  const results=path.resolve('artifacts/test-results/M18');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'electron-'));
  const nativeTemp=path.join(work,'native-temp');await mkdir(nativeTemp);
  const project=path.join(work,'synthetic-project');await mkdir(project);
  const source=path.join(project,'synthetic.py');await writeFile(source,"from pathlib import Path\nPath('output/result.txt').write_text('合成LPAC产物',encoding='utf-8')\nprint('合成脚本真实执行')\n");
  const selectedExport=path.join(project,'approved-export.txt'),counter=path.join(work,'requests.txt');await writeFile(counter,'0');
  const powershell=path.join(process.env.SystemRoot!,'System32/WindowsPowerShell/v1.0/powershell.exe');
  await promisify(execFile)(powershell,['-NoProfile','-NonInteractive','-File',path.resolve('tests/e2e/m18_desktop_fixture.ps1'),'-OutputDirectory',work,'-PrepareOnly'],{windowsHide:true,env:{...process.env,TEMP:nativeTemp,TMP:nativeTemp}});
  const fixture=spawn(path.join(work,'m18_desktop_fixture.exe'),['Orvia M18 Electron synthetic'],{stdio:'ignore',windowsHide:false});
  const env={...process.env,TEMP:nativeTemp,TMP:nativeTemp,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M18_PROJECT:project,ORVIA_M18_SOURCE:source,ORVIA_M18_EXPORT:selectedExport,ORVIA_M18_COUNTER:counter,ORVIA_M18_FIXTURE_PID:String(fixture.pid)};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete(env as NodeJS.ProcessEnv)[key];
  const app=await electron.launch({args:[path.resolve('tests/e2e/m18-launch.cjs')],env});
  try{
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'＋ 选择目录'}).click();
    await expect.poll(async()=>{const r=await page.evaluate(()=>window.orvia.chatList());return r.ok&&r.result.conversations.length>0;}).toBe(true);
    const cid=await page.evaluate(async()=>{const r=await window.orvia.chatList();if(!r.ok)throw Error(r.message);return r.result.conversations[0].id;});
    const invalid=await page.evaluate(id=>window.orvia.m18ScriptExecute({id,operation_id:crypto.randomUUID(),revision:'a'.repeat(64)}),cid);expect(invalid.ok).toBe(false);
    // 首次走真正界面与原生文件选择，读回源码原文，随后main/Python分别复核批准。
    const workspace=page.getByLabel('M18脚本桌面浏览器可控执行');
    await expect(workspace).toBeVisible();
    await workspace.getByText('任意脚本：Python隔离执行',{exact:true}).click();
    await workspace.getByRole('button',{name:'原生选择Python脚本',exact:true}).click();
    await expect(workspace.getByRole('textbox',{name:'M18 Python源码'})).toHaveValue(await readFile(source,'utf8'));
    await expect(workspace.getByLabel('脚本审批预览')).toContainText('合成LPAC产物');
    const preview=await page.evaluate(async id=>{const r=await window.orvia.m18History({id});if(!r.ok)throw Error(r.message);return r.result.operations.find(x=>x.kind==='script'&&x.status==='awaiting_approval')!;},cid);
    await page.screenshot({path:path.join(results,'m18-script-review.png')});
    await workspace.getByLabel('脚本审批预览').screenshot({path:path.join(results,'m18-script-plan.png')});
    const approval={id:cid,operation_id:preview.operation_id,revision:preview.revision};
    await workspace.getByRole('button',{name:'原生确认此脚本步骤',exact:true}).click();
    await expect.poll(async()=>{const r=await page.evaluate(q=>window.orvia.m18ScriptStatus(q),{id:cid,operation_id:preview.operation_id});if(r.ok&&r.result.status==='failed')throw Error(JSON.stringify({status:r.result.status,evidence:r.result.audit.evidence,error:r.result.result?.error}));return r.ok?r.result.status:r.message;},{timeout:60000}).toBe('completed');
    const fact=await page.evaluate(q=>window.orvia.m18ScriptStatus(q),{id:cid,operation_id:preview.operation_id});
    expect(fact.ok&&fact.result.result?.token_verified).toBe(true);expect(fact.ok&&fact.result.result?.processes_reaped).toBe(true);
    expect((await page.evaluate(q=>window.orvia.m18ScriptExecute(q),approval)).ok).toBe(false);
    expect((await page.evaluate(q=>window.orvia.m18ScriptExport(q),{...approval,index:0})).ok).toBe(true);
    expect(await readFile(selectedExport,'utf8')).toBe('合成LPAC产物');
    const picked=await page.evaluate(id=>window.orvia.m18DesktopChoose({id}),cid);
    if(!picked.ok||!picked.result.observation)throw Error(JSON.stringify(picked));
    let observed=picked.result.observation;
    for(const step of [{action:'set_value' as const,value:'synthetic Electron UIA',name:''},{action:'invoke' as const,value:'',name:'M18 apply'}]){
      const control=observed.controls.find(c=>step.name?c.name===step.name:c.control_type==='Edit'&&c.patterns?.includes('value'))!;
      const request={id:cid,grant_id:observed.grant_id!,control_id:control.control_id,action:step.action,value:step.value,state_hash:observed.state_hash,category:'local' as const,expectation:'APPLIED:synthetic Electron UIA'};
      const plan=await page.evaluate(q=>window.orvia.m18DesktopPreview(q),request);if(!plan.ok)throw Error(plan.message);
      const q={id:cid,operation_id:plan.result.operation_id,revision:plan.result.revision};
      expect((await page.evaluate(q=>window.orvia.m18DesktopExecute(q),q)).ok).toBe(true);
      await expect.poll(async()=>{const h=await page.evaluate(id=>window.orvia.m18History({id}),cid);return h.ok?h.result.operations.find(x=>x.operation_id===q.operation_id)?.status:h.message;},{timeout:25000}).toBe('completed');
      const fresh=await page.evaluate(q=>window.orvia.m18DesktopObserve(q),{id:cid,grant_id:observed.grant_id!});if(!fresh.ok)throw Error(fresh.message);observed=fresh.result;
    }
    expect(observed.controls.some(c=>c.name==='APPLIED:synthetic Electron UIA')).toBe(true);
    const opened=await page.evaluate(id=>window.orvia.m18BrowserOpen({id,url:'https://m18.example/',allowed_actions:['message'],get_write_paths:[]}),cid);
    if(!opened.ok||!opened.result.observation)throw Error(JSON.stringify(opened));
    const browser=opened.result.observation,sid=browser.session_id!,send=browser.controls.find(c=>c.name==='提交合成消息')!;
    const plan=await page.evaluate(q=>window.orvia.m18BrowserPreview(q),{id:cid,session_id:sid,control_id:send.control_id,action:'click',value:'',state_hash:browser.state_hash,category:'message',expectation:'合成消息完成:唯一回执'});
    if(!plan.ok)throw Error(plan.message);
    expect((await page.evaluate(q=>window.orvia.m18BrowserExecute(q),{id:cid,operation_id:plan.result.operation_id,revision:plan.result.revision})).ok).toBe(true);
    await expect.poll(async()=>{const p=await page.evaluate(q=>window.orvia.m18BrowserPending(q),{id:cid,session_id:sid});return p.ok&&!!p.result.pending_request;}).toBe(true);
    expect(await readFile(counter,'utf8')).toBe('0');
    const pending=await page.evaluate(q=>window.orvia.m18BrowserPending(q),{id:cid,session_id:sid});if(!pending.ok||!pending.result.pending_request)throw Error(JSON.stringify(pending));
    const actual=pending.result.pending_request;
    expect((await page.evaluate(q=>window.orvia.m18BrowserRequest(q),{id:cid,session_id:sid,request_id:actual.request_id,revision:actual.revision})).ok).toBe(true);
    await expect.poll(async()=>{await page.evaluate(q=>window.orvia.m18BrowserPending(q),{id:cid,session_id:sid});const h=await page.evaluate(id=>window.orvia.m18History({id}),cid);return h.ok?h.result.operations.find(x=>x.operation_id===plan.result.operation_id)?.status:h.message;},{timeout:20000}).toBe('completed');
    expect(await readFile(counter,'utf8')).toBe('1');
    expect((await page.evaluate(q=>window.orvia.m18BrowserRequest(q),{id:cid,session_id:sid,request_id:actual.request_id,revision:actual.revision})).ok).toBe(false);
    await page.evaluate(q=>window.orvia.m18BrowserClose(q),{id:cid,session_id:sid});
    // 拒绝原生步骤批准与取消账本均走真实main/Python，不能启动隔离执行或重放旧计划。
    await app.evaluate(()=>{process.env.ORVIA_M18_CANCEL='1';});
    const deniedPlan=await page.evaluate(q=>window.orvia.m18ScriptPreview(q),{id:cid,source:"print('synthetic denial')",inputs:[]});if(!deniedPlan.ok)throw Error(deniedPlan.message);
    const deniedApproval={id:cid,operation_id:deniedPlan.result.operation_id,revision:deniedPlan.result.revision};
    const denied=await page.evaluate(q=>window.orvia.m18ScriptExecute(q),deniedApproval);expect(denied.ok&&denied.result.cancelled).toBe(true);
    const notRun=await page.evaluate(q=>window.orvia.m18ScriptStatus(q),{id:cid,operation_id:deniedApproval.operation_id});expect(notRun.ok&&notRun.result.status).toBe('awaiting_approval');
    const cancelled=await page.evaluate(q=>window.orvia.m18Cancel(q),deniedApproval);expect(cancelled.ok&&cancelled.result.status).toBe('cancelled');
    expect((await page.evaluate(q=>window.orvia.m18ScriptExecute(q),deniedApproval)).ok).toBe(false);
    const deniedOpen=await page.evaluate(id=>window.orvia.m18BrowserOpen({id,url:'https://m18.example/',allowed_actions:['message'],get_write_paths:[]}),cid);expect(deniedOpen.ok&&deniedOpen.result.cancelled).toBe(true);
    // 独立批准控件后，实际外发仍可拒绝；合成HTTP计数保持1而不是2。
    await app.evaluate(()=>{delete process.env.ORVIA_M18_CANCEL;});
    const retryOpen=await page.evaluate(id=>window.orvia.m18BrowserOpen({id,url:'https://m18.example/',allowed_actions:['message'],get_write_paths:[]}),cid);if(!retryOpen.ok||!retryOpen.result.observation)throw Error(JSON.stringify(retryOpen));
    const rb=retryOpen.result.observation,rs=rb.session_id!,rc=rb.controls.find(c=>c.name==='提交合成消息')!;
    const rp=await page.evaluate(q=>window.orvia.m18BrowserPreview(q),{id:cid,session_id:rs,control_id:rc.control_id,action:'click',value:'',state_hash:rb.state_hash,category:'message',expectation:'合成消息完成:唯一回执'});if(!rp.ok)throw Error(rp.message);
    expect((await page.evaluate(q=>window.orvia.m18BrowserExecute(q),{id:cid,operation_id:rp.result.operation_id,revision:rp.result.revision})).ok).toBe(true);
    await expect.poll(async()=>{const p=await page.evaluate(q=>window.orvia.m18BrowserPending(q),{id:cid,session_id:rs});return p.ok&&!!p.result.pending_request;}).toBe(true);
    const rq=await page.evaluate(q=>window.orvia.m18BrowserPending(q),{id:cid,session_id:rs});if(!rq.ok||!rq.result.pending_request)throw Error(JSON.stringify(rq));
    await app.evaluate(()=>{process.env.ORVIA_M18_CANCEL='1';});
    const refused=await page.evaluate(q=>window.orvia.m18BrowserRequest(q),{id:cid,session_id:rs,request_id:rq.result.pending_request.request_id,revision:rq.result.pending_request.revision});expect(refused.ok&&refused.result.cancelled).toBe(true);
    expect(await readFile(counter,'utf8')).toBe('1');
    await page.evaluate(q=>window.orvia.m18BrowserClose(q),{id:cid,session_id:rs});
    await expect.poll(async()=>{const r=await page.evaluate(()=>window.orvia.chatList());return r.ok;}).toBe(true);
    await expect(page.getByRole('button',{name:/新建对话/})).toBeEnabled({timeout:10000});
    await page.screenshot({path:path.join(results,'m18-electron.png')});
  }finally{await app.close();fixture.kill();}
});
