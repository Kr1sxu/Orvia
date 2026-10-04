import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp} from 'node:fs/promises';
import path from 'node:path';

test('V3-003菜单、键盘、持久化、原生删除取消和确认',async()=>{
  const results=path.resolve('artifacts/test-results/V3-003');await mkdir(results,{recursive:true});
  const profile=await mkdtemp(path.join(results,'profile-'));
  const env={...process.env,ORVIA_DEV_DATA_DIR:profile};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete env[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/m20-launch.cjs'),`--user-data-dir=${profile}`],env});
  let app=await launch();
  try{
    let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    const ids=await page.evaluate(async()=>{
      const a=await window.orvia.chatCreate({client_request_id:crypto.randomUUID(),title:'第一条合成对话'});
      const b=await window.orvia.chatCreate({client_request_id:crypto.randomUUID(),title:'第二条合成对话'});
      if(!a.ok||!b.ok)throw Error('create');return[a.result.id,b.result.id];
    });
    await page.reload();await expect(page.getByRole('button',{name:'第一条合成对话',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'第一条合成对话',exact:true}).click();
    const more=page.getByRole('button',{name:'更多操作：第一条合成对话'});
    await more.focus();await page.keyboard.press('Enter');
    await expect(page.getByRole('menu')).toBeVisible();await expect(page.getByRole('menuitem',{name:'置顶',exact:true})).toBeFocused();
    await page.keyboard.press('ArrowDown');await expect(page.getByRole('menuitem',{name:'重命名'})).toBeFocused();
    await page.keyboard.press('Escape');await expect(page.getByRole('menu')).toHaveCount(0);await expect(more).toBeFocused();
    await more.click();await page.getByRole('menuitem',{name:'置顶',exact:true}).click();
    await expect(page.locator('.conversation-row').first()).toContainText('第一条合成对话');
    await expect(page.locator('.conversation-row').first()).toContainText('已置顶');
    await more.click();await page.getByRole('menuitem',{name:'重命名'}).click();
    await page.getByLabel('对话名称',{exact:true}).fill('  ');await expect(page.getByRole('button',{name:'保存名称'})).toBeDisabled();
    await page.getByLabel('对话名称',{exact:true}).fill('改名后的合成对话');await page.getByRole('button',{name:'保存名称'}).click();
    await expect(page.getByRole('dialog')).not.toBeVisible();await expect(page.locator('.topbar')).toContainText('改名后的合成对话');
    await app.close();app=await launch();page=await app.firstWindow();
    await expect(page.getByRole('button',{name:'改名后的合成对话',exact:true})).toBeVisible();
    await expect(page.locator('.conversation-row').first()).toContainText('已置顶');
    await page.getByRole('button',{name:'改名后的合成对话',exact:true}).click();
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(960,680));
    await page.getByRole('button',{name:'更多操作：改名后的合成对话'}).click();
    const bounds=await page.getByRole('menu').boundingBox();const viewport=page.viewportSize()??await page.evaluate(()=>({width:innerWidth,height:innerHeight}));
    expect(bounds!.x).toBeGreaterThanOrEqual(0);expect(bounds!.y+bounds!.height).toBeLessThanOrEqual(viewport.height);
    await page.screenshot({path:path.join(results,'conversation-menu.png')});
    await page.locator('.topbar').click();await expect(page.getByRole('menu')).toHaveCount(0);
    // 仅测试端替换原生用户选择，断言产品实际传入的取消默认值和永久删除提示。
    await app.evaluate(({dialog})=>{dialog.showMessageBox=async(_window:any,options:any)=>{(globalThis as any).__deleteOptions=options;return{response:0,checkboxChecked:false};};});
    await page.getByRole('button',{name:'更多操作：改名后的合成对话'}).click();await page.getByRole('menuitem',{name:'删除',exact:true}).click();
    await expect(page.getByRole('button',{name:'改名后的合成对话',exact:true})).toBeVisible();
    await expect.poll(()=>app.evaluate(()=>(globalThis as any).__deleteOptions?.defaultId)).toBe(0);
    const detail=await app.evaluate(()=>(globalThis as any).__deleteOptions.detail);expect(detail).toContain('会话消息、引用证据');
    await app.evaluate(({dialog})=>{dialog.showMessageBox=async()=>({response:1,checkboxChecked:false});});
    await page.getByRole('button',{name:'更多操作：改名后的合成对话'}).click();await page.getByRole('menuitem',{name:'删除',exact:true}).click();
    await expect(page.getByRole('button',{name:'改名后的合成对话',exact:true})).toHaveCount(0);
    await expect(page.locator('.topbar')).not.toContainText('改名后的合成对话');
    const replies=await page.evaluate(async id=>[await window.orvia.chatGet({id}),await window.orvia.chatList()],ids[0]);
    expect(replies[0].ok).toBe(false);expect(replies[1].ok).toBe(true);
    await expect(page.getByRole('button',{name:'第二条合成对话',exact:true})).toBeVisible();
    await app.close();app=await launch();page=await app.firstWindow();
    await expect(page.getByRole('button',{name:'第二条合成对话',exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'改名后的合成对话',exact:true})).toHaveCount(0);
  }finally{await app.close();}
});
