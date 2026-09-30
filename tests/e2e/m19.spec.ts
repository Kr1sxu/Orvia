import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,writeFile,readFile} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
const run=promisify(execFile),results=path.resolve('artifacts/test-results/M19/product');

async function launch(scale=1){
  await mkdir(results,{recursive:true});const profile=await mkdtemp(path.join(results,'profile-'));
  const env={...process.env,ORVIA_DEV_DATA_DIR:profile};delete env.ELECTRON_RUN_AS_NODE;
  for(const name of ['DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete env[name];
  const app=await electron.launch({args:[path.resolve('tests/e2e/m11-launch.cjs'),`--force-device-scale-factor=${scale}`],env});
  const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
  return{app,page,profile};
}
async function identity(app:import('@playwright/test').ElectronApplication){return app.evaluate(({BrowserWindow})=>{const w=BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().startsWith('file:'))!;const b=w.getNativeWindowHandle();return{handle:Number(b.length>=8?b.readBigUInt64LE():b.readUInt32LE()),pid:process.pid,bounds:w.getBounds(),max:w.isMaximized(),snap:w.isSnapped(),full:w.isFullScreen()}})}
async function native(app:import('@playwright/test').ElectronApplication,action:string){const own=await identity(app);const reply=await run(path.join(process.env.SystemRoot!,'System32/WindowsPowerShell/v1.0/powershell.exe'),['-NoProfile','-NonInteractive','-File',path.resolve('tests/e2e/m19-native-window.ps1'),'-WindowHandle',String(own.handle),'-OwnerProcess',String(own.pid),'-Action',action],{windowsHide:true,timeout:15000,encoding:'utf8'});return JSON.parse(reply.stdout)}

test('M19 真实产品外轮廓、原生窗口状态与系统命中区域（合成数据）',async()=>{
  test.skip(process.env.ORVIA_M19_DESKTOP_ALLOWED!=='1','需用户提供可见桌面验收时段；不抢占当前前台');
  const {app,page}=await launch();const states:any[]=[];
  try{
    await app.evaluate(async({BrowserWindow,screen})=>{const w=BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().startsWith('file:'))!;const work=screen.getPrimaryDisplay().workArea;const bg=new BrowserWindow({...work,frame:false,skipTaskbar:true,webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false}});await bg.loadURL('data:text/html,'+encodeURIComponent('<style>body{background:#c8d8e5;margin:0}</style>'));bg.showInactive();bg.setAlwaysOnTop(true);w.setAlwaysOnTop(true);w.setBounds({x:90,y:90,width:1120,height:880});w.focus();});
    async function capture(name:string){await native(app,'Focus');const own=await identity(app);const reply=await run(path.join(process.env.SystemRoot!,'System32/WindowsPowerShell/v1.0/powershell.exe'),['-NoProfile','-NonInteractive','-File',path.resolve('tests/e2e/m19-desktop-capture.ps1'),'-WindowHandle',String(own.handle),'-Output',path.join(results,name+'.png'),'-Padding',own.max||own.snap||own.full?'0':'10'],{windowsHide:true,encoding:'utf8',timeout:15000});states.push({...own,name,native:JSON.parse(reply.stdout)});}
    await capture('ordinary');const hits=await native(app,'Inspect');expect(hits.thickFrame).toBe(true);expect(hits.captionHit).toBe(2);expect(hits.leftHit).toBe(10);expect(hits.rightHit).toBe(11);expect(hits.bottomHit).toBe(15);
    const original=await identity(app);await native(app,'Move');expect((await identity(app)).bounds.x).not.toBe(original.bounds.x);
    await native(app,'DoubleTitle');await expect.poll(async()=>(await identity(app)).max).toBe(true);await capture('maximized');
    await native(app,'DoubleTitle');await expect.poll(async()=>(await identity(app)).max).toBe(false);await capture('restored');
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().startsWith('file:'))!.minimize());expect(await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().startsWith('file:'))!.isMinimized())).toBe(true);await app.evaluate(({BrowserWindow})=>{const w=BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().startsWith('file:'))!;w.restore();w.focus();});
    await native(app,'FullScreenKey');await expect.poll(async()=>(await identity(app)).full).toBe(true);await capture('fullscreen');await native(app,'EscapeKey');await expect.poll(async()=>(await identity(app)).full).toBe(false);
    await app.evaluate(({BrowserWindow})=>{const w=BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().startsWith('file:'))!;w.setBounds({x:90,y:90,width:760,height:560});w.focus()});
    await expect.poll(async()=>(await identity(app)).bounds.width).toBe(760);await expect.poll(async()=>(await identity(app)).bounds.height).toBe(560);
    await expect(page.getByLabel('输入需求')).toBeInViewport();await capture('minimum');
    await native(app,'SnapLeft');await expect.poll(async()=>(await identity(app)).snap).toBe(true);await capture('snapped');
    await writeFile(path.join(results,'native-window.json'),JSON.stringify({scope:'产品原生窗口；命中/双击/移动/贴靠由测试侧系统API驱动，非人工鼠标验收',realModels:0,hits,states},null,2));
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().filter(w=>!w.webContents.getURL().startsWith('file:')).forEach(w=>w.destroy()));
    await native(app,'Close');await expect.poll(async()=>{try{return (await app.windows()).length}catch{return 0}}).toBe(0);
  }finally{await app.close().catch(()=>{});}
});

for(const scale of [1,1.25,1.5,2])test(`M19 ${scale*100}%渲染倍率、离线字体与最小窗口键盘（非更改系统DPI）`,async()=>{
  const {app,page}=await launch(scale);
  try{
    await page.evaluate(()=>Promise.all(Array.from(document.fonts).map(f=>f.load())));
    const resources=await page.evaluate(()=>({fonts:Array.from(document.fonts).map(f=>({family:f.family,status:f.status})),images:Array.from(document.querySelectorAll<HTMLImageElement>('.brand-mark,.welcome-mark')).map(img=>({loaded:img.complete&&img.naturalWidth>0,src:img.src})),node:typeof(window as any).require,ipc:typeof(window.orvia as any).invoke}));
    expect(resources.fonts).toHaveLength(3);expect(resources.fonts.every(f=>f.status==='loaded')).toBe(true);expect(resources.images.every(i=>i.loaded&&i.src.startsWith('file:'))).toBe(true);expect(resources.node).toBe('undefined');expect(resources.ipc).toBe('undefined');
    await page.screenshot({path:path.join(results,`welcome-${scale}.png`)});
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().find(w=>w.webContents.getURL().startsWith('file:'))!.setSize(760,560));
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await expect(page.getByLabel('输入需求')).toBeInViewport();
    await page.getByRole('button',{name:'设置',exact:true}).click();await expect(page.getByRole('button',{name:'关闭设置'})).toBeFocused();await page.keyboard.press('Shift+Tab');await expect(page.getByRole('button',{name:'重新检查连接'})).toBeFocused();await page.keyboard.press('Escape');
    const input=page.getByLabel('输入需求');await input.fill('长中文与mixed-text 0123456789 '+ '合成内容'.repeat(80));await input.press('Shift+Enter');await expect(input).toHaveValue(/\n$/);
    await page.emulateMedia({reducedMotion:'reduce'});expect(await page.locator('.send').evaluate(el=>getComputedStyle(el).transitionDuration)).toBe('0s');
    await page.screenshot({path:path.join(results,`minimum-${scale}.png`)});await writeFile(path.join(results,`resources-${scale}.json`),JSON.stringify({...resources,scope:'force-device-scale-factor渲染倍率，不是系统DPI改动'},null,2));
  }finally{await app.close();}
});
