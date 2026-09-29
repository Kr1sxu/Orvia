// 测试启动器仅替换模型与系统对话框；成品仍由真实 Python/文件网关生成。
const path=require('node:path');
const {dialog}=require('electron');
const root=path.resolve(__dirname,'../..');
const runtime=require(path.join(root,'apps/desktop/dist/main/runtime.js'));
const original=runtime.backendLaunch;
runtime.backendLaunch=(...args)=>({...original(...args),args:['-I','-u','-X','utf8',path.join(__dirname,'m15_backend.py')]});
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};
CredentialVault.prototype.getSecrets=()=>({});
dialog.showOpenDialog=async()=>({canceled:false,filePaths:[process.env.ORVIA_M16_INPUT]});
dialog.showMessageBox=async()=>({response:1,checkboxChecked:false});
dialog.showSaveDialog=async(_window,options)=>({canceled:process.env.ORVIA_M16_CANCEL==='1',filePath:path.join(process.env.ORVIA_M16_OUTPUT_DIR,path.basename(options.defaultPath))});
require(path.join(root,'apps/desktop/dist/main/main.js'));
