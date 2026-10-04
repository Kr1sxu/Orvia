import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp} from 'node:fs/promises';
import path from 'node:path';
import {documentFixtures} from '../integration/m13-fixtures';

test('M15 显式选择文档、预览正文、原生确认后生成并回查引用',async()=>{
  const results=path.resolve(process.env.ORVIA_TEST_RESULTS??'artifacts/test-results/M15');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'e2e-'));documentFixtures(work);
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M15_INPUT:path.join(work,'synthetic.docx')};
  delete (env as NodeJS.ProcessEnv).ELECTRON_RUN_AS_NODE;
  for(const key of ['DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete (env as NodeJS.ProcessEnv)[key];
  const app=await electron.launch({args:[path.resolve('tests/e2e/m15-launch.cjs')],env});
  try{
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'添加附件'}).click();
    const panel=page.getByLabel('生成式文档与来源回答');await expect(panel).toBeVisible();
    const bypass=await page.evaluate(async()=>{
      const list=await window.orvia.chatList();if(!list.ok)throw new Error('list');
      const id=list.result.conversations[0].id,snapshot=await window.orvia.chatGet({id});if(!snapshot.ok)throw new Error('snapshot');
      return window.orvia.chatSynthesisGenerate({id,mode:'summary',question:'概括',sources:[{kind:'document',evidence_id:snapshot.result.documents![0].evidence_id}],revision:'a'.repeat(64),request_id:crypto.randomUUID()});
    });
    expect(bypass.ok).toBe(false);
    await panel.getByRole('checkbox').first().check();
    await panel.getByRole('button',{name:'预览拟发送片段'}).click();
    const preview=page.getByLabel('模型发送范围预览');await expect(preview).toContainText('deepseek-flash');
    await expect(preview).toContainText('合成');
    await preview.getByRole('button',{name:'确认发送并生成回答'}).click();
    const answer=page.getByLabel('模型综合回答');await expect(answer).toContainText('需要保留来源');
    await answer.locator('summary').click();
    await answer.getByRole('button',{name:/synthetic.docx/}).first().click();
    await expect(page.getByLabel('文档证据详情')).toContainText('保留来源');
    expect(await page.evaluate(()=>({node:typeof (window as any).require,ipc:typeof (window.orvia as any).invoke}))).toEqual({node:'undefined',ipc:'undefined'});
    await page.screenshot({path:path.join(results,'synthesis.png')});
  }finally{await app.close();}
});

test('M15 用户在原生框取消后不调用模型',async()=>{
  const results=path.resolve(process.env.ORVIA_TEST_RESULTS??'artifacts/test-results/M15');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'cancel-'));documentFixtures(work);
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M15_INPUT:path.join(work,'synthetic.docx'),ORVIA_M15_CONFIRM:'0'};
  delete (env as NodeJS.ProcessEnv).ELECTRON_RUN_AS_NODE;
  for(const key of ['DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete (env as NodeJS.ProcessEnv)[key];
  const app=await electron.launch({args:[path.resolve('tests/e2e/m15-launch.cjs')],env});
  try{
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'添加附件'}).click();
    const panel=page.getByLabel('生成式文档与来源回答');await panel.getByRole('checkbox').first().check();
    await panel.getByRole('button',{name:'预览拟发送片段'}).click();
    await page.getByLabel('模型发送范围预览').getByRole('button',{name:'确认发送并生成回答'}).click();
    await expect(page.getByText('已取消正文发送；未调用模型。')).toBeVisible();
    await expect(page.getByLabel('模型综合回答')).toHaveCount(0);
  }finally{await app.close();}
});
