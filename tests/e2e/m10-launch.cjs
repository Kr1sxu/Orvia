// 测试启动器在加载产品主进程前替换模型进程入口和凭据来源；产品不存在测试后门。
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const runtime = require(path.join(root, 'apps/desktop/dist/main/runtime.js'));
const original = runtime.backendLaunch;
runtime.backendLaunch = (...args) => {
  const launch = original(...args);
  return {...launch, args: ['-I', '-u', '-X', 'utf8', path.join(__dirname, 'm10_backend.py')]};
};
const {CredentialVault} = require(path.join(root, 'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load = async function () {};
CredentialVault.prototype.getSecrets = () => ({});
require(path.join(root, 'apps/desktop/dist/main/main.js'));
