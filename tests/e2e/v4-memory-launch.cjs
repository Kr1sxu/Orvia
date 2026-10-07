// 仅测试启动器：产品原生许可不读取环境变量，模型全部使用合成HTTP替身。
const path=require('node:path');
const {dialog}=require('electron');
const root=path.resolve(__dirname,'../..');
const runtime=require(path.join(root,'apps/desktop/dist/main/runtime.js'));
const original=runtime.backendLaunch;
runtime.backendLaunch=(...args)=>{const launch=original(...args);return {...launch,args:['-I','-u','-X','utf8',path.join(__dirname,'v4-memory-backend.py')],env:{...launch.env,ORVIA_M20_COUNTER:process.env.ORVIA_M20_COUNTER}};};
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};
CredentialVault.prototype.getSecrets=()=>({main:'synthetic-memory-main'});
dialog.showMessageBox=async()=>({response:process.env.ORVIA_M20_CONFIRM==='0'?0:1,checkboxChecked:false});
require(path.join(root,'apps/desktop/dist/main/main.js'));
