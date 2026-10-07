// 合成测试启动器；产品没有环境变量批准、模型切换或任选后端入口。
const path=require('node:path');
const {dialog}=require('electron');
const root=path.resolve(__dirname,'../..');
const runtime=require(path.join(root,'apps/desktop/dist/main/runtime.js'));
const original=runtime.backendLaunch;
runtime.backendLaunch=(...args)=>{const launch=original(...args);return {...launch,args:['-I','-u','-X','utf8',path.join(__dirname,'v4-rewrite-backend.py')],env:{...launch.env,ORVIA_M20_COUNTER:process.env.ORVIA_M20_COUNTER}};};
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};
CredentialVault.prototype.getSecrets=()=>({main:'synthetic-rewrite-main'});
dialog.showOpenDialog=async(_owner,options)=>{
  if(options.properties.includes('openDirectory'))throw new Error('本轮合成只读会话工作流禁止选择文件夹');
  return {canceled:false,filePaths:JSON.parse(process.env.ORVIA_M20_INPUTS||'[]')};
};
dialog.showMessageBox=async()=>({response:process.env.ORVIA_M20_CONFIRM==='0'?0:1,checkboxChecked:true});
require(path.join(root,'apps/desktop/dist/main/main.js'));
