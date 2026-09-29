// 仅测试启动器模拟原生选择器；产品没有环境自动授权入口，解析/SQLite/导出均为真实。
const path=require('node:path');
const {dialog}=require('electron');
const root=path.resolve(__dirname,'../..');
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};
CredentialVault.prototype.getSecrets=()=>({});
dialog.showOpenDialog=async()=>({canceled:false,filePaths:[process.env.ORVIA_M13_INPUT]});
dialog.showSaveDialog=async()=>({canceled:false,filePath:process.env.ORVIA_M13_OUTPUT});
require(path.join(root,'apps/desktop/dist/main/main.js'));
