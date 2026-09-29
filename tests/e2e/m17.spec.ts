import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,readFile,stat,utimes} from 'node:fs/promises';
import path from 'node:path';

async function launch(cancel=false){
  const results=path.resolve(process.env.ORVIA_TEST_RESULTS??'artifacts/test-results/M17');
  await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'e2e-'));
  const project=path.join(work,'project');await mkdir(project);
  const {writeFile}=await import('node:fs/promises');
  await writeFile(path.join(project,'App.tsx'),'export const App = () => <p>old synthetic</p>;');
  const local=path.join(work,'Local');const temp=path.join(local,'Temp');await mkdir(temp,{recursive:true});
  const old=path.join(temp,'old.tmp');await writeFile(old,'old synthetic temporary file');
  const oldTime=new Date(Date.now()-40*24*3600*1000);await utimes(old,oldTime,oldTime);
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M17_PROJECT:project,ORVIA_M17_LOCAL_BASE:local,ORVIA_M17_CANCEL:cancel?'1':'0'};
  delete (env as NodeJS.ProcessEnv).ELECTRON_RUN_AS_NODE;
  for(const key of ['DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete (env as NodeJS.ProcessEnv)[key];
  const app=await electron.launch({args:[path.resolve('tests/e2e/m17-launch.cjs')],env});
  return {app,project,old,results};
}

async function enter(page:import('@playwright/test').Page){
  await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'＋ 选择目录'}).click();
  const workspace=page.getByLabel('代码、原型和系统清理');
  await expect(workspace).toBeVisible();
  return workspace;
}

test('M17 代码逐项差异审批、原型受限交互与旧临时文件隔离恢复',async()=>{
  const {app,project,old,results}=await launch();
  try{
    const page=await app.firstWindow();const workspace=await enter(page);
    await workspace.locator('summary').filter({hasText:'代码生成与网页原型'}).click();
    await workspace.getByLabel('代码或原型需求').fill('修改合成 React 组件');
    await workspace.getByLabel('代码上下文路径').fill('App.tsx');
    await workspace.getByRole('button',{name:'预览拟发送上下文'}).click();
    await expect(workspace.getByLabel('拟发送代码上下文')).toContainText('old synthetic');
    const bypass=await page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok)throw new Error('list');return window.orvia.developmentApply({id:list.result.conversations[0].id,draft_id:crypto.randomUUID(),revision:'a'.repeat(64),index:0});});
    expect(bypass.ok).toBe(false);
    await workspace.getByRole('button',{name:'原生确认后生成草稿'}).click();
    const draft=workspace.getByLabel('代码草稿差异');await expect(draft).toContainText('修改 App.tsx');
    expect(await readFile(path.join(project,'App.tsx'),'utf8')).toContain('old synthetic');
    await draft.getByRole('button',{name:'确认此文件并写入'}).click();
    await expect.poll(()=>readFile(path.join(project,'App.tsx'),'utf8')).toContain('new synthetic');
    await workspace.getByLabel('交付类型').selectOption('prototype');
    await workspace.getByLabel('代码或原型需求').fill('做两页合成交互原型');
    await workspace.getByLabel('代码上下文路径').fill('');
    await workspace.getByRole('button',{name:'预览拟发送上下文'}).click();
    await workspace.getByRole('button',{name:'原生确认后生成草稿'}).click();
    const proto=workspace.getByLabel('原型受限预览');await expect(proto).toContainText('首页');
    await proto.getByRole('button',{name:'详情'}).click();await expect(proto).toContainText('详情页');
    await proto.getByRole('button',{name:'提交演示'}).click();
    await expect(proto.getByRole('status')).toBeEmpty();
    await proto.getByRole('textbox',{name:'姓名'}).fill('合成用户');
    await proto.getByRole('button',{name:'提交演示'}).click();await expect(proto).toContainText('演示已提交');
    await page.setViewportSize({width:800,height:600});
    await expect(proto.getByRole('button',{name:'提交演示'})).toBeVisible();
    await page.screenshot({path:path.join(results,'m17-prototype-800x600.png')});
    for(const [i,name] of ['index.html','style.css','app.js'].entries()){
      const row=workspace.getByLabel('代码草稿差异').locator(':scope > details').nth(i);
      if(i>0)await row.locator(':scope > summary').click();
      await row.getByRole('button',{name:'确认此文件并写入'}).click();
      await expect.poll(async()=>{try{return await readFile(path.join(project,name),'utf8');}catch{return '';}}).not.toBe('');
    }
    expect((await readFile(path.join(project,'index.html'),'utf8'))).toContain('演示数据 · 未连接真实业务');
    await workspace.locator('summary').filter({hasText:'系统清理：旧临时文件隔离'}).click();
    await workspace.getByRole('button',{name:'扫描白名单'}).click();
    const plan=workspace.getByLabel('清理逐项计划');await expect(plan).toContainText('old.tmp');
    await plan.getByRole('button',{name:'批准选中项的此版本并隔离'}).click();
    await expect(plan).toContainText('moved');
    await expect(plan).toContainText('实际释放空间 0 B');
    await expect(stat(old)).rejects.toThrow();
    await plan.getByRole('button',{name:'确认恢复'}).click();
    await expect(plan).toContainText('restored');
    expect((await readFile(old,'utf8'))).toBe('old synthetic temporary file');
    await page.screenshot({path:path.join(results,'m17-workspace.png')});
  }finally{await app.close();}
});

test('M17 原生确认取消不隔离临时文件',async()=>{
  const {app,old}=await launch(true);
  try{
    const page=await app.firstWindow();const workspace=await enter(page);
    await workspace.locator('summary').filter({hasText:'系统清理：旧临时文件隔离'}).click();
    await workspace.getByRole('button',{name:'扫描白名单'}).click();
    await workspace.getByRole('button',{name:'批准选中项的此版本并隔离'}).click();
    expect((await readFile(old,'utf8'))).toContain('old synthetic');
  }finally{await app.close();}
});
