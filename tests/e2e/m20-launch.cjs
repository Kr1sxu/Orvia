// 仅测试启动器替换合成凭据、系统选择/确认；产品没有环境变量批准或任选后端入口。
const path=require('node:path');
const {dialog}=require('electron');
const root=path.resolve(__dirname,'../..');
const runtime=require(path.join(root,'apps/desktop/dist/main/runtime.js'));
const original=runtime.backendLaunch;
runtime.backendLaunch=(...args)=>{const launch=original(...args);return{...launch,args:['-I','-u','-X','utf8',path.join(__dirname,'m20_backend.py')],env:{...launch.env,
  ORVIA_M20_COUNTER:process.env.ORVIA_M20_COUNTER,ORVIA_M20_FIXTURE_PID:process.env.ORVIA_M20_FIXTURE_PID,ORVIA_M20_MODEL_MODE:process.env.ORVIA_M20_MODEL_MODE}};};
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};
CredentialVault.prototype.getSecrets=()=>process.env.ORVIA_M20_MODEL_MODE==='missing'?{}:{main:'synthetic-m20-main',computer:'synthetic-m20-computer'};
dialog.showOpenDialog=async(_window,options)=>({canceled:process.env.ORVIA_M20_SELECT_CANCEL==='1',filePaths:options.properties.includes('openDirectory')?[process.env.ORVIA_M20_DIRECTORY]:JSON.parse(process.env.ORVIA_M20_INPUTS||'[]')});
dialog.showSaveDialog=async()=>({canceled:process.env.ORVIA_M20_SAVE_CANCEL==='1',filePath:process.env.ORVIA_M20_EXPORT});
dialog.showMessageBox=async()=>({response:process.env.ORVIA_M20_CONFIRM==='0'?0:1,checkboxChecked:false});
require(path.join(root,'apps/desktop/dist/main/main.js'));
