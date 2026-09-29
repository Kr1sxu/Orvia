import {_electron as electron,expect,test,type Page} from '@playwright/test';
import {mkdir,mkdtemp} from 'node:fs/promises';
import path from 'node:path';

async function fixture(missing=false){
  const results=path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M12');await mkdir(results,{recursive:true});
  const profile=await mkdtemp(path.join(results,'e2e-profile-'));
  const env={...process.env,ORVIA_DEV_DATA_DIR:profile,ORVIA_M12_NO_SEARCH:missing?'1':'0'};
  delete (env as NodeJS.ProcessEnv).ELECTRON_RUN_AS_NODE;
  for(const key of ['DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete (env as NodeJS.ProcessEnv)[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/m12-launch.cjs')],env});
  return {results,launch};
}
async function send(page:Page,intent:string,text:string){
  await expect(page.getByRole('button',{name:'发送',exact:true})).toBeDisabled();
  await page.getByLabel('需求类型').selectOption(intent);
  await page.getByLabel('输入需求').fill(text);
  await page.getByLabel('输入需求').press('Enter');
  await expect(page.getByLabel('输入需求')).toHaveValue('');
  await expect(page.getByLabel('需求类型')).toBeEnabled();
}
test('M12 搜索、引用、显式读取、已有来源追问、重启和窄窗口（网络mock）',async()=>{
  const {results,launch}=await fixture();let app=await launch();
  try{
    let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await send(page,'search','合成许可');
    const card=page.locator('.source-card').last();
    await card.locator('summary').click();
    await expect(card).toContainText('搜索摘要（未读取原网页）');
    await card.getByRole('button',{name:'查看证据',exact:true}).click();
    await expect(page.getByLabel('证据详情')).toContainText('合成来源摘要');
    await page.getByRole('button',{name:'关闭证据',exact:true}).click();
    await page.getByLabel('输入需求').fill('尚未发送的合成草稿');
    await card.getByRole('button',{name:'读取此网页',exact:true}).click();
    await expect(page.locator('.source-card')).toHaveCount(2);
    await expect(page.getByLabel('需求类型')).toBeEnabled();
    await expect(page.getByLabel('输入需求')).toHaveValue('尚未发送的合成草稿');
    await page.getByLabel('输入需求').fill('');
    await page.locator('.source-card').last().locator('summary').click();
    await expect(page.locator('.source-card').last()).toContainText('HTTP 网页正文');
    await send(page,'ask','许可');
    await expect(page.locator('.source-card').last().locator('details')).toHaveCount(2);
    await expect(page.getByText('以下是当前会话来源中匹配的原文片段，可按引用查看证据；未生成模型结论。')).toBeVisible();
    await page.locator('.source-card').last().locator('summary').first().click();
    await page.locator('.source-card').last().getByRole('button',{name:'查看证据',exact:true}).first().click();
    await expect(page.getByLabel('证据详情')).toContainText('内容 SHA256');
    expect(await page.evaluate(()=>({node:typeof (window as any).require,ipc:typeof (window.orvia as any).invoke}))).toEqual({node:'undefined',ipc:'undefined'});
    await app.evaluate(({BrowserWindow})=>{BrowserWindow.getAllWindows()[0].setSize(760,560);});
    await page.getByLabel('证据详情').scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(results,'sources-narrow.png')});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await app.close();app=await launch();page=await app.firstWindow();
    await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('navigation',{name:'历史会话'}).getByRole('button').first().click();
    await expect(page.locator('.source-card')).toHaveCount(3);
    await page.locator('.source-card').last().locator('summary').first().click();
    await page.locator('.source-card').last().getByRole('button',{name:'查看证据',exact:true}).first().click();
    await expect(page.getByLabel('证据详情')).toContainText('访问时间');
    await page.getByRole('button',{name:'＋ 新建对话',exact:true}).click();
    await send(page,'ask','许可');
    await expect(page.locator('.source-card').last()).toContainText('没有匹配来源');
    await expect(page.getByLabel('当前操作计划')).toHaveCount(0);
    await page.screenshot({path:path.join(results,'isolated-empty.png')});
  }finally{await app.close();}
});

test('M12 缺搜索凭据、URL拒绝、失败和截断（网络mock）',async()=>{
  const {results,launch}=await fixture(true);const app=await launch();
  try{
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByLabel('需求类型').selectOption('search');
    await expect(page.locator('#composer-hint')).toContainText('搜索不可用');
    await send(page,'search','合成');
    await expect(page.locator('.source-card').last()).toContainText('SEARCH_UNAVAILABLE');
    await send(page,'read','http://127.0.0.1/');
    await expect(page.locator('.source-card').last()).toContainText('URL_BLOCKED');
    await send(page,'read','https://example.com/fail');
    await expect(page.locator('.source-card').last()).toContainText('HTTP_FAILED');
    await send(page,'read','https://example.com/long');
    await page.locator('.source-card').last().locator('summary').click();
    await expect(page.locator('.source-card').last()).toContainText('原文已截断');
    await page.locator('.source-card').last().getByRole('button',{name:'查看证据',exact:true}).click();
    await expect(page.getByLabel('证据详情')).toContainText('原文已截断');
    await page.screenshot({path:path.join(results,'truncated-evidence.png')});
    await expect(page.getByLabel('当前操作计划')).toHaveCount(0);
  }finally{await app.close();}
});
