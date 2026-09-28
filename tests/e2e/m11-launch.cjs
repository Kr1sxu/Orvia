// 仅测试入口：合成模型与空凭据，记录本应用的子进程供生命周期故障注入。
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const runtime = require(path.join(root, 'apps/desktop/dist/main/runtime.js'));
const original = runtime.backendLaunch;
runtime.backendLaunch = (...args) => ({...original(...args), args: ['-I', '-u', '-X', 'utf8', path.join(__dirname, 'm11_backend.py')]});
const cp = require('node:child_process');
const spawn = cp.spawn;
cp.spawn = (...args) => {
  const child = spawn(...args);
  if (args[1]?.includes(path.join(__dirname, 'm11_backend.py'))) global.__m11OwnedBackend = child;
  return child;
};
const {CredentialVault} = require(path.join(root, 'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load = async function () {};
CredentialVault.prototype.getSecrets = () => ({});
require(path.join(root, 'apps/desktop/dist/main/main.js'));
