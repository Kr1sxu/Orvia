// 原生确认仅在此测试启动器替换，生产preload无法选择后端执行器或批准来源。
const path=require('node:path');
const {dialog}=require('electron');
const root=path.resolve(__dirname,'../..');
const runtime=require(path.join(root,'apps/desktop/dist/main/runtime.js'));
const original=runtime.backendLaunch;
runtime.backendLaunch=(...args)=>{const launch=original(...args);return {...launch,args:['-I','-u','-X','utf8',path.join(__dirname,'m18_backend.py')],env:{...launch.env,
  ORVIA_M18_FIXTURE_PID:process.env.ORVIA_M18_FIXTURE_PID,ORVIA_M18_COUNTER:process.env.ORVIA_M18_COUNTER}};};
const {BackendClient}=require(path.join(root,'apps/desktop/dist/main/backend.js'));
const automate=BackendClient.prototype.automation;
BackendClient.prototype.automation=async function(...args){try{return await automate.apply(this,args);}catch(error){
  // 仅测试侧记录固定方法/code；不保存请求、响应、URL、文件内容或原始异常。
  require('node:fs').appendFileSync(path.join(path.dirname(process.env.ORVIA_M18_COUNTER),'ipc-errors.jsonl'),JSON.stringify({method:args[0],code:typeof error.code==='string'?error.code:'UNKNOWN'})+'\n');throw error;
}};
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};
CredentialVault.prototype.getSecrets=()=>({});
dialog.showOpenDialog=async(_window,options)=>({canceled:false,filePaths:[options.properties.includes('openDirectory')?process.env.ORVIA_M18_PROJECT:process.env.ORVIA_M18_SOURCE]});
dialog.showSaveDialog=async()=>({canceled:false,filePath:process.env.ORVIA_M18_EXPORT});
dialog.showMessageBox=async(_window,options)=>({response:process.env.ORVIA_M18_CANCEL==='1'&&options.title!=='明确选择一个普通权限应用'?0:1,checkboxChecked:false});
require(path.join(root,'apps/desktop/dist/main/main.js'));
