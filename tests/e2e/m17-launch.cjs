// 测试启动器仅替换 Computer 响应和原生确认，项目与清理动作仍由真实后端执行。
const path=require('node:path');
const {dialog}=require('electron');
const root=path.resolve(__dirname,'../..');
const runtime=require(path.join(root,'apps/desktop/dist/main/runtime.js'));
const original=runtime.backendLaunch;
runtime.backendLaunch=(...args)=>{const value=original(...args);return {...value,args:['-I','-u','-X','utf8',path.join(__dirname,'m17_backend.py')],env:{...value.env,ORVIA_M17_LOCAL_BASE:process.env.ORVIA_M17_LOCAL_BASE}}};
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};
CredentialVault.prototype.getSecrets=()=>({});
dialog.showOpenDialog=async()=>({canceled:false,filePaths:[process.env.ORVIA_M17_PROJECT]});
dialog.showMessageBox=async()=>({response:process.env.ORVIA_M17_CANCEL==='1'?0:1,checkboxChecked:false});
require(path.join(root,'apps/desktop/dist/main/main.js'));
