// 原生窗口候选实验与产品完全分离；不加载凭据、后端、外部页面或用户资料。
const {app,BrowserWindow,screen,session}=require('electron');
const path=require('node:path');
const fs=require('node:fs/promises');
const {execFileSync}=require('node:child_process');
const results=path.resolve('artifacts/test-results/M19/window-probe');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));

app.whenReady().then(async()=>{
  await fs.mkdir(results,{recursive:true});
  session.defaultSession.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false));
  session.defaultSession.webRequest.onBeforeRequest({urls:['http://*/*','https://*/*','ws://*/*','wss://*/*']},(_details,callback)=>callback({cancel:true}));
  const display=screen.getPrimaryDisplay();const work=display.workArea;
  // 自有合成背景覆盖候选窗口截图周边，避免保存个人桌面内容。
  const backdrop=new BrowserWindow({x:work.x,y:work.y,width:work.width,height:work.height,frame:false,skipTaskbar:true,backgroundColor:'#c8d8e5',webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false}});
  await backdrop.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent('<style>body{margin:0;background:repeating-conic-gradient(#c8d8e5 0 25%,#c2d2df 0 50%) 0/32px 32px}</style>'));
  backdrop.showInactive();backdrop.setAlwaysOnTop(true);
  const candidate=new BrowserWindow({x:work.x+70,y:work.y+65,width:Math.min(940,work.width-140),height:Math.min(690,work.height-130),minWidth:760,minHeight:560,title:'Orvia M19 候选窗口探针',backgroundColor:'#f6f7f8',titleBarStyle:'hidden',titleBarOverlay:{color:'#f6f7f8',symbolColor:'#22272e',height:42},roundedCorners:true,thickFrame:true,webPreferences:{sandbox:true,contextIsolation:true,nodeIntegration:false}});
  await candidate.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent('<style>body{margin:0;font:15px/1.8 Segoe UI,Microsoft YaHei,sans-serif;color:#22272e;background:#f6f7f8}header{height:42px;app-region:drag;padding:0 24px;display:flex;align-items:center}main{padding:45px}h1{font-size:26px}section{padding:24px;background:#fff;border:1px solid #e0e5e9;border-radius:14px;margin-top:24px}</style><header>序航 Orvia · M19 独立窗口探针</header><main><h1>原生圆角与标题栏候选</h1><p>此窗口仅用于验证真实外轮廓和系统状态。<br>没有加载产品、凭据、后端或模型。</p><section>Windows 11 系统圆角 / 原生最小化、最大化、关闭<br>保留 thickFrame，未使用透明窗口或 CSS 外轮廓裁切。</section></main>'));
  candidate.setAlwaysOnTop(true);candidate.show();candidate.focus();await delay(500);
  const states=[];
  function capture(name){
    const native=candidate.getNativeWindowHandle();const hwnd=Number(native.length>=8?native.readBigUInt64LE():native.readUInt32LE());
    const output=execFileSync(path.join(process.env.SystemRoot,'System32/WindowsPowerShell/v1.0/powershell.exe'),['-NoProfile','-NonInteractive','-File',path.resolve('tests/e2e/m19-desktop-capture.ps1'),'-WindowHandle',String(hwnd),'-Output',path.join(results,name+'.png'),'-Padding',candidate.isMaximized()?'0':'10'],{windowsHide:true,encoding:'utf8',timeout:20000});
    states.push({name,bounds:candidate.getBounds(),maximized:candidate.isMaximized(),minimized:candidate.isMinimized(),fullscreen:candidate.isFullScreen(),native:JSON.parse(output)});
  }
  try{
    capture('ordinary');
    candidate.maximize();await delay(500);capture('maximized');
    candidate.unmaximize();await delay(350);candidate.minimize();await delay(250);
    states.push({name:'minimized',minimized:candidate.isMinimized()});
    candidate.restore();await delay(350);capture('restored');
    candidate.setSize(760,560);await delay(350);capture('minimum');
    await fs.writeFile(path.join(results,'window-report.json'),JSON.stringify({scope:'独立原生候选，不是产品验收；没有测试用户拖动/双击/贴靠',realModels:0,electron:process.versions.electron,display:{scaleFactor:display.scaleFactor,bounds:display.bounds,workArea:work},states},null,2));
    console.log(JSON.stringify({result:'passed',states:states.length,scope:'独立原生窗口候选'}));
  }finally{candidate.destroy();backdrop.destroy();app.quit()}
}).catch(()=>{console.error('M19原生窗口候选探针失败');app.exit(1)});
