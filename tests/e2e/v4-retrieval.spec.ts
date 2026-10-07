import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,readFile} from 'node:fs/promises';
import path from 'node:path';
import {documentFixtures} from '../integration/m13-fixtures';

test('V4-004 缺模型降级、首次下载取消、关联原文与重启',async()=>{
  const root=path.resolve('artifacts/test-results/V4-004');await mkdir(root,{recursive:true});
  const work=await mkdtemp(path.join(root,'electron-'));documentFixtures(work);
  const counter=path.join(work,'calls.json');
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M20_CONFIRM:'0',ORVIA_M20_INPUTS:JSON.stringify([path.join(work,'synthetic.docx')]),ORVIA_M20_COUNTER:counter};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','REDIS_PASSWORD'])delete env[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/m20-launch.cjs')],env});let app=await launch();
  try{
    let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'添加本地资料',exact:true}).click();await page.getByRole('menuitem',{name:'添加文件（最多3个）'}).click();
    await expect(page.getByLabel('本次需求资料')).toContainText('synthetic.docx');
    await page.getByRole('button',{name:'设置',exact:true}).click();let panel=page.getByLabel('本地混合检索',{exact:true});
    await expect(panel).toContainText('关键词降级：尚未准备本地模型');
    await panel.getByRole('button',{name:'确认下载官方模型'}).click();await expect(panel).toContainText('已取消下载。');
    await panel.getByRole('button',{name:'建立当前资料索引'}).click();await expect(panel).toContainText('索引未完成：尚未准备本地模型');
    await panel.getByLabel('检索问题').fill('许可');await panel.getByRole('button',{name:'检索关联资料'}).click();await expect(panel).toContainText('合成文档许可条件');
    await panel.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(work,'keyword.png')});
    await panel.getByRole('button',{name:'清除当前会话向量'}).click();await expect(panel).toContainText('当前会话全部向量已清除');
    await app.close();app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'设置',exact:true}).click();panel=page.getByLabel('本地混合检索',{exact:true});
    await panel.getByLabel('检索问题').fill('许可');await panel.getByRole('button',{name:'检索关联资料'}).click();await expect(panel).toContainText('合成文档许可条件');
    await page.screenshot({path:path.join(work,'restart.png')});
    let calls=[];try{calls=JSON.parse(await readFile(counter,'utf8'));}catch{}expect(calls).toEqual([]);
  }finally{await app.close();}
});

test('V4-004 显式已有Qwen核验、真实混合索引及重启加载',async()=>{
  test.skip(!process.env.ORVIA_EMBEDDING_MODEL_PATH,'必须显式提供首次批准后核验的固定模型目录；不自动下载');
  test.setTimeout(540000);
  const root=path.resolve('artifacts/test-results/V4-004');await mkdir(root,{recursive:true});
  const work=await mkdtemp(path.join(root,'electron-real-'));documentFixtures(work);
  const counter=path.join(work,'calls.json');
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M20_CONFIRM:'1',ORVIA_M20_DIRECTORY:process.env.ORVIA_EMBEDDING_MODEL_PATH!,ORVIA_M20_INPUTS:JSON.stringify([path.join(work,'synthetic.docx')]),ORVIA_M20_COUNTER:counter};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','REDIS_PASSWORD'])delete env[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/m20-launch.cjs')],env});let app=await launch();
  try{
    let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'添加本地资料',exact:true}).click();await page.getByRole('menuitem',{name:'添加文件（最多3个）'}).click();
    await expect(page.getByLabel('本次需求资料')).toContainText('synthetic.docx');
    await page.getByRole('button',{name:'设置',exact:true}).click();let panel=page.getByLabel('本地混合检索',{exact:true});
    await panel.getByRole('button',{name:'选择已有模型'}).click();await expect(panel).toContainText('本地模型已就绪',{timeout:190000});
    await panel.getByRole('button',{name:'建立当前资料索引'}).click();await expect(panel).toContainText('已建立 2 个片段的向量索引',{timeout:125000});
    await panel.getByLabel('检索问题').fill('资料许可要求是什么？');await panel.getByRole('button',{name:'检索关联资料'}).click();
    await expect(panel).toContainText('已融合关键词和向量召回',{timeout:35000});await expect(panel).toContainText('保留来源');
    await panel.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(work,'hybrid.png')});
    await app.close();app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'设置',exact:true}).click();panel=page.getByLabel('本地混合检索',{exact:true});
    await panel.getByRole('button',{name:'加载此前模型'}).click();await expect(panel).toContainText('本地模型已就绪',{timeout:190000});
    await panel.getByLabel('检索问题').fill('资料许可要求是什么？');await panel.getByRole('button',{name:'检索关联资料'}).click();
    await expect(panel).toContainText('已融合关键词和向量召回',{timeout:35000});await expect(panel).toContainText('保留来源');
    let calls=[];try{calls=JSON.parse(await readFile(counter,'utf8'));}catch{}expect(calls).toEqual([]);
  }finally{await app.close();}
});
