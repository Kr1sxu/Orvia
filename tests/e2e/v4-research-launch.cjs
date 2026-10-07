// 仅测试替换原生dialogs、合成DNS路由与云模型，stdio/权限/SQLite/提取/成品真实。
const path=require('node:path');const {dialog}=require('electron');const root=path.resolve(__dirname,'../..');
const {CredentialVault}=require(path.join(root,'apps/desktop/dist/main/credentials/index.js'));
CredentialVault.prototype.load=async function(){};CredentialVault.prototype.getSecrets=()=>({});
const runtime=require(path.join(root,'apps/desktop/dist/main/runtime.js'));const original=runtime.backendLaunch;
runtime.backendLaunch=(...args)=>{const launch=original(...args);return{...launch,args:['-I','-u','-X','utf8',path.join(root,'backend/tests/v4_research_fixture.py'),process.env.ORVIA_RESEARCH_PORT,process.env.ORVIA_RESEARCH_STATS]};};
dialog.showMessageBox=async()=>({response:process.env.ORVIA_RESEARCH_CONFIRM==='0'?0:1,checkboxChecked:false});
dialog.showSaveDialog=async(_owner,options)=>({canceled:process.env.ORVIA_RESEARCH_SAVE==='0',filePath:path.join(process.env.ORVIA_RESEARCH_OUTPUT,'合成调研简报.'+options.filters[0].extensions[0])});
require(path.join(root,'apps/desktop/dist/main/main.js'));
