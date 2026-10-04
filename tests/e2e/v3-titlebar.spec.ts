import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,writeFile} from 'node:fs/promises';
import path from 'node:path';

test('V3-002顶部去重、会话状态与窄窗口、原生窗口状态',async()=>{
  const results=path.resolve('artifacts/test-results/V3-002');await mkdir(results,{recursive:true});
  const profile=await mkdtemp(path.join(results,'profile-'));
  const env={...process.env,ORVIA_DEV_DATA_DIR:profile};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete env[key];
  // 启动器只隔离凭据和原生对话框；本轮简单寒暄不调用模型，也不选择或写入用户文件。
  const app=await electron.launch({args:[path.resolve('tests/e2e/m20-launch.cjs'),`--user-data-dir=${profile}`],env});
  try{
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    const check=async(name:string)=>{
      const bar=page.getByLabel('窗口拖动区域');await expect(bar).toBeVisible();await expect(bar).toHaveText('');await expect(bar.locator('img,svg')).toHaveCount(0);
      await expect(page.locator('.sidebar .brand')).toContainText('序航');await expect(page.locator('.sidebar .brand img')).toBeVisible();
      await expect(page.getByLabel('输入需求')).toBeInViewport();
      const layout=await page.evaluate(()=>{const bar=document.querySelector('.window-titlebar')!,top=document.querySelector('.topbar')!,side=document.querySelector('.sidebar')!;return{height:bar.getBoundingClientRect().height,bottom:bar.getBoundingClientRect().bottom,top:top.getBoundingClientRect().top,side:side.getBoundingClientRect().top,drag:getComputedStyle(bar).getPropertyValue('-webkit-app-region'),overflow:document.documentElement.scrollWidth>innerWidth};});
      expect(layout).toMatchObject({height:42,drag:'drag',overflow:false});expect(layout.top).toBe(layout.bottom);expect(layout.side).toBe(layout.bottom);
      await page.screenshot({path:path.join(results,name+'.png')});return layout;
    };
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(1120,880));
    const normal=await check('new-chat');
    await page.getByLabel('输入需求').fill('你好');await page.getByLabel('输入需求').press('Enter');
    await expect(page.getByText('你好！有什么可以帮你的吗？',{exact:true})).toBeVisible();await expect(page.locator('.topbar')).toContainText('已完成');
    await page.getByRole('button',{name:'新建对话',exact:true}).click();await page.getByRole('navigation',{name:'历史会话'}).getByRole('button').first().click();
    await expect(page.locator('.topbar')).toContainText('你好');await check('history');
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(760,560));const narrow=await check('narrow-history');
    await page.getByRole('button',{name:'新建对话',exact:true}).click();await check('narrow-new');
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].maximize());await expect.poll(()=>app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isMaximized())).toBe(true);
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].unmaximize());await expect.poll(()=>app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isMaximized())).toBe(false);
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].minimize());await expect.poll(()=>app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isMinimized())).toBe(true);
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].restore());await expect.poll(()=>app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].isMinimized())).toBe(false);
    await writeFile(path.join(results,'window.json'),JSON.stringify({normal,narrow,realModels:0,nativeWindowStates:true,scope:'真实Electron窗口API验证；不是人工点击原生按钮或拖动验收'},null,2));
  }finally{await app.close();}
});
