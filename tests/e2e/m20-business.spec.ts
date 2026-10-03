/** M20自然业务L3：真Electron/stdio/SQLite/文件/LPAC/可见Chromium，仅模型网络和原生框替身。 */
import {_electron as electron,expect,test,type Page} from '@playwright/test';
import {mkdir,mkdtemp,readFile,writeFile,stat,utimes} from 'node:fs/promises';
import path from 'node:path';
import {execFile,spawn,type ChildProcess} from 'node:child_process';
import {promisify} from 'node:util';
import type {} from '../../apps/desktop/src/shared/api';

async function fixture(desktop=false){
  const results=path.resolve('artifacts/test-results/M20');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'business-')),project=path.join(work,'project');await mkdir(project);
  await writeFile(path.join(project,'alpha.txt'),'M20 rename synthetic identity');await writeFile(path.join(project,'App.tsx'),'export const App = () => <p>old synthetic</p>;');
  const source=path.join(project,'synthetic.py');await writeFile(source,"from pathlib import Path\nPath('output/file.txt').write_text('M20 synthetic file LPAC',encoding='utf-8')\nprint('synthetic file executed')\n");
  const local=path.join(work,'Local'),temp=path.join(local,'Temp');await mkdir(temp,{recursive:true});
  const old=path.join(temp,'old.tmp'),fresh=path.join(temp,'fresh.tmp'),other=path.join(temp,'old.txt');
  for(const item of [old,fresh,other])await writeFile(item,'M20 synthetic temporary file');
  const oldTime=new Date(Date.now()-40*24*3600*1000);await utimes(old,oldTime,oldTime);await utimes(other,oldTime,oldTime);
  const counter=path.join(work,'model-count.json'),networkCount=path.join(work,'network-count.txt'),dialogs=path.join(work,'dialogs.jsonl'),output=path.join(work,'approved-output.txt');await writeFile(networkCount,'0');
  const nativeTemp=path.join(work,'native-temp');await mkdir(nativeTemp);
  let nativeFixture:ChildProcess|undefined;
  if(desktop){const powershell=path.join(process.env.SystemRoot!,'System32/WindowsPowerShell/v1.0/powershell.exe');await promisify(execFile)(powershell,['-NoProfile','-NonInteractive','-File',path.resolve('tests/e2e/m18_desktop_fixture.ps1'),'-OutputDirectory',work,'-PrepareOnly'],{windowsHide:true,env:{...process.env,TEMP:nativeTemp,TMP:nativeTemp}});nativeFixture=spawn(path.join(work,'m18_desktop_fixture.exe'),['Orvia M20 business synthetic'],{stdio:'ignore',windowsHide:false});}
  const env:Record<string,string>={...Object.fromEntries(Object.entries(process.env).filter((pair):pair is [string,string]=>typeof pair[1]==='string')),TEMP:nativeTemp,TMP:nativeTemp,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M20_COUNTER:counter,
    ORVIA_M20_BUSINESS_PROJECT:project,ORVIA_M20_BUSINESS_SCRIPT:source,ORVIA_M20_BUSINESS_LOCAL:local,ORVIA_M20_BUSINESS_NETWORK_COUNT:networkCount,ORVIA_M20_BUSINESS_EXPORT:output,ORVIA_M20_BUSINESS_DIALOGS:dialogs};
  if(nativeFixture?.pid)env.ORVIA_M20_BUSINESS_FIXTURE_PID=String(nativeFixture.pid);
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete env[key];
  const app=await electron.launch({args:[path.resolve('tests/e2e/m20-business-launch.cjs'),`--user-data-dir=${env.ORVIA_DEV_DATA_DIR}`],env});
  const page=await app.firstWindow();try{await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible({timeout:30000});}catch(error){await writeFile(path.join(work,'startup-ui-synthetic.txt'),await page.locator('body').innerText(),'utf8');await app.close();nativeFixture?.kill();throw error;}
  const evidence=async(name:string,details:unknown)=>writeFile(path.join(work,name+'.json'),JSON.stringify({module:'M20',models:'httpx.MockTransport',nativeDialogs:'test launcher substitute',components:'real Electron/stdio/SQLite; other actual components specified per scenario',details},null,2),'utf8');
  return{app,page,work,project,source,old,fresh,other,output,counter,networkCount,dialogs,evidence,nativeFixture};
}
async function send(page:Page,text:string){const input=page.getByLabel('输入需求');await expect(input).toBeEnabled();await input.fill(text);await input.press('Enter');}
async function directory(page:Page){await page.getByRole('button',{name:'添加本地资料',exact:true}).click();await page.getByRole('menuitem',{name:'选择并授权文件夹',exact:true}).click();}
async function snapshot(page:Page){return page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok)throw Error('list');const got=await window.orvia.chatGet({id:list.result.conversations[0].id});if(!got.ok)throw Error(got.message);return got.result;});}
async function done(page:Page){await expect.poll(async()=>(await snapshot(page)).workflow,{timeout:20000}).toBeNull();}
async function browserControl(page:Page,label:string){const select=page.getByLabel('M18浏览器控件'),option=select.locator('option').filter({hasText:label}).first();const value=await option.getAttribute('value');if(!value)throw Error('合成控件缺失');await select.selectOption(value);}

test('M20自然列目录并重命名：原生拒绝不变，批准后真实核验并接续',async()=>{
  const f=await fixture();try{
    await send(f.page,'列出目录，然后重命名 alpha.txt 为 beta.txt');await expect(f.page.getByLabel('当前需求待办')).toContainText('原请求已保留');await directory(f.page);
    const plan=f.page.getByLabel('当前操作计划');await expect(plan).toContainText('alpha.txt');await expect(plan).toContainText('beta.txt');
    const before=await snapshot(f.page);expect(before.workflow?.action).toBe('files');
    await f.app.evaluate(()=>{process.env.ORVIA_M20_BUSINESS_CONFIRM='0';});await plan.getByRole('button',{name:'批准此版本并执行',exact:true}).click();
    expect(await readFile(path.join(f.project,'alpha.txt'),'utf8')).toBe('M20 rename synthetic identity');await expect(stat(path.join(f.project,'beta.txt'))).rejects.toThrow();expect((await snapshot(f.page)).workflow?.continuation_id).toBe(before.workflow?.continuation_id);
    await f.app.evaluate(()=>{process.env.ORVIA_M20_BUSINESS_CONFIRM='1';});await plan.getByRole('button',{name:'批准此版本并执行',exact:true}).click();await done(f.page);
    expect(await readFile(path.join(f.project,'beta.txt'),'utf8')).toBe('M20 rename synthetic identity');await expect(stat(path.join(f.project,'alpha.txt'))).rejects.toThrow();
    const final=await snapshot(f.page);expect(final.operation?.status).toBe('completed');expect(final.messages.some(item=>item.kind==='result'&&item.data?.success===true)).toBe(true);expect(final.messages.filter(item=>item.kind==='natural_request')).toHaveLength(1);
    await f.evidence('rename',{workflow:final.workflow,operation:final.operation?.status,requests:final.messages.filter(item=>item.kind==='natural_request').length});await f.page.screenshot({path:path.join(f.work,'rename.png')});
  }finally{await f.app.close();}
});

test('M20自然React代码草稿：确切上下文、Computer原生确认、逐文件真实批准',async()=>{
  const f=await fixture();try{
    await send(f.page,'生成 React 代码草稿，修改 App.tsx 显示合成文字');await expect(f.page.getByLabel('当前需求待办')).toContainText('授权本次目录');await directory(f.page);
    const workspace=f.page.getByLabel('代码、原型和系统清理');await expect(workspace.getByLabel('代码或原型需求')).toHaveValue(/App.tsx/);
    await workspace.getByLabel('代码上下文路径').fill('App.tsx');await workspace.getByRole('button',{name:'预览拟发送上下文',exact:true}).click();await expect(workspace.getByLabel('拟发送代码上下文')).toContainText('old synthetic');
    await workspace.getByRole('button',{name:'原生确认后生成草稿',exact:true}).click();const draft=workspace.getByLabel('代码草稿差异');await expect(draft).toContainText('M20 new synthetic');
    expect(await readFile(path.join(f.project,'App.tsx'),'utf8')).toContain('old synthetic');await f.app.evaluate(()=>{process.env.ORVIA_M20_BUSINESS_CONFIRM='0';});await draft.getByRole('button',{name:'确认此文件并写入',exact:true}).click();expect(await readFile(path.join(f.project,'App.tsx'),'utf8')).toContain('old synthetic');
    await f.app.evaluate(()=>{process.env.ORVIA_M20_BUSINESS_CONFIRM='1';});await draft.getByRole('button',{name:'确认此文件并写入',exact:true}).click();await expect.poll(()=>readFile(path.join(f.project,'App.tsx'),'utf8')).toContain('M20 new synthetic');await done(f.page);
    await f.evidence('code',{calls:JSON.parse(await readFile(f.counter,'utf8')),fileApproved:true});
  }finally{await f.app.close();}
});

test('M20自然网页原型：真实受限预览与三文件逐项写入',async()=>{
  const f=await fixture();try{
    await send(f.page,'生成两页网页原型，包含详情和姓名表单');await expect(f.page.getByLabel('当前需求待办')).toContainText('授权本次目录');await directory(f.page);
    const workspace=f.page.getByLabel('代码、原型和系统清理');await expect(workspace.getByLabel('拟发送代码上下文')).toBeVisible();await workspace.getByRole('button',{name:'原生确认后生成草稿',exact:true}).click();
    const proto=workspace.getByLabel('原型受限预览');await expect(proto).toContainText('M20合成原型');await proto.getByRole('button',{name:'详情',exact:true}).click();await proto.getByRole('textbox',{name:'姓名',exact:true}).fill('合成用户');await proto.getByRole('button',{name:'提交演示',exact:true}).click();await expect(proto).toContainText('演示已提交');
    const draft=workspace.getByLabel('代码草稿差异');for(const [index,name] of ['index.html','style.css','app.js'].entries()){const file=draft.locator(':scope > details').nth(index);if(index)await file.locator(':scope > summary').click();await file.getByRole('button',{name:'确认此文件并写入',exact:true}).click();await expect.poll(async()=>{try{return(await stat(path.join(f.project,name))).size;}catch{return 0;}}).toBeGreaterThan(0);}
    expect(await readFile(path.join(f.project,'index.html'),'utf8')).toContain('演示数据 · 未连接真实业务');await done(f.page);await f.evidence('prototype',{files:3,modelCalls:JSON.parse(await readFile(f.counter,'utf8')),previewOnly:true});await f.page.screenshot({path:path.join(f.work,'prototype.png')});
  }finally{await f.app.close();}
});

test('M20自然临时文件清理：实际范围、原生拒绝、隔离核验与恢复',async()=>{
  const f=await fixture();try{
    await send(f.page,'清理旧临时文件');const plan=f.page.getByLabel('清理逐项计划');await expect(plan).toContainText('old.tmp');await expect(plan).not.toContainText('fresh.tmp');await expect(plan).not.toContainText('old.txt');
    await f.app.evaluate(()=>{process.env.ORVIA_M20_BUSINESS_CONFIRM='0';});await plan.getByRole('button',{name:'批准选中项的此版本并隔离',exact:true}).click();expect(await readFile(f.old,'utf8')).toContain('synthetic');
    // 原生拒绝消耗旧预览授权；重新读取同一真实计划后才能再次批准，不重新扫描或重放。
    const workspace=f.page.getByLabel('代码、原型和系统清理');await workspace.locator('summary').filter({hasText:'已保存清理计划'}).click();await workspace.getByRole('button',{name:/^查看计划 /}).click();
    await f.app.evaluate(()=>{process.env.ORVIA_M20_BUSINESS_CONFIRM='1';});await plan.getByRole('button',{name:'批准选中项的此版本并隔离',exact:true}).click();await expect(plan).toContainText('moved');await expect(stat(f.old)).rejects.toThrow();await expect(plan).toContainText('实际释放空间 0 B');await done(f.page);
    await plan.getByRole('button',{name:'确认恢复',exact:true}).click();await expect(plan).toContainText('restored');expect(await readFile(f.old,'utf8')).toBe('M20 synthetic temporary file');expect(await readFile(f.fresh,'utf8')).toContain('synthetic');expect(await readFile(f.other,'utf8')).toContain('synthetic');await f.evidence('cleanup',{modelCalls:0,restored:true,unselectedFilesPreserved:true});
  }finally{await f.app.close();}
});

test('M20自然Computer Python草稿及原生单选.py：连续新operation真实LPAC与回传',async()=>{
  test.setTimeout(180000);const f=await fixture();try{
    const workspace=f.page.getByLabel('M18脚本桌面浏览器可控执行');await send(f.page,'生成 Python 脚本并运行，输出合成文件');await expect(workspace.getByLabel('脚本模型发送预览')).toContainText('glm-5.3-flashx');await workspace.getByRole('button',{name:'原生确认后生成Python草稿',exact:true}).click();await expect(workspace.getByLabel('脚本审批预览')).toContainText('M20 synthetic model LPAC');
    await workspace.getByRole('button',{name:'原生确认此脚本步骤',exact:true}).click();await expect(workspace.getByLabel('Python实际运行结果')).toContainText('程序核验完成',{timeout:60000});await done(f.page);
    const first=await snapshot(f.page);const history1=await f.page.evaluate(async id=>{const h=await window.orvia.m18History({id});if(!h.ok)throw Error(h.message);return h.result.operations;},first.id);const op1=history1.find(item=>item.kind==='script'&&item.status==='completed')!;expect(op1).toBeTruthy();
    await workspace.getByRole('button',{name:'原生确认回传此产物',exact:true}).click();await expect.poll(async()=>{try{return await readFile(f.output,'utf8');}catch{return '';}}).toBe('M20 synthetic model LPAC');
    await send(f.page,'运行我选择的 synthetic.py 文件');await expect(workspace.getByLabel('脚本审批预览')).toContainText('M20 synthetic file LPAC');const pending=await snapshot(f.page);expect(pending.workflow?.action).toBe('script');await expect(workspace.getByLabel('Python实际运行结果')).toHaveCount(0);
    await workspace.getByRole('button',{name:'原生确认此脚本步骤',exact:true}).click();await expect(workspace.getByLabel('Python实际运行结果')).toContainText('程序核验完成',{timeout:60000});await done(f.page);
    const history2=await f.page.evaluate(async id=>{const h=await window.orvia.m18History({id});if(!h.ok)throw Error(h.message);return h.result.operations;},first.id);const scripts=history2.filter(item=>item.kind==='script'&&item.status==='completed');expect(scripts).toHaveLength(2);expect(new Set(scripts.map(item=>item.operation_id)).size).toBe(2);
    for(const op of scripts){const fact=await f.page.evaluate(q=>window.orvia.m18ScriptStatus(q),{id:first.id,operation_id:op.operation_id});expect(fact.ok&&fact.result.result?.token_verified).toBe(true);expect(fact.ok&&fact.result.result?.processes_reaped).toBe(true);}
    await f.evidence('script',{operations:scripts.map(item=>({id:item.operation_id,status:item.status})),calls:JSON.parse(await readFile(f.counter,'utf8')),realLPAC:true});await f.page.screenshot({path:path.join(f.work,'script.png')});
  }finally{await f.app.close();}
});

test('M20自然网页写任务：准确站点、填写局部核验不冒充发送、POST另批与真实回执',async()=>{
  test.setTimeout(180000);const f=await fixture();try{
    await send(f.page,'在 https://m20-write.example/ 填写合成正文并发送消息“synthetic M20 message”');const workspace=f.page.getByLabel('M18脚本桌面浏览器可控执行');await expect(workspace.getByLabel('M18浏览器URL')).toHaveValue('https://m20-write.example/');await workspace.getByRole('button',{name:'原生授权并打开专用浏览器',exact:true}).click();const browser=workspace.getByLabel('专用浏览器会话');await expect(browser).toContainText('M20合成写操作',{timeout:30000});
    await browserControl(f.page,'合成正文');await workspace.getByLabel('M18浏览器动作').selectOption('fill');await workspace.getByLabel('M18网页填写值').fill('synthetic M20 message');await workspace.getByLabel('M18浏览器核验文字').fill('M20合成消息完成:唯一回执');await workspace.getByRole('button',{name:'预览网页单步计划',exact:true}).click();await workspace.getByRole('button',{name:'原生确认此浏览器步骤',exact:true}).click();await expect(workspace.getByLabel('浏览器程序核验事实')).toContainText('control_matched');
    expect(await readFile(f.networkCount,'utf8')).toBe('0');expect((await snapshot(f.page)).workflow?.action).toBe('browser');
    await browserControl(f.page,'提交合成消息');await workspace.getByLabel('M18浏览器动作').selectOption('click');await workspace.getByRole('button',{name:'预览网页单步计划',exact:true}).click();await workspace.getByRole('button',{name:'原生确认此浏览器步骤',exact:true}).click();await expect(workspace.getByLabel('浏览器实际外发预览')).toContainText('POST');expect(await readFile(f.networkCount,'utf8')).toBe('0');
    await workspace.getByRole('button',{name:'原生决定此实际外发请求',exact:true}).click();await expect(workspace.getByLabel('浏览器程序核验事实')).toContainText('"matched": true',{timeout:30000});await done(f.page);expect(await readFile(f.networkCount,'utf8')).toBe('1');await workspace.getByRole('button',{name:'关闭专用会话并停止后续请求',exact:true}).click();await f.evidence('browser',{actualPOSTs:1,fillDidNotCompleteRequest:true,network:'MockTransport',chromium:'actual dedicated visible runtime'});
  }catch(error){await writeFile(path.join(f.work,'browser-ui-synthetic.txt'),await f.page.locator('body').innerText(),'utf8');throw error;}finally{await f.app.close();}
});

test('M20自然桌面复合：准确自有窗口、填写再点击、两步真实UIA与原请求完成',async()=>{
  test.setTimeout(180000);const f=await fixture(true);try{
    await send(f.page,'请在桌面应用输入到控件“正文”文本“synthetic M20 desktop”，然后点击应用窗口“M18 apply”');
    await expect(f.page.getByLabel('当前需求待办')).toBeVisible({timeout:20000});const workspace=f.page.getByLabel('M18脚本桌面浏览器可控执行');await expect.poll(async()=>(await snapshot(f.page)).workflow?.action,{timeout:20000}).toBe('desktop');const first=await snapshot(f.page);
    await workspace.getByRole('button',{name:'原生选择并授权桌面应用',exact:true}).click();await expect(workspace.getByLabel('桌面控件观察')).toContainText('Orvia M20 business synthetic',{timeout:20000});await expect(workspace.getByLabel('M18桌面动作')).toHaveValue('set_value');await expect(workspace.getByLabel('M18桌面填写值')).toHaveValue('synthetic M20 desktop');
    await workspace.getByLabel('M18桌面预期结果').fill('控件值等于synthetic M20 desktop');await workspace.getByRole('button',{name:'预览桌面单步计划',exact:true}).click();await workspace.getByRole('button',{name:'原生确认此桌面步骤',exact:true}).click();
    await expect.poll(async()=>{const next=(await snapshot(f.page)).workflow;return next?.action==='desktop'&&next.continuation_id!==first.workflow?.continuation_id;},{timeout:30000}).toBe(true);const second=await snapshot(f.page);expect(second.workflow?.request_id).toBe(first.workflow?.request_id);
    await workspace.getByRole('button',{name:'原生选择并授权桌面应用',exact:true}).click();await expect(workspace.getByLabel('桌面控件观察')).toBeVisible();await expect(workspace.getByLabel('M18桌面动作')).toHaveValue('invoke');
    const option=workspace.getByLabel('M18桌面控件').locator('option').filter({hasText:'M18 apply'}).first(),value=await option.getAttribute('value');if(!value)throw Error('自有唯一按钮缺失');await workspace.getByLabel('M18桌面控件').selectOption(value);await workspace.getByLabel('M18桌面预期结果').fill('APPLIED:synthetic M20 desktop');
    await workspace.getByRole('button',{name:'预览桌面单步计划',exact:true}).click();await workspace.getByRole('button',{name:'原生确认此桌面步骤',exact:true}).click();await done(f.page);await workspace.getByRole('button',{name:'重新观察桌面控件',exact:true}).click();await expect(workspace.getByLabel('桌面控件观察')).toContainText('APPLIED:synthetic M20 desktop');
    const final=await snapshot(f.page),history=await f.page.evaluate(async id=>{const h=await window.orvia.m18History({id});if(!h.ok)throw Error(h.message);return h.result.operations;},final.id);expect(history.filter(item=>item.kind==='desktop'&&item.status==='completed')).toHaveLength(2);expect(final.messages.filter(item=>item.kind==='natural_request')).toHaveLength(1);
    await f.evidence('desktop',{actualUIA:true,completedOperations:2,parentRequest:first.workflow?.request_id,nativeEnumeration:'only newly started synthetic fixture PID'});await f.page.screenshot({path:path.join(f.work,'desktop.png')});
  }catch(error){await writeFile(path.join(f.work,'desktop-ui-synthetic.txt'),await f.page.locator('body').innerText(),'utf8');throw error;}finally{await f.app.close();f.nativeFixture?.kill();}
});
