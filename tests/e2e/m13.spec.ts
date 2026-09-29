import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,readFile} from 'node:fs/promises';
import path from 'node:path';
import {documentFixtures} from '../integration/m13-fixtures';

async function fixture(image=false){
  const results=path.resolve('artifacts/test-results/M13');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'e2e-'));documentFixtures(work);
  const output=path.join(work,'result.md');
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M13_INPUT:path.join(work,image?'synthetic.png':'synthetic.docx'),ORVIA_M13_OUTPUT:output};
  delete (env as NodeJS.ProcessEnv).ELECTRON_RUN_AS_NODE;
  for(const key of ['DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete (env as NodeJS.ProcessEnv)[key];
  return {results,output,launch:()=>electron.launch({args:[path.resolve('tests/e2e/m13-launch.cjs')],env})};
}

test('M13 选择附件、原文引用、预览导出、不覆盖、重启及会话隔离',async()=>{
  const {results,output,launch}=await fixture();let app=await launch();
  try{
    let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'＋ 添加附件',exact:true}).click();
    const card=page.getByLabel('文档与引用').last();await expect(card).toContainText('synthetic.docx');
    await card.locator('summary').first().click();
    await card.getByRole('button',{name:'查看文档证据',exact:true}).click();
    const detail=page.getByLabel('文档证据详情');await expect(detail).toContainText('保留来源');
    const denied=await page.evaluate(async()=>{
      const list=await window.orvia.chatList();if(!list.ok)throw new Error('list');
      const id=list.result.conversations[0].id;const snapshot=await window.orvia.chatGet({id});if(!snapshot.ok)throw new Error('snapshot');
      return window.orvia.chatDocumentExport({id,evidence_id:snapshot.result.documents![0].evidence_id,format:'md',revision:'a'.repeat(64),request_id:crypto.randomUUID()});
    });
    expect(denied.ok).toBe(false);
    await detail.getByRole('button',{name:'预览 Markdown 导出'}).click();
    const preview=page.getByLabel('文档导出预览');await expect(preview).toContainText('2/2');
    await preview.getByRole('button',{name:'选择路径并确认导出'}).click();
    await expect(page.getByText('已创建新导出文件并核验；不会覆盖已有文件。')).toBeVisible();
    await expect(page.getByLabel('文档导出记录')).toContainText('result.md');
    const saved=await readFile(output,'utf8');expect(saved).toContain('许可');expect(saved).toContain('SHA256');
    await detail.getByRole('button',{name:'预览 Markdown 导出'}).click();
    await preview.getByRole('button',{name:'选择路径并确认导出'}).click();
    await expect(page.getByText('目标已存在，请选择新的文件名',{exact:true})).toBeVisible();
    expect(await readFile(output,'utf8')).toBe(saved);
    expect(await page.evaluate(()=>({node:typeof (window as any).require,ipc:typeof (window.orvia as any).invoke}))).toEqual({node:'undefined',ipc:'undefined'});
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(760,560));
    await page.screenshot({path:path.join(results,'document-export-narrow.png')});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await app.close();app=await launch();page=await app.firstWindow();
    await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('navigation',{name:'历史会话'}).getByRole('button').first().click();
    await page.getByLabel('需求类型').selectOption('document');await page.getByLabel('输入需求').fill('许可');await page.getByLabel('输入需求').press('Enter');
    await expect(page.getByLabel('文档与引用')).toHaveCount(2);
    await expect(page.getByLabel('输入需求')).toHaveValue('');
    await page.getByRole('button',{name:'＋ 新建对话',exact:true}).click();
    await page.getByLabel('需求类型').selectOption('document');await page.getByLabel('输入需求').fill('许可');await page.getByLabel('输入需求').press('Enter');
    await expect(page.getByText('请先添加文档附件。',{exact:true})).toBeVisible();
    await expect(page.getByLabel('文档与引用')).toHaveCount(0);
    await expect(page.getByLabel('当前操作计划')).toHaveCount(0);
  }finally{await app.close();}
});

test('M13 本地真实 OCR 合成图片：识别方式和置信度可见',async()=>{
  const {results,launch}=await fixture(true);const app=await launch();
  try{
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'＋ 添加附件',exact:true}).click();
    const card=page.getByLabel('文档与引用').last();await expect(card).toContainText('synthetic.png',{timeout:60000});
    await card.locator('summary').first().click();await card.getByRole('button',{name:'查看文档证据'}).click();
    await expect(page.getByLabel('文档证据详情')).toContainText('OCR 识别');
    await expect(page.getByLabel('文档证据详情')).toContainText('置信度');
    await expect(page.getByLabel('文档证据详情')).toContainText('ORVIA');
    await page.screenshot({path:path.join(results,'ocr-evidence.png')});
  }finally{await app.close();}
});
