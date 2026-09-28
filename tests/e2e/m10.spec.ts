import {_electron as electron,expect,test, type ElectronApplication} from '@playwright/test';
import path from 'node:path';
import {mkdir,mkdtemp,writeFile,readFile,stat} from 'node:fs/promises';

async function mockDialog(app: ElectronApplication, directory: string | null) {
  await app.evaluate(({dialog},dir)=>{dialog.showOpenDialog=async()=>({canceled:dir===null,filePaths:dir?[dir]:[]});},directory);
}

test('M10 对话→授权→观察→版本审批→核验→重启重新授权→撤销（模型mock）',async()=>{
  const results=path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M10');await mkdir(results,{recursive:true});
  const profile=await mkdtemp(path.join(results,'profile-'));
  const root=await mkdtemp(path.join(results,'files-'));
  await writeFile(path.join(root,'合成说明.txt'),'synthetic-only');
  await writeFile(path.join(root,'large.bin'),Buffer.alloc(2*1024*1024));
  const env={...process.env,ORVIA_DEV_DATA_DIR:profile};delete env.ELECTRON_RUN_AS_NODE;
  for(const key of ['DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','ORVIA_TEST_DIRECTORY'])delete env[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/m10-launch.cjs')],env});
  let app=await launch();
  try {
    let page=await app.firstWindow();
    await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.screenshot({path:path.join(results,'welcome.png')});
    expect(await page.evaluate(()=>({node:typeof (window as any).require,ipc:typeof (window.orvia as any).invoke,grant:typeof (window.orvia as any).chatGrant}))).toEqual({node:'undefined',ipc:'undefined',grant:'undefined'});
    await mockDialog(app,root);
    await page.getByRole('button',{name:'＋ 选择目录',exact:true}).click();
    await expect(page.getByText('合成说明.txt',{exact:true})).toBeVisible();
    await page.getByLabel('文件名搜索').fill('合成说明');await page.getByRole('button',{name:'搜索',exact:true}).click();
    await expect(page.locator('.result-card').last()).toContainText('合成说明.txt');
    await page.locator('.result-card').last().getByRole('button',{name:'属性'}).click();
    await expect(page.locator('.result-card').last()).toContainText('修改时间');
    await page.getByRole('button',{name:'空间与大文件'}).click();
    await expect(page.locator('.result-card').last()).toContainText('2.0 MB');
    await page.getByLabel('输入需求').fill('请把合成说明.txt重命名为已整理.txt');await page.getByRole('button',{name:'发送',exact:true}).click();
    await expect(page.getByRole('button',{name:'批准此版本并执行'})).toBeVisible();
    expect(await readFile(path.join(root,'合成说明.txt'),'utf8')).toBe('synthetic-only');
    const snapshot=await page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok)throw Error('list');const reply=await window.orvia.chatGet({id:list.result.conversations[0].id});if(!reply.ok)throw Error('get');return reply.result;});
    const approval={id:snapshot.id,operation_id:snapshot.operation!.operation_id,revision:snapshot.operation!.revision};
    const denied=await page.evaluate(async input=>({old:await window.orvia.chatApprove({...input,revision:'0'.repeat(64)}),path:await window.orvia.chatInspect({id:input.id,tool:'get_file_metadata',arguments:{path:'../outside'}})}),approval);
    expect(denied.old.ok).toBe(false);expect(denied.path.ok).toBe(false);
    await page.getByLabel('输入需求').fill('同意');await page.getByRole('button',{name:'发送',exact:true}).click();
    await expect(page.getByText(/这是合成模型建议/)).toBeVisible();
    expect(await stat(path.join(root,'合成说明.txt'))).toBeTruthy();
    await page.screenshot({path:path.join(results,'plan.png')});
    await page.getByRole('button',{name:'批准此版本并执行'}).click();
    await expect(page.getByRole('button',{name:'撤销最近一次变更'})).toBeVisible();
    expect(await readFile(path.join(root,'已整理.txt'),'utf8')).toBe('synthetic-only');
    await expect(page.getByLabel('当前操作计划')).toContainText('已完成');
    await page.getByRole('button',{name:'＋ 新建对话',exact:true}).click();
    await page.getByLabel('输入需求').fill('另一会话');await page.getByRole('button',{name:'发送',exact:true}).click();
    await expect(page.getByText('请先通过“选择目录”授权本次任务范围，然后发送需要处理的需求。')).toBeVisible();
    const cross=await page.evaluate(async input=>{const list=await window.orvia.chatList();if(!list.ok)throw Error('list');return window.orvia.chatUndo({...input,id:list.result.conversations[0].id});},approval);
    expect(cross.ok).toBe(false);
    await app.close();app=await launch();page=await app.firstWindow();
    await page.getByRole('navigation',{name:'历史会话'}).getByRole('button',{name:'本地文件整理',exact:true}).click();
    await expect(page.getByText('当前未授权目录；历史记录不会恢复目录权限。')).toBeVisible();
    await expect(page.getByRole('button',{name:'撤销最近一次变更'})).toBeDisabled();
    expect((await page.evaluate(input=>window.orvia.chatUndo(input),approval)).ok).toBe(false);
    await mockDialog(app,null);await page.getByRole('button',{name:'＋ 选择目录',exact:true}).click();
    await expect(page.getByRole('alert')).toContainText('已取消选择');
    await mockDialog(app,root);await page.getByRole('button',{name:'＋ 选择目录',exact:true}).click();
    await expect(page.getByRole('button',{name:'撤销最近一次变更'})).toBeEnabled();
    await page.getByRole('button',{name:'撤销最近一次变更'}).click();
    await expect(page.getByLabel('当前操作计划')).toContainText('已撤销');
    expect(await readFile(path.join(root,'合成说明.txt'),'utf8')).toBe('synthetic-only');
    await page.screenshot({path:path.join(results,'completed.png')});
    await page.setViewportSize({width:800,height:650});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:path.join(results,'narrow.png')});
    await page.getByRole('button',{name:'⚙ 设置'}).click();await expect(page.getByRole('dialog',{name:'设置'})).toBeVisible();
    await expect(page.getByText('deepseek-flash',{exact:true})).toBeVisible();
    for(const label of ['自动任务','技能广场','管家团队'])await expect(page.getByText(label,{exact:true})).toHaveCount(0);
  } finally {await app.close();}
});

test('M10 空目录、模型失败、部分结果与键盘输入（mock，无真实供应商）',async()=>{
  const results=path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M10');await mkdir(results,{recursive:true});
  const profile=await mkdtemp(path.join(results,'states-profile-'));
  const root=await mkdtemp(path.join(results,'empty-'));
  const env={...process.env,ORVIA_DEV_DATA_DIR:profile};delete env.ELECTRON_RUN_AS_NODE;
  const app=await electron.launch({args:[path.resolve('tests/e2e/m10-launch.cjs')],env});
  try {
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await mockDialog(app,root);await page.getByRole('button',{name:'＋ 选择目录',exact:true}).click();
    await expect(page.getByText('没有匹配项目。')).toBeVisible();
    await page.getByLabel('输入需求').fill('合成模型失败');await page.getByLabel('输入需求').press('Enter');
    await expect(page.getByText('固定 Main 模型暂不可用；未切换模型，请稍后重新发送。')).toBeVisible();
    await expect(page.getByLabel('当前操作计划')).toHaveCount(0);
    await Promise.all(Array.from({length:110},(_,i)=>writeFile(path.join(root,'合成长文件名-'+i+'.txt'),'synthetic')));
    await page.getByRole('button',{name:'目录列表',exact:true}).click();
    await expect(page.locator('.result-card').last()).toContainText('部分结果');
    await page.getByLabel('输入需求').fill('第一行');await page.getByLabel('输入需求').press('Shift+Enter');
    await expect(page.getByLabel('输入需求')).toHaveValue('第一行\n');
    await page.screenshot({path:path.join(results,'partial-and-failure.png')});
  }finally{await app.close();}
});
