import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
const run=promisify(execFile),results=path.resolve('artifacts/test-results/M19');
test('M19定向安装版离线资源、安全边界与实际任务栏（旧冻结后端，非M20安装验收）',async()=>{
  test.skip(process.env.ORVIA_M19_DESKTOP_ALLOWED!=='1','需可见桌面验收时段');
  test.setTimeout(120000);
  const installed=path.join(results,'install-smoke/Orvia M19 Visual Test.exe');
  const record=JSON.parse((await readFile(path.join(results,'installation.json'),'utf8')).replace(/^\uFEFF/,''));
  expect(record.status).toBe('installed');expect(record.signature).toBe('NotSigned');
  const profile=await mkdtemp(path.join(results,'packaged-profile-'));
  const env={...process.env};for(const key of Object.keys(env))if(/^(ELECTRON_RUN_AS_NODE|PYTHONHOME|PYTHONPATH|DEEPSEEK_API_KEY|ZHIPU_API_KEY|MIMO_API_KEY|TAVILY_API_KEY|NODE_OPTIONS|NODE_PATH|ORVIA_.*|PLAYWRIGHT_.*)$/i.test(key))delete env[key];
  env.PATH=path.join(process.env.SystemRoot!,'System32');
  const app=await electron.launch({executablePath:installed,cwd:results,args:[`--user-data-dir=${profile}`],env});
  try{
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible({timeout:30000});
    expect(await app.evaluate(({app})=>({packaged:app.isPackaged,userData:app.getPath('userData')}))).toEqual({packaged:true,userData:profile});
    await page.evaluate(()=>Promise.all(Array.from(document.fonts).map(f=>f.load())));
    const resource=await page.evaluate(()=>({fonts:Array.from(document.fonts).map(f=>({family:f.family,status:f.status})),images:Array.from(document.querySelectorAll<HTMLImageElement>('.brand-mark,.welcome-mark')).map(img=>img.complete&&img.naturalWidth>0),node:typeof(window as any).require,ipc:typeof(window.orvia as any).invoke}));
    expect(resource.fonts).toHaveLength(3);expect(resource.fonts.every(f=>f.status==='loaded')).toBe(true);expect(resource.images.every(Boolean)).toBe(true);expect(resource.node).toBe('undefined');expect(resource.ipc).toBe('undefined');
    const settings=await page.evaluate(()=>window.orvia.settings());expect(settings.ok&&settings.result.mode).toBe('secure_storage');expect(settings.ok&&settings.result.profiles.every(p=>!p.configured)).toBe(true);
    const own=await app.evaluate(({BrowserWindow})=>{const w=BrowserWindow.getAllWindows()[0];w.setTitle('Orvia M19 synthetic icon verification');w.focus();const h=w.getNativeWindowHandle();return{handle:Number(h.length>=8?h.readBigUInt64LE():h.readUInt32LE()),pid:process.pid}});
    await page.screenshot({path:path.join(results,'packaged-welcome.png')});
    // Explorer图标可能异步加载；仅重试只读定位/裁切，不执行桌面业务动作。
    let taskbar:any;await expect.poll(async()=>{try{const result=await run('powershell.exe',['-NoProfile','-NonInteractive','-File',path.resolve('tests/e2e/m19-taskbar.ps1'),'-WindowHandle',String(own.handle),'-OwnerProcess',String(own.pid)],{windowsHide:true,timeout:15000});taskbar=JSON.parse(result.stdout);return true}catch(error:any){await writeFile(path.join(results,'taskbar-error.log'),String(error.stderr||error.message));return false}},{timeout:10000}).toBe(true);
    await writeFile(path.join(results,'packaged-visual.json'),JSON.stringify({scope:'真实定向安装EXE、空凭据、旧M14冻结后端；不是M15–M18安装功能验收',realModels:0,resource,taskbar},null,2));
  }finally{await app.close()}
});
