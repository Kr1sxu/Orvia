import {dialog,type BrowserWindow} from 'electron';
import {graphId,graphGenerateInput,graphQueryInput,graphPreview} from './graph-contracts';
import type {BackendClient} from './backend';

/** 图谱发送许可绑定准确原文；本地查询和既有资料授权不批准本次云端抽取。 */
export function registerGraph({handle,serial,window,backend}:{
  handle:(channel:string,count:number,action:(...args:unknown[])=>Promise<unknown>)=>void;
  serial:<T>(action:()=>Promise<T>)=>Promise<T>;
  window:()=>BrowserWindow;backend:()=>BackendClient;
}){
  const reviewed=new Map<string,{revision:string;body:string}>();
  handle('orvia:graph-list',1,input=>backend().graph('list',graphId.parse(input)));
  handle('orvia:graph-query',1,input=>serial(()=>backend().graph('query',graphQueryInput.parse(input))));
  handle('orvia:graph-preview',1,input=>serial(async()=>{
    const request=graphId.parse(input),preview=graphPreview.parse(await backend().graph('preview',request));
    if(preview.id!==request.id)throw new Error('图谱发送预览与当前会话不对应。');
    // 预览只保存在有界内存；重连、撤权或删除会话时由主进程丢弃。
    reviewed.delete(request.id);
    while(reviewed.size>=8)reviewed.delete(reviewed.keys().next().value!);
    reviewed.set(request.id,{revision:preview.revision,body:JSON.stringify(preview)});
    return preview;
  }));
  handle('orvia:graph-generate',1,input=>serial(async()=>{
    const request=graphGenerateInput.parse(input),old=reviewed.get(request.id);
    if(!old||old.revision!==request.revision)throw new Error('请重新准备并审查当前会话的图谱发送预览。');
    const fresh=graphPreview.parse(await backend().graph('preview',{id:request.id}));
    if(fresh.id!==request.id||fresh.revision!==request.revision||JSON.stringify(fresh)!==old.body){reviewed.delete(request.id);throw new Error('会话、原文或发送范围已变化，请重新审查。');}
    // 开始原生决定即消耗许可，窗口异常或决定未知也不能重用旧按钮。
    reviewed.delete(request.id);
    const choice=await dialog.showMessageBox(window(),{type:'question',title:'批准此批实体关系抽取',
      message:'将以下准确原文发送给固定 Main 抽取实体和关系？',
      detail:old.body+'\n接收方：Main / deepseek-flash / https://api.deepseek.com。用途仅为实体关系抽取，可能产生供应商费用。取消不会调用模型；失败或结果未知不会自动重试。',
      buttons:['取消','批准此批发送'],defaultId:0,cancelId:0,noLink:true});
    if(choice.response!==1)return {cancelled:true};
    return {cancelled:false,result:await backend().graph('generate',request)};
  }));
  return {clear:()=>reviewed.clear()};
}
