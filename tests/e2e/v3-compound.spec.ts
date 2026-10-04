import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,writeFile,readFile} from 'node:fs/promises';
import path from 'node:path';

const instruction='扫描 C 盘垃圾文件并找出占用空间较大的可清理项；扫描已安装应用并找出长期未使用或从未使用的闲置应用；分析风险等级并给出清理或保留建议；输出包含清单、空间、风险和建议的 Doc 文档；在对话框给出摘要并指出高价值清理项。';
test('V3-004完整复合请求、授权接续、剩余目标和重启不重放',async()=>{
 const results=path.resolve('artifacts/test-results/V3-004');await mkdir(results,{recursive:true});
 const root=await mkdtemp(path.join(results,'compound-')),directory=path.join(root,'synthetic-files');await mkdir(directory);await writeFile(path.join(directory,'keep.txt'),'synthetic preserve');
 const profile=path.join(root,'profile'),counter=path.join(root,'calls.json');
 const env={...process.env,ORVIA_DEV_DATA_DIR:profile,ORVIA_M20_DIRECTORY:directory,ORVIA_M20_COUNTER:counter};
 for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete env[key];
 const launch=()=>electron.launch({args:[path.resolve('tests/e2e/m20-launch.cjs'),`--user-data-dir=${profile}`],env});
 let app=await launch();
 try{
  let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
  await page.getByLabel('输入需求').fill(instruction);await page.getByLabel('输入需求').press('Enter');
  await expect(page.getByLabel('当前需求待办')).toContainText('选择并授权');
  await expect(page.getByLabel('完整目标进度')).toContainText('未实现已安装应用');
  await page.getByRole('button',{name:'添加本地资料',exact:true}).click();await page.getByRole('menuitem',{name:'选择并授权文件夹'}).click();
  await expect(page.getByLabel('当前需求待办')).toContainText('未实现全盘垃圾识别');
  const progress=page.getByLabel('完整目标进度');await expect(progress).toContainText('已完成：');await expect(progress).toContainText('Doc 文档');
  await expect(page.locator('.topbar')).not.toContainText('已完成');
  await expect(page.getByRole('button',{name:'接受此项未完成或受限范围，继续'})).toBeEnabled();
  await expect(page.getByLabel('简报成品制作')).toHaveCount(0);
  const snapshot=await page.evaluate(async()=>{const l=await window.orvia.chatList();if(!l.ok)throw Error('list');const r=await window.orvia.chatGet({id:l.result.conversations[0].id});if(!r.ok)throw Error('get');return r.result;});
  const goals=snapshot.task_progress!.steps.map(s=>s.title);
  await progress.screenshot({path:path.join(results,'compound-progress.png')});
  await page.reload();await page.locator('.conversation-open').first().click();await expect(page.getByLabel('完整目标进度')).toContainText('Doc 文档');
  await app.close();app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
  await page.locator('.conversation-open').first().click();await expect(page.getByLabel('完整目标进度')).toContainText('没有自动重放');
  await expect(page.locator('.topbar')).toContainText('已中断');await expect(page.getByLabel('当前需求待办')).toHaveCount(0);
  const restored=await page.evaluate(async id=>{const r=await window.orvia.chatGet({id});if(!r.ok)throw Error('get');return r.result;},snapshot.id);
  expect(restored.task_progress!.steps.map(s=>s.title)).toEqual(goals);expect(restored.grant).toBeNull();
  expect(restored.messages.filter(m=>m.kind==='directory_result')).toHaveLength(1);
  expect(await readFile(path.join(directory,'keep.txt'),'utf8')).toBe('synthetic preserve');
  let calls=[];try{calls=JSON.parse(await readFile(counter,'utf8'));}catch{}expect(calls).toHaveLength(0);
 }finally{await app.close();}
});
