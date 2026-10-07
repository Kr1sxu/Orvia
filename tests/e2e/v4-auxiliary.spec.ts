import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,readFile} from 'node:fs/promises';
import path from 'node:path';

test('V4-001 真实Redis设置、关闭/断连/恢复与寒暄零模型',async()=>{
  test.skip(process.env.ORVIA_REDIS_TEST_PORT===undefined,'真实 Redis 验收需显式测试端口');
  const root=path.resolve('artifacts/test-results/V4-001');await mkdir(root,{recursive:true});
  const work=await mkdtemp(path.join(root,'electron-')),counter=path.join(work,'calls.json');
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M20_COUNTER:counter};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','REDIS_PASSWORD'])delete env[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/m20-launch.cjs')],env});
  let app=await launch();
  try{
    let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'设置',exact:true}).click();
    let panel=page.getByLabel('Redis 辅助服务',{exact:true});await expect(panel).toContainText('未启用；使用 SQLite 本地模式。');
    await panel.getByLabel('Redis 端口',{exact:true}).fill(process.env.ORVIA_REDIS_TEST_PORT!);
    await panel.getByRole('button',{name:'保存并启用连接'}).click();await expect(panel).toContainText('已连接 Redis；SQLite 保留事实。');
    await panel.getByText('辅助服务详情',{exact:true}).click();await page.screenshot({path:path.join(work,'connected.png')});
    // 错误端口是真实TCP失败；不伪称关闭真实服务。通过正确端口重新配置恢复。
    await panel.getByLabel('Redis 端口',{exact:true}).fill('1');await panel.getByRole('button',{name:'保存并启用连接'}).click();
    await expect(panel).toContainText('Redis 已降级；使用 SQLite 本地通知。');
    await page.getByRole('button',{name:'关闭设置'}).click();
    await page.getByLabel('输入需求').fill('你好');await page.getByLabel('输入需求').press('Enter');
    await expect(page.getByLabel('输入需求')).toBeEnabled();
    await page.getByRole('button',{name:'设置',exact:true}).click();panel=page.getByLabel('Redis 辅助服务',{exact:true});
    await expect(panel).toContainText('Redis 已降级');
    await panel.getByText('辅助服务详情',{exact:true}).click();
    await expect(panel).toContainText('已结束（具体结果见会话）',{timeout:15000});
    await panel.getByText('最近核对的任务状态',{exact:true}).scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(work,'local-projection.png')});
    await panel.getByLabel('Redis 端口',{exact:true}).fill(process.env.ORVIA_REDIS_TEST_PORT!);
    await panel.getByRole('button',{name:'保存并启用连接'}).click();await expect(panel).toContainText('已连接 Redis');
    await panel.getByRole('button',{name:'检测并恢复连接'}).click();await expect(panel).toContainText('已连接 Redis');
    await app.close();app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'设置',exact:true}).click();panel=page.getByLabel('Redis 辅助服务',{exact:true});await expect(panel).toContainText('已连接 Redis');
    await panel.getByRole('button',{name:'关闭辅助连接'}).click();await expect(panel).toContainText('未启用；使用 SQLite 本地模式。');
    await page.screenshot({path:path.join(work,'disabled.png')});
    let calls=[];try{calls=JSON.parse(await readFile(counter,'utf8'));}catch{}
    expect(calls).toEqual([]);
  }finally{await app.close();}
});
