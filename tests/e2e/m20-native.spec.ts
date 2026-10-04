/** 真Windows文件/目录选择及原生取消；仅默认目录被固定在M20合成树，结果没有替换。 */
import {_electron as electron,expect,test,type Page} from '@playwright/test';
import {mkdir,mkdtemp,writeFile} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
import {documentFixtures} from '../integration/m13-fixtures';
import type {} from '../../apps/desktop/src/shared/api';

const run=promisify(execFile);
test('M20真实原生＋目录与文件选择、原生Main审批取消不发送',async()=>{
  test.setTimeout(180000);
  const results=path.resolve('artifacts/test-results/M20');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'native-')),directory=path.join(work,'synthetic-files'),profile=path.join(work,'profile');await mkdir(directory);await mkdir(profile);
  await writeFile(path.join(directory,'only.txt'),'M20 synthetic directory');documentFixtures(work);
  const env:Record<string,string>={...Object.fromEntries(Object.entries(process.env).filter((pair):pair is [string,string]=>typeof pair[1]==='string')),ORVIA_DEV_DATA_DIR:profile};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete env[key];
  const app=await electron.launch({args:[path.resolve('tests/e2e/m20-runtime-parity-launch.cjs'),`--user-data-dir=${profile}`],env});
  let ownerProcess:number;
  const native=async(action:'File'|'Folder'|'Cancel',title:string,synthetic?:string)=>{
    const name=action==='Cancel'?'main-cancel':action.toLowerCase();
    const {stdout}=await run(path.join(process.env.SystemRoot!,'System32/WindowsPowerShell/v1.0/powershell.exe'),['-NoProfile','-NonInteractive','-File',path.resolve('tests/e2e/m20-native-dialog.ps1'),'-OwnerProcess',String(ownerProcess),'-ProfileDirectory',profile,'-DialogTitle',title,'-Action',action,...(synthetic?['-SyntheticPath',synthetic]:[]),'-CapturePath',path.join(work,name+'.png')],{windowsHide:true,timeout:35000,maxBuffer:16000});
    const fact=JSON.parse(stdout.trim());expect(fact.ownerMatched).toBe(true);expect(fact.nativeAPI).toBe(true);await writeFile(path.join(work,name+'.json'),JSON.stringify(fact,null,2));return fact;
  };
  try{
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible({timeout:30000});
    const identity=await app.evaluate(()=>({pid:process.pid,executable:process.execPath}));ownerProcess=identity.pid;expect(path.resolve(identity.executable).toLowerCase()).toBe(path.resolve('node_modules/electron/dist/electron.exe').toLowerCase());await writeFile(path.join(work,'owner-identity.json'),JSON.stringify({...identity,launcherProcess:app.process().pid},null,2));
    await app.evaluate(({dialog},{work,backendPath})=>{
      // 主进程测试探针只设置合成起始目录，调用真实API并保留所有props及返回值。
      const original=dialog.showOpenDialog.bind(dialog);dialog.showOpenDialog=((owner,options)=>original(owner,{...options,defaultPath:work})) as typeof dialog.showOpenDialog;
      const load=process.getBuiltinModule('node:module')!.createRequire(backendPath),backend=load(backendPath),old=backend.BackendClient.prototype.chat;
      (globalThis as any).__m20Native={generateRequests:0};
      backend.BackendClient.prototype.chat=function(method:string,...args:unknown[]){if(method==='chat.synthesis.generate')(globalThis as any).__m20Native.generateRequests++;return old.call(this,method,...args);};
    },{work,backendPath:path.resolve('apps/desktop/dist/main/backend.js')});
    await send(page,'看看目录里有哪些文件');await expect(page.getByLabel('当前需求待办')).toBeVisible();
    await page.getByRole('button',{name:'添加本地资料',exact:true}).click();const folder=page.getByRole('menuitem',{name:'选择并授权文件夹',exact:true}).click();
    await native('Folder','授权此对话访问一个本地目录',directory);await folder;
    await expect(page.getByLabel('目录直接回答').last()).toContainText('only.txt');const listed=await snapshot(page);expect(listed.workflow).toBeNull();expect(listed.messages.filter(message=>message.kind==='natural_request')).toHaveLength(1);
    await send(page,'总结这份文档');await expect(page.getByLabel('当前需求待办')).toBeVisible();await page.getByRole('button',{name:'添加本地资料',exact:true}).click();
    const attachment=page.getByRole('menuitem',{name:'添加文件（最多3个）',exact:true}).click();await native('File','添加本地资料（最多3个，每个10 MiB；不上传云端）',path.join(work,'synthetic.docx'));await attachment;
    const preview=page.getByLabel('模型发送范围预览');await expect(preview).toContainText('deepseek-flash');const pending=await snapshot(page);
    const approval=preview.getByRole('button',{name:'确认发送并生成回答',exact:true}).click();await native('Cancel','确认发送文件内容');await approval;
    await expect(page.getByText('已取消正文发送；未调用模型。',{exact:true})).toBeVisible();
    const after=await snapshot(page);expect(after.workflow?.continuation_id).toBe(pending.workflow?.continuation_id);expect(after.messages.some(message=>message.kind==='synthesis')).toBe(false);
    expect(await app.evaluate(()=>(globalThis as any).__m20Native.generateRequests)).toBe(0);
    await writeFile(path.join(work,'native-evidence.json'),JSON.stringify({module:'M20',actual:['Electron dialog.showOpenDialog/showMessageBox','Windows owned-HWND UIA SelectionItemPattern/IsSelected; guarded fixed Win32 BM_CLICK for observed Button whose UIA provider exposes Pane without InvokePattern','product Python/stdio/SQLite/local parsing'],testProbe:'defaultPath only, fixed generate-method call counter',credentials:'empty; no cloud calls',physicalIME:'separate m20-ime.spec.ts; not proved by native dialog test',screenshots:'only owned dialog PrintWindow; captured flag records success',parentRequests:2,approvalCancelled:true},null,2));
    await page.screenshot({path:path.join(work,'native-product.png')});
  }finally{await app.close();}
});
async function send(page:Page,text:string){await page.getByLabel('输入需求').fill(text);await expect(page.getByRole('button',{name:'发送',exact:true})).toBeEnabled();await page.getByLabel('输入需求').press('Enter');}
async function snapshot(page:Page){return page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok||!list.result.conversations.length)throw Error('native conversation missing');const reply=await window.orvia.chatGet({id:list.result.conversations[0].id});if(!reply.ok)throw Error(reply.message);return reply.result;});}
