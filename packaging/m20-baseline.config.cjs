const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const asar=require('@electron/asar');
const base=require('../electron-builder.config.cjs');
const root=path.resolve(__dirname,'..');
const source=path.join(root,'artifacts/test-results/M14/release/win-unpacked/resources');
const result=path.join(root,'artifacts/test-results/M20/baseline');
const input=path.join(result,'app');
const original=path.join(source,'app.asar');
const record=path.join(result,'source.json');

function plain(target){
  // 仅在已批准的本仓库产物中准备基线输入；所有已存在祖先均拒绝重解析点。
  for(let current=target;current;current=path.dirname(current)){
    if(fs.existsSync(current)&&fs.lstatSync(current).isSymbolicLink())throw new Error('基线资源含重解析点');
    if(path.dirname(current)===current)break;
  }
}
function digest(file){return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');}
function inventory(directory){
  const pending=[directory],files={};let entries=0,total=0;
  while(pending.length){
    for(const entry of fs.readdirSync(pending.pop(),{withFileTypes:true})){
      const target=path.join(entry.parentPath,entry.name);plain(target);
      if(++entries>5000)throw new Error('基线输入超过目录项预算');
      const info=fs.lstatSync(target);
      if(info.isSymbolicLink())throw new Error('基线输入含链接');
      if(info.isDirectory()){pending.push(target);continue;}
      if(!info.isFile()||info.nlink!==1||(total+=info.size)>128*1024*1024)throw new Error('基线输入文件身份/体积不符');
      files[path.relative(directory,target).split(path.sep).join('/')]=digest(target);
    }
  }
  return Object.fromEntries(Object.entries(files).sort(([a],[b])=>a.localeCompare(b)));
}
plain(source);plain(result);plain(original);
const metadata=JSON.parse(asar.extractFile(original,'package.json').toString('utf8'));
if(metadata.name!=='@orvia/desktop'||metadata.version!=='0.2.0-rc.1'||metadata.main!=='dist/main/main.js')throw new Error('历史ASAR不是已记录M14基线');
const identity={module:'M20',scope:'旧M14资源只读再封装；不宣称具有M15–M20功能',version:metadata.version,asarSha256:digest(original)};
if(fs.existsSync(input)){
  // 已有输入必须仍对应同一历史来源，不覆盖可能被人工修改的验收现场。
  plain(input);plain(record);
  const saved=JSON.parse(fs.readFileSync(record,'utf8'));
  if(JSON.stringify(saved)!==JSON.stringify({...identity,files:inventory(input)}))throw new Error('基线来源/输入记录不一致');
}else{
  for(const entry of asar.listPackage(original)){
    const relative=entry.replaceAll('\\','/').replace(/^\/+/,''),info=asar.statFile(original,relative.split('/').join(path.sep),false);
    if(info.link||relative.includes(':')||relative.split('/').includes('..')||path.isAbsolute(relative))throw new Error('历史ASAR含不安全路径');
  }
  fs.mkdirSync(result,{recursive:true});
  asar.extractAll(original,input);
  fs.writeFileSync(record,JSON.stringify({...identity,files:inventory(input)},null,2),'utf8');
}

// 以独立测试AppId封装0.2基线，随后同身份升级0.3；旧安装器/ASAR/资源均不修改。
module.exports={...base,appId:'cn.orvia.m20.fulltest',productName:'Orvia M20 Full Test',
  extraMetadata:{version:'0.2.0-rc.1',orviaAppId:'cn.orvia.m20.fulltest'},
  directories:{...base.directories,app:input,output:path.join(result,'release')},
  files:['dist/main/**/*','dist/renderer/**/*','node_modules/**/*','package.json'],
  extraResources:[
    {from:path.join(source,'backend'),to:'backend',filter:['**/*']},
    {from:path.join(source,'chromium'),to:'chromium',filter:['**/*']},
    {from:path.join(source,'runtime-manifest.json'),to:'runtime-manifest.json'},
    {from:path.join(source,'LICENSE.txt'),to:'LICENSE.txt'},
  ],
  artifactName:'Orvia-M20-baseline-test-${version}-win-${arch}-setup.${ext}',
  nsis:{...base.nsis,license:path.join(source,'LICENSE.txt'),shortcutName:'Orvia M20 Full Test'},
};
