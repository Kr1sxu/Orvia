import {_electron as electron,expect,test,type Page} from '@playwright/test';
import {mkdir,mkdtemp,writeFile,readFile,utimes} from 'node:fs/promises';
import path from 'node:path';
import type {} from '../../apps/desktop/src/shared/api';

async function fixture(){
  const work=await mkdtemp(path.resolve('artifacts/test-results/V3-001/electron-'));
  const project=path.join(work,'project'),local=path.join(work,'Local');
  await mkdir(project);await mkdir(path.join(local,'Temp'),{recursive:true});
  const old=path.join(local,'Temp','synthetic.log');await writeFile(old,'synthetic only');
  const date=new Date(Date.now()-40*86400000);await utimes(old,date,date);
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M20_COUNTER:path.join(work,'calls.json'),ORVIA_M20_BUSINESS_PROJECT:project,ORVIA_M20_BUSINESS_LOCAL:local,ORVIA_M20_BUSINESS_DIALOGS:path.join(work,'dialogs.jsonl')};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete (env as NodeJS.ProcessEnv)[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/m20-business-launch.cjs'),`--user-data-dir=${env.ORVIA_DEV_DATA_DIR}`],env});
  return {work,launch};
}
async function ready(page:Page){await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible({timeout:30000});}
async function send(page:Page,text:string){await page.getByLabel('输入需求').fill(text);await expect(page.getByRole('button',{name:'发送',exact:true})).toBeEnabled();await page.getByLabel('输入需求').press('Enter');}
async function snapshot(page:Page){return page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok)throw Error('list');const got=await window.orvia.chatGet({id:list.result.conversations[0].id});if(!got.ok)throw Error(got.message);return got.result;});}
async function hidden(page:Page){for(const selector of ['.m17-workspace','.m18-workspace'])await expect(page.locator(selector)).toHaveCount(0);}

test('V3普通寒暄无能力IPC或模型；只按当前需求显示并隔离会话',async()=>{
  const f=await fixture();const app=await f.launch();
  try{const page=await app.firstWindow();await ready(page);
    await app.evaluate(({ipcMain})=>{(globalThis as any).v3Calls=[];for(const [name,handler] of (ipcMain as any)._invokeHandlers){if(/orvia:(m18-|development-|cleanup-)/.test(name))(ipcMain as any)._invokeHandlers.set(name,async(...args:unknown[])=>{(globalThis as any).v3Calls.push(name);return handler(...args);});}});
    await hidden(page);
    for(const text of ['你好','谢谢','好的','继续']){await send(page,text);await expect.poll(async()=>(await snapshot(page)).messages.at(-1)?.data?.origin).toBe('local');await hidden(page);}
    expect(await app.evaluate(()=>(globalThis as any).v3Calls)).toEqual([]);
    await expect(readFile(path.join(f.work,'calls.json'),'utf8')).rejects.toThrow();
    await page.screenshot({path:path.join(f.work,'greeting.png')});
    for(const [text,action,label] of [
      ['生成 React 页面','development','代码生成与网页原型'],
      ['清理旧临时文件','cleanup','系统清理：旧临时文件隔离'],
      ['运行 Python 脚本\n```python\nprint("synthetic")\n```','script','任意脚本：Python隔离执行'],
      ['聚焦桌面应用','desktop','桌面点击：准确应用与控件'],
      ['在 https://synthetic.example/ 填写表单','browser','浏览器写操作：专用会话与实际外发'],
    ]){
      await page.getByRole('button',{name:'新建对话',exact:true}).click();await send(page,text);
      if(action==='development'){await page.getByRole('button',{name:'添加本地资料',exact:true}).click();await page.getByRole('menuitem',{name:'选择并授权文件夹',exact:true}).click();}
      await expect.poll(async()=>(await snapshot(page)).workflow?.action).toBe(action);
      await expect(page.getByText(label,{exact:true})).toBeVisible();
      const expected=action==='development'||action==='cleanup'?1:2;
      expect(await page.locator('.m17-workspace > details > summary, .m18-workspace > details > summary').count()).toBe(expected);
      await page.getByRole('button',{name:'新建对话',exact:true}).click();await hidden(page);
    }
    await page.screenshot({path:path.join(f.work,'new-chat.png')});
  }finally{await app.close();}
});

test('V3脚本待审批账本重启保留，历史打开不执行或恢复权限',async()=>{
  const f=await fixture();let app=await f.launch();
  try{let page=await app.firstWindow();await ready(page);
    await send(page,'运行 Python 脚本\n```python\nprint("synthetic")\n```');
    await expect(page.getByLabel('脚本审批预览')).toBeVisible();
    const state=await snapshot(page);expect(state.workspace_history?.automation).toEqual(['script']);
    await app.close();app=await f.launch();page=await app.firstWindow();await ready(page);
    await page.getByRole('navigation',{name:'历史会话'}).getByRole('button').filter({hasText:'运行 Python'}).first().click();
    const workspace=page.getByLabel('M18脚本桌面浏览器可控执行');await expect(workspace).toBeVisible();
    await workspace.locator(':scope > summary').click();
    await workspace.getByText('执行账本与取消',{exact:true}).click();
    await expect(workspace.getByLabel('M18执行记录')).toContainText('等待步骤审批');
    expect((await snapshot(page)).grant).toBeNull();
    await expect(page.getByLabel('脚本审批预览')).toHaveCount(0);
    await expect(readFile(path.join(f.work,'calls.json'),'utf8')).rejects.toThrow();
    await page.screenshot({path:path.join(f.work,'restored-script.png')});
  }finally{await app.close();}
});
