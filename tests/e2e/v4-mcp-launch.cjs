// V4-007：仅原生选择/确认替身；产品后端与真实stdio服务不替换，不读取任何真实Key。
const path=require('node:path');const {dialog}=require('electron');
const root=path.resolve(__dirname,'../..');
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};CredentialVault.prototype.getSecrets=()=>({});
dialog.showOpenDialog=async(_owner,options)=>{
  if(!options.filters?.some(filter=>filter.extensions.includes('json')))throw new Error('本测试仅允许显式合成配置文件');
  return{canceled:false,filePaths:[process.env.ORVIA_MCP_CONFIG]};
};
dialog.showMessageBox=async()=>({response:process.env.ORVIA_MCP_CONFIRM==='0'?0:1,checkboxChecked:false});
require(path.join(root,'apps/desktop/dist/main/main.js'));
