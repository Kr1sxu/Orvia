// 显式真实验收的独立进程，只将固定Main开发Key存入M20隔离profile的DPAPI密文。
// 不传Key到argv/env，不打印原文、密文、原请求或响应；产品没有此种测试入口。
const fs=require('node:fs'),path=require('node:path');
const {app,safeStorage}=require('electron');
const root=path.resolve(__dirname,'../..'),resultRoot=path.join(root,'artifacts/test-results/M20');
const target=path.resolve(process.argv[2]||'');
if(process.env.ORVIA_M20_LIVE!=='1'||!target.startsWith(resultRoot+path.sep))throw Error('LIVE_TEST_SCOPE_REQUIRED');
for(let current=target;current;current=path.dirname(current)){if(fs.existsSync(current)&&fs.lstatSync(current).isSymbolicLink())throw Error('TEST_PROFILE_REPARSE');if(path.dirname(current)===current)break;}
app.setPath('userData',target);
app.whenReady().then(()=>{
  if(!safeStorage.isEncryptionAvailable())throw Error('SAFE_STORAGE_UNAVAILABLE');
  const filename=path.join(target,'credentials.enc.json');
  if(fs.existsSync(filename))throw Error('TEST_PROFILE_ALREADY_SEEDED');
  const lines=fs.readFileSync(path.join(root,'.env.local'),'utf8').replace(/^\uFEFF/,'').split(/\r?\n/);
  const line=lines.find(value=>/^\s*(?:export\s+)?DEEPSEEK_API_KEY\s*=/.test(value));
  let value=line?.slice(line.indexOf('=')+1).trim();
  if(value?.startsWith('"')||value?.startsWith("'")){const matched=value.match(/^(["'])(.*?)\1\s*(?:#.*)?$/);value=matched?.[2];}else value=value?.replace(/\s+#.*$/,'').trim();
  if(!value||value.length>4096||/[\r\n]/.test(value))throw Error('MAIN_KEY_MISSING');
  fs.mkdirSync(target,{recursive:true});
  fs.writeFileSync(filename,JSON.stringify({main:safeStorage.encryptString(value).toString('base64')}),{flag:'wx'});
  console.log(JSON.stringify({seeded:true,encrypted:true,role:'main',profileIsolated:true}));
  app.quit();
}).catch(()=>{console.error('M20_LIVE_CREDENTIAL_PREPARATION_FAILED');app.exit(2);});
