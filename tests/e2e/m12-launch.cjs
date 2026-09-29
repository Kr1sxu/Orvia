// 只在测试入口替换网络进程和凭据；生产代码没有网页 mock 或自动授权开关。
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const runtime=require(path.join(root,'apps/desktop/dist/main/runtime.js'));
const original=runtime.backendLaunch;
runtime.backendLaunch=(...args)=>({...original(...args),args:['-I','-u','-X','utf8',path.join(__dirname,'m12_backend.py')]});
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};
CredentialVault.prototype.getSecrets=()=>process.env.ORVIA_M12_NO_SEARCH==='1'?{}:{tavily:'synthetic-only'};
require(path.join(root,'apps/desktop/dist/main/main.js'));
