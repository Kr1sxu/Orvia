// 仅合成原生选择和确认；真实产品Shell/SQLite/进程运行器保持原样，不读取Key。
const path=require('node:path');const {dialog}=require('electron');const root=path.resolve(__dirname,'../..');
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};CredentialVault.prototype.getSecrets=()=>({});
dialog.showOpenDialog=async(_owner,options)=>({canceled:false,filePaths:[options.properties?.includes('openDirectory')?process.env.ORVIA_SHELL_CWD:process.env.ORVIA_SHELL_INPUT]});
dialog.showSaveDialog=async()=>({canceled:false,filePath:process.env.ORVIA_SHELL_SAVE});
dialog.showMessageBox=async()=>({response:process.env.ORVIA_SHELL_CONFIRM==='0'?0:1,checkboxChecked:false});
require(path.join(root,'apps/desktop/dist/main/main.js'));
