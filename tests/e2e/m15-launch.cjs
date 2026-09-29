// 测试启动器模拟系统选择框与原生发送确认；产品无自动正文上传入口。
const path=require('node:path');
const {dialog}=require('electron');
const root=path.resolve(__dirname,'../..');
const runtime=require(path.join(root,'apps/desktop/dist/main/runtime.js'));
const original=runtime.backendLaunch;
runtime.backendLaunch=(...args)=>({...original(...args),args:['-I','-u','-X','utf8',path.join(__dirname,'m15_backend.py')]});
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};
CredentialVault.prototype.getSecrets=()=>({});
dialog.showOpenDialog=async()=>({canceled:false,filePaths:[process.env.ORVIA_M15_INPUT]});
dialog.showMessageBox=async()=>({response:process.env.ORVIA_M15_CONFIRM==='0'?0:1,checkboxChecked:false});
require(path.join(root,'apps/desktop/dist/main/main.js'));
