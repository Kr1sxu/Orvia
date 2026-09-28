import {_electron as electron,expect,test,type ElectronApplication,type Page} from '@playwright/test';
import path from 'node:path';
import {mkdir,mkdtemp,writeFile,readFile} from 'node:fs/promises';
import {spawn} from 'node:child_process';

async function fixture() {
 const results=path.resolve('artifacts/test-results/M11');await mkdir(results,{recursive:true});
 const profile=await mkdtemp(path.join(results,'profile-'));
 const root=await mkdtemp(path.join(results,'files-'));await writeFile(path.join(root,'sample.txt'),'synthetic');
 const env={...process.env,ORVIA_DEV_DATA_DIR:profile};delete env.ELECTRON_RUN_AS_NODE;
 for(const key of ['DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete env[key];
 const launch=()=>electron.launch({args:[path.resolve('tests/e2e/m11-launch.cjs')],env});
 return {results,root,launch};
}
async function authorize(app:ElectronApplication,page:Page,root:string) {
 await app.evaluate(({dialog},directory)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[directory]});},root);
 await page.getByRole('button',{name:'＋ 选择目录',exact:true}).click();
 await expect(page.locator('.result-card').last()).toContainText('sample.txt');
}
async function idle(page:Page) {
 await expect.poll(()=>page.evaluate(async()=>{const s=await window.orvia.connectionStatus();return s.ok&&!s.result.busy;})).toBe(true);
}
async function current(page:Page) {
 return page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok)throw Error('list unavailable');const chat=await window.orvia.chatGet({id:list.result.conversations[0].id});if(!chat.ok)throw Error('snapshot unavailable');return chat.result;});
}

test('M11 取消规划、重载保持任务、崩溃重连与显式重新授权（模型mock）',async()=>{
 const {results,root,launch}=await fixture();const app=await launch();
 try {
  const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
  // 相同应用第二次启动应退出并激活已有窗口，不生成第二个数据库使用者。
  const secondaryEnv={...process.env};delete secondaryEnv.ELECTRON_RUN_AS_NODE;
  const secondary=spawn(app.process().spawnfile,[path.resolve('tests/e2e/m11-launch.cjs')],{
   env:secondaryEnv,windowsHide:true,stdio:'ignore',
  });
  const secondaryCode=await new Promise<number|null>((resolve,reject)=>{
   const timer=setTimeout(()=>{secondary.kill();reject(Error('second instance did not exit'));},8000);
   secondary.once('error',error=>{clearTimeout(timer);reject(error);});
   secondary.once('close',code=>{clearTimeout(timer);resolve(code);});
  });
  expect(secondaryCode).toBe(0);
  await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
  await authorize(app,page,root);
  await page.getByLabel('输入需求').fill('慢速合成查询');await page.getByLabel('输入需求').press('Enter');
  await expect(page.getByRole('button',{name:'取消规划',exact:true})).toBeVisible();
  const inFlight=await page.evaluate(async()=>{const s=await window.orvia.connectionStatus();if(!s.ok||!s.result.activeSend)throw Error('active');return s.result.activeSend;});
  expect((await page.evaluate(()=>window.orvia.reconnect())).ok).toBe(false);
  expect(await page.evaluate(x=>window.orvia.chatCancel({...x,request_id:'11111111-1111-4111-8111-111111111111'}),inFlight)).toEqual({ok:true,result:{cancelled:false}});
  await page.reload();
  await expect(page.getByRole('button',{name:'取消规划',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'发送',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'取消规划',exact:true}).click();await idle(page);
  const cancelled=await current(page);expect(cancelled.status).toBe('cancelled');
  expect(cancelled.messages.filter(m=>m.role==='user')).toHaveLength(1);
  expect(cancelled.operation).toBeNull();expect(await readFile(path.join(root,'sample.txt'),'utf8')).toBe('synthetic');
  const retried=await page.evaluate(x=>window.orvia.chatSend({...x,text:'慢速合成查询'}),inFlight);
  expect(retried.ok).toBe(true);expect((await current(page)).messages.filter(m=>m.role==='user')).toHaveLength(1);
  await expect(page.getByLabel('输入需求')).toBeEnabled();await page.getByLabel('输入需求').fill('慢速中断查询');await page.getByLabel('输入需求').press('Enter');
  await expect(page.getByRole('button',{name:'取消规划',exact:true})).toBeVisible();
  await app.evaluate(()=>{(globalThis as any).__m11OwnedBackend.kill();});
  await expect(page.getByRole('button',{name:'重新连接',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'重新连接',exact:true}).click();
  await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();await idle(page);
  const interrupted=await current(page);expect(interrupted.status).toBe('interrupted');expect(interrupted.grant).toBeNull();
  expect(interrupted.messages.filter(m=>m.role==='user')).toHaveLength(2);
  await expect(page.getByText('当前未授权目录；历史记录不会恢复目录权限。')).toBeVisible();
  await page.screenshot({path:path.join(results,'reconnected.png')});
  await authorize(app,page,root);
  await page.getByLabel('输入需求').fill('把 sample.txt 重命名为 renamed.txt');await page.getByLabel('输入需求').press('Enter');
  await expect(page.getByRole('button',{name:'批准此版本并执行'})).toBeVisible();
  await page.getByRole('button',{name:'批准此版本并执行'}).click();
  await expect(page.getByRole('button',{name:'撤销最近一次变更'})).toBeVisible();
  await expect(page.getByRole('navigation',{name:'历史会话'}).getByRole('button',{name:'本地文件整理',exact:true})).toContainText('已完成');
  const completed=await current(page);expect(completed.operations?.[0].can_undo).toBe(true);
  expect(await readFile(path.join(root,'renamed.txt'),'utf8')).toBe('synthetic');
  await page.setViewportSize({width:760,height:560});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:path.join(results,'narrow-completed.png')});
 } finally {await app.close();}
});

test('M11 窗口关闭终止自有后端，重启保留中断事实且不重放',async()=>{
 const {root,launch}=await fixture();let app=await launch();
 try {
  let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
  await authorize(app,page,root);
  await page.getByLabel('输入需求').fill('慢速关闭查询');await page.getByLabel('输入需求').press('Enter');
  await expect(page.getByRole('button',{name:'取消规划',exact:true})).toBeVisible();
  const pid=await app.evaluate(()=>(globalThis as any).__m11OwnedBackend.pid as number);
  await app.close();
  await expect.poll(()=>{try {process.kill(pid,0);return false;}catch{return true;}}).toBe(true);
  app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
  await page.getByRole('navigation',{name:'历史会话'}).getByRole('button',{name:'本地文件整理',exact:true}).click();
  const snapshot=await current(page);expect(snapshot.grant).toBeNull();expect(snapshot.status).toBe('interrupted');
  expect(snapshot.messages.filter(m=>m.role==='user')).toHaveLength(1);
  expect(snapshot.operation).toBeNull();expect(await readFile(path.join(root,'sample.txt'),'utf8')).toBe('synthetic');
 } finally {await app.close();}
});
