import { _electron as electron, expect, test } from '@playwright/test';
import path from 'node:path';
import { mkdir, mkdtemp, writeFile } from 'node:fs/promises';

test('M11 历史阅读、折叠、输入法、键盘焦点与显式重试（合成数据）', async () => {
  const results=path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M11');
  await mkdir(results,{recursive:true});
  const profile=await mkdtemp(path.join(results,'ui-profile-'));
  const root=await mkdtemp(path.join(results,'ui-files-'));
  await Promise.all(Array.from({length:15},(_,i)=>writeFile(path.join(root,`synthetic-${i}.txt`),'synthetic only')));
  const env={...process.env,ORVIA_DEV_DATA_DIR:profile};delete env.ELECTRON_RUN_AS_NODE;
  for(const key of ['DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete env[key];
  const app=await electron.launch({args:[path.resolve('tests/e2e/m11-launch.cjs')],env});
  try {
    const page=await app.firstWindow();
    await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    const id=await page.evaluate(async()=>{
      const result=await window.orvia.chatCreate({client_request_id:crypto.randomUUID(),title:'合成阅读测试'});
      if(!result.ok)throw Error('create');
      for(let i=0;i<12;i++){
        const reply=await window.orvia.chatSend({id:result.result.id,request_id:crypto.randomUUID(),text:'合成历史 '+i+' '+ '中文内容'.repeat(180)});
        if(!reply.ok)throw Error('send');
      }
      return result.result.id;
    });
    await page.reload();
    await page.getByRole('button',{name:'合成阅读测试',exact:true}).click();
    await expect(page.locator('.long-message').first()).toBeVisible();
    await expect(page.locator('.long-message').first()).not.toHaveAttribute('open','');
    await page.locator('.message-scroll').evaluate(el=>{el.scrollTop=0;el.dispatchEvent(new Event('scroll'));});
    await page.evaluate(async cid=>{await window.orvia.chatSend({id:cid,request_id:crypto.randomUUID(),text:'新到合成消息'});},id);
    await page.getByRole('button',{name:'刷新状态',exact:true}).click();
    await expect(page.getByRole('button',{name:'↓ 查看最新消息'})).toBeVisible();
    expect(await page.locator('.message-scroll').evaluate(el=>el.scrollTop)).toBeLessThan(10);
    await page.getByRole('button',{name:'↓ 查看最新消息'}).click();
    await expect(page.getByRole('button',{name:'↓ 查看最新消息'})).toHaveCount(0);
    const input=page.getByLabel('输入需求');
    await input.fill('中文候选');
    await input.dispatchEvent('compositionstart');
    await input.dispatchEvent('keydown',{key:'Enter',code:'Enter',keyCode:229,isComposing:true,bubbles:true});
    await expect(input).toHaveValue('中文候选');
    await input.dispatchEvent('compositionend');
    await input.press('Shift+Enter');await expect(input).toHaveValue('中文候选\n');
    await page.getByRole('button',{name:'⚙ 设置'}).click();
    await expect(page.getByRole('button',{name:'关闭设置'})).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(page.getByRole('button',{name:'重新检查连接'})).toBeFocused();
    await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'关闭设置'})).toBeFocused();
    await page.keyboard.press('Escape');await expect(input).toBeFocused();
    await app.evaluate(({dialog},directory)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[directory]});},root);
    await page.getByRole('button',{name:'＋ 选择目录',exact:true}).click();
    const files=page.locator('.result-card').last().locator('details').first();
    await expect(files.locator('summary')).toContainText('15 项');
    await expect(files).not.toHaveAttribute('open','');
    await files.locator('summary').click();await expect(files.getByText('synthetic-0.txt',{exact:true})).toBeVisible();
    await input.fill('合成失败');await input.press('Enter');
    await expect(page.getByRole('button',{name:'重新尝试规划'})).toBeEnabled();
    const failures=page.locator('.message.user').filter({hasText:'合成失败'});
    const before=await failures.count();
    await page.getByRole('button',{name:'重新尝试规划'}).click();
    await expect(failures).toHaveCount(before+1);
    await expect(page.getByRole('button',{name:'重新尝试规划'})).toBeEnabled();
    await page.setViewportSize({width:760,height:560});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await expect(input).toBeInViewport();
    await page.screenshot({path:path.join(results,'ui-narrow.png')});
  } finally {await app.close();}
});
