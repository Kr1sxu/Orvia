import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,readFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';

for(const mode of ['normal','partial','ocr'])test(`V3-005 ${mode} 文件状态、来源详情与发送边界`,async()=>{
 const root=path.resolve('artifacts/test-results/V3-005');await mkdir(root,{recursive:true});
 const work=await mkdtemp(path.join(root,mode+'-'));
 execFileSync(path.resolve('backend/.venv/Scripts/python.exe'),['-X','utf8','-c',`import sys\nfrom pathlib import Path\nsys.path[:0]=['backend/src','backend/tests']\nfrom test_m13_parser import text_pdf\nfrom PIL import Image\np=Path(sys.argv[1])\np.joinpath('normal.pdf').write_bytes(text_pdf())\np.joinpath('partial.pdf').write_bytes(text_pdf()+b'\\n% V3-PARTIAL')\nImage.new('RGB',(20,20)).save(p/'ocr.png')`,work],{windowsHide:true});
 const counter=path.join(work,'calls.json');
 const env:NodeJS.ProcessEnv={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M20_INPUTS:JSON.stringify([path.join(work,mode+(mode==='ocr'?'.png':'.pdf'))]),ORVIA_M20_COUNTER:counter};
 for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete env[key];
 const app=await electron.launch({args:[path.resolve('tests/e2e/v3-document-launch.cjs')],env});
 const calls=async()=>{try{return JSON.parse(await readFile(counter,'utf8'));}catch{return[];}};
 try{
  const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible({timeout:30000});
  await page.getByRole('button',{name:'添加本地资料',exact:true}).click();await page.getByRole('menuitem',{name:'添加文件（最多3个）'}).click();
  const card=page.getByLabel('文档与引用').last();await expect(card).toContainText(mode==='ocr'?'无法回答':mode==='partial'?'部分内容无法读取':'已准备回答');
  expect(await card.innerText()).not.toMatch(/证据|文件版本|不可信|SHA256/);expect(await calls()).toEqual([]);
  if(mode==='ocr'){
   await expect(card).toContainText('含可选中文字');await expect(page.getByRole('button',{name:'添加本地资料',exact:true})).toBeEnabled();await card.scrollIntoViewIfNeeded();await expect(page.getByLabel('模型发送范围预览')).toHaveCount(0);
  }else{
   await page.getByLabel('输入需求').fill('总结这份文档');await expect(page.getByRole('button',{name:'发送',exact:true})).toBeEnabled();await page.getByLabel('输入需求').press('Enter');
   const preview=page.getByLabel('模型发送范围预览');try{await expect(preview).toBeVisible();}catch(error){await test.info().attach('page',{body:await page.locator('body').innerText(),contentType:'text/plain'});throw error;}expect(await preview.innerText()).not.toMatch(/[a-f0-9]{64}/);
   if(mode==='partial')await expect(preview).toContainText('回答不包含这些内容');
   expect(await calls()).toEqual([]);
   // 第一次原生确认取消，第二次明确批准；确认前以及取消后模型都不能收到正文。
   await app.evaluate(({dialog})=>{dialog.showMessageBox=(async()=>({response:0,checkboxChecked:false})) as typeof dialog.showMessageBox;});
   await preview.getByRole('button',{name:'确认发送并生成回答'}).click();await expect(preview).toHaveCount(0);expect(await calls()).toEqual([]);
   await page.getByText('调整回答使用的资料',{exact:true}).click();await page.getByRole('button',{name:'预览拟发送片段',exact:true}).click();await expect(preview).toBeVisible();
   await app.evaluate(({dialog})=>{dialog.showMessageBox=(async()=>({response:1,checkboxChecked:false})) as typeof dialog.showMessageBox;});
   await preview.getByRole('button',{name:'确认发送并生成回答'}).click();
   const answer=page.getByLabel('模型综合回答');await expect(answer).toContainText('合成摘要');expect(await answer.innerText()).not.toMatch(/[a-f0-9]{64}/);
   await answer.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(work,'answer.png')});await answer.getByRole('button',{name:/第 1 页/}).click();await expect(page.getByLabel('文档证据详情')).toContainText('文件版本');expect(await calls()).toEqual([{role:'main',stream:true}]);
  }
  await page.screenshot({path:path.join(work,'result.png')});
 }finally{await app.close();}
});
