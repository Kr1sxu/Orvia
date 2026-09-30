import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,readFile,stat} from 'node:fs/promises';
import path from 'node:path';
import {documentFixtures} from '../integration/m13-fixtures';

async function launch(cancel=false){
  const results=path.resolve(process.env.ORVIA_TEST_RESULTS??'artifacts/test-results/M16');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'e2e-'));documentFixtures(work);
  const output=path.join(work,'outputs');await mkdir(output);
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M16_INPUT:path.join(work,'synthetic.docx'),ORVIA_M16_OUTPUT_DIR:output,ORVIA_M16_CANCEL:cancel?'1':'0'};
  delete (env as NodeJS.ProcessEnv).ELECTRON_RUN_AS_NODE;
  for(const key of ['DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete (env as NodeJS.ProcessEnv)[key];
  const app=await electron.launch({args:[path.resolve('tests/e2e/m16-launch.cjs')],env});
  return {app,output,results};
}

async function generate(page:import('@playwright/test').Page){
  await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'添加附件'}).click();
  const panel=page.getByLabel('生成式文档与来源回答');await panel.getByRole('checkbox').first().check();
  await panel.getByRole('button',{name:'预览拟发送片段'}).click();
  await page.getByLabel('模型发送范围预览').getByRole('button',{name:'确认这些片段并调用 Main 模型'}).click();
  await expect(page.getByLabel('模型综合回答')).toBeVisible();
  await page.getByRole('button',{name:'制作 Word／PPT／PDF 简报'}).click();
  return page.getByLabel('简报成品制作');
}

test('M16 同一已生成回答制作三种可解析成品，绕过预览被拒绝',async()=>{
  const {app,output,results}=await launch();
  try{
    const page=await app.firstWindow();const composer=await generate(page);
    const bypass=await page.evaluate(async()=>{
      const list=await window.orvia.chatList();if(!list.ok)throw new Error('list');
      return window.orvia.chatPublicationSave({id:list.result.conversations[0].id,message_id:crypto.randomUUID(),format:'pdf',title:'x',answer:'x',claim_texts:['x'],revision:'a'.repeat(64),request_id:crypto.randomUUID()});
    });
    expect(bypass.ok).toBe(false);
    await composer.getByLabel('简报标题').fill('合成简报');
    for(const [format,signature] of [['docx','PK'],['pptx','PK'],['pdf','%PDF']] as const){
      await composer.getByLabel('成品格式').selectOption(format);
      await composer.getByRole('button',{name:'预览内容与版面'}).click();
      const preview=page.getByLabel('简报版式预览');await expect(preview).toContainText('合成简报');
      await expect(preview).toContainText('来源与引用');
      await preview.getByRole('button',{name:'选择新文件路径并确认保存'}).click();
      const result=page.getByLabel('成品核验结果').last();await expect(result).toContainText(format.toUpperCase());
      const filename=(await result.textContent())?.match(/Orvia-brief-[a-f0-9]{12}\.(docx|pptx|pdf)/)?.[0];
      expect(filename).toBeTruthy();
      const file=path.join(output,filename!);
      expect((await readFile(file)).subarray(0,signature.length).toString()).toBe(signature);
      expect((await stat(file)).size).toBeGreaterThan(1000);
    }
    await page.screenshot({path:path.join(results,'publication.png')});
  }finally{await app.close();}
});

test('M16 原生保存框取消后没有成品记录',async()=>{
  const {app}=await launch(true);
  try{
    const page=await app.firstWindow();const composer=await generate(page);
    await composer.getByRole('button',{name:'预览内容与版面'}).click();
    await page.getByLabel('简报版式预览').getByRole('button',{name:'选择新文件路径并确认保存'}).click();
    await expect(page.getByText('已取消保存，未创建文件')).toBeVisible();
    await expect(page.getByLabel('成品核验结果')).toHaveCount(0);
  }finally{await app.close();}
});
