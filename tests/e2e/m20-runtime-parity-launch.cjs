// M20真实开发运行时：仅把凭据仓库置空，保留产品真实后端选择、权限链和浏览器网络。
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};
CredentialVault.prototype.getSecrets=()=>({});
require(path.join(root,'apps/desktop/dist/main/main.js'));
