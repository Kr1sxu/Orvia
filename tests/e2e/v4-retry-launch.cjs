// 仅测试入口复用010固定DNS/真实TCP与固定Main替身，凭据为空；不替换重试或目标核验。
const path=require('node:path');const {dialog}=require('electron');const root=path.resolve(__dirname,'../..');
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};CredentialVault.prototype.getSecrets=()=>({});
const runtime=require(path.join(root,'apps/desktop/dist/main/runtime.js'));const original=runtime.backendLaunch;
runtime.backendLaunch=(...args)=>{const launch=original(...args);return{...launch,args:['-I','-u','-X','utf8',path.join(root,'backend/tests/v4_retry_fixture.py'),process.env.ORVIA_RETRY_PORT,process.env.ORVIA_RETRY_STATS]};};
dialog.showMessageBox=async()=>({response:1,checkboxChecked:false});
require(path.join(root,'apps/desktop/dist/main/main.js'));
