// 只替换准确原生选择/确认，实际进程权限、SQLite和固定协议均为产品实现。
const path=require('node:path');const {dialog}=require('electron');const root=path.resolve(__dirname,'../..');
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};CredentialVault.prototype.getSecrets=()=>({});
dialog.showOpenDialog=async(_owner,options)=>({canceled:false,filePaths:[options.properties?.includes('openDirectory')?process.env.ORVIA_PROCESS_CWD:process.env.ORVIA_PROCESS_EXE]});
dialog.showMessageBox=async()=>({response:process.env.ORVIA_PROCESS_CONFIRM==='0'?0:1,checkboxChecked:false});
require(path.join(root,'apps/desktop/dist/main/main.js'));
