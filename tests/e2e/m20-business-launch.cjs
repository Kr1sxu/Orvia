// 测试侧有限替身；真实主进程固定IPC、后端、文件审批和LPAC不替换。
const path=require('node:path'),fs=require('node:fs');
const {dialog}=require('electron');
const root=path.resolve(__dirname,'../..');
const runtime=require(path.join(root,'apps/desktop/dist/main/runtime.js'));
const original=runtime.backendLaunch;
runtime.backendLaunch=(...args)=>{const launch=original(...args);return{...launch,args:['-I','-u','-X','utf8',path.join(__dirname,'m20_business_backend.py')],env:{...launch.env,
  ORVIA_M20_COUNTER:process.env.ORVIA_M20_COUNTER,ORVIA_M20_MODEL_MODE:'normal',ORVIA_M20_BUSINESS_LOCAL:process.env.ORVIA_M20_BUSINESS_LOCAL,
  ORVIA_M20_BUSINESS_NETWORK_COUNT:process.env.ORVIA_M20_BUSINESS_NETWORK_COUNT,ORVIA_M20_BUSINESS_FIXTURE_PID:process.env.ORVIA_M20_BUSINESS_FIXTURE_PID}};};
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};
CredentialVault.prototype.getSecrets=()=>({main:'synthetic-m20-main',computer:'synthetic-m20-computer'});
const {BackendClient}=require(path.join(root,'apps/desktop/dist/main/backend.js'));
const originalAutomation=BackendClient.prototype.automation;
BackendClient.prototype.automation=async function(...args){try{return await originalAutomation.apply(this,args);}catch(error){
  fs.appendFileSync(path.join(path.dirname(process.env.ORVIA_M20_BUSINESS_DIALOGS),'ipc-errors.jsonl'),JSON.stringify({method:args[0],code:typeof error.code==='string'?error.code:'UNKNOWN'})+'\n');throw error;
}};
const originalChat=BackendClient.prototype.chat;
BackendClient.prototype.chat=async function(...args){try{return await originalChat.apply(this,args);}catch(error){
  if(args[0]==='chat.continue')fs.appendFileSync(path.join(path.dirname(process.env.ORVIA_M20_BUSINESS_DIALOGS),'ipc-errors.jsonl'),JSON.stringify({method:args[0],code:typeof error.code==='string'?error.code:'UNKNOWN'})+'\n');throw error;
}};
dialog.showOpenDialog=async(_window,options)=>({canceled:false,filePaths:[options.properties.includes('openDirectory')?process.env.ORVIA_M20_BUSINESS_PROJECT:process.env.ORVIA_M20_BUSINESS_SCRIPT]});
dialog.showSaveDialog=async()=>({canceled:false,filePath:process.env.ORVIA_M20_BUSINESS_EXPORT});
dialog.showMessageBox=async(_window,options)=>{const response=process.env.ORVIA_M20_BUSINESS_CONFIRM==='0'?0:1;
  // 只记录固定原生框标题与批准/拒绝事实，不记权限正文、源码或模型请求。
  fs.appendFileSync(process.env.ORVIA_M20_BUSINESS_DIALOGS,JSON.stringify({title:options.title,response})+'\n');return{response,checkboxChecked:false};};
require(path.join(root,'apps/desktop/dist/main/main.js'));
