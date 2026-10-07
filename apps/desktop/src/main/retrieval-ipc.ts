import {dialog,BrowserWindow} from 'electron';
import {retrievalId,retrievalQuery} from './retrieval-contracts';
import type {BackendClient} from './backend';

/** 固定工件下载与路径仅经原生选择/确认，renderer不能传URL、校验值或批准布尔值。 */
export function registerRetrieval({handle,serial,window,backend}:{
  handle:(channel:string,count:number,action:(...args:unknown[])=>Promise<unknown>)=>void;
  serial:<T>(action:()=>Promise<T>)=>Promise<T>;
  window:()=>BrowserWindow;backend:()=>BackendClient;
}){
  handle('orvia:retrieval-status',0,()=>backend().retrieval('status',{}));
  handle('orvia:retrieval-activate',0,()=>serial(()=>backend().retrieval('activate',{})));
  handle('orvia:retrieval-choose',0,()=>serial(async()=>{
    const chosen=await dialog.showOpenDialog(window(),{title:'选择已有官方 Qwen3 嵌入模型目录',properties:['openDirectory']});
    if(chosen.canceled||chosen.filePaths.length!==1)return {cancelled:true};
    return {cancelled:false,result:await backend().retrieval('prepare',{path:chosen.filePaths[0]})};
  }));
  handle('orvia:retrieval-download',0,()=>serial(async()=>{
    const info=await backend().retrieval('model',{});
    const choice=await dialog.showMessageBox(window(),{type:'question',title:'首次准备本地嵌入模型',
      message:'下载并核验此固定官方模型版本？',detail:JSON.stringify(info,null,2)+'\n约1.12 GiB，保存在应用私有模型目录；运行库另占空间。文本在本机处理，不替换三个角色模型。推理不会补下载。',
      buttons:['取消','下载此版本'],defaultId:0,cancelId:0,noLink:true});
    if(choice.response!==1)return {cancelled:true};
    return {cancelled:false,result:await backend().retrieval('download',{})};
  }));
  handle('orvia:retrieval-search',1,input=>serial(()=>backend().retrieval('search',retrievalQuery.parse(input))));
  handle('orvia:retrieval-rebuild',1,input=>serial(()=>backend().retrieval('rebuild',retrievalId.parse(input))));
  handle('orvia:retrieval-clear',1,input=>serial(()=>backend().retrieval('clear',retrievalId.parse(input))));
}
