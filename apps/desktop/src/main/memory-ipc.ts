import {dialog,type BrowserWindow} from 'electron';
import {memoryId,memoryContextInput,memoryGenerateInput,memorySearchInput,memoryCorrectInput,memoryForgetInput,memoryPreview} from './memory-contracts';
import type {BackendClient} from './backend';

/** 发送许可绑定完整准确预览；记忆来源和已有文件授权不会自动批准本次云端整理。 */
export function registerMemory({handle,serial,window,backend}:{
  handle:(channel:string,count:number,action:(...args:unknown[])=>Promise<unknown>)=>void;
  serial:<T>(action:()=>Promise<T>)=>Promise<T>;
  window:()=>BrowserWindow;backend:()=>BackendClient;
}){
  const reviewed=new Map<string,{revision:string;body:string}>();
  handle('orvia:memory-list',1,input=>serial(()=>backend().memory('list',memoryId.parse(input))));
  handle('orvia:memory-context',1,input=>serial(()=>backend().memory('context',memoryContextInput.parse(input))));
  handle('orvia:memory-search',1,input=>serial(()=>backend().memory('search',memorySearchInput.parse(input))));
  handle('orvia:memory-preview',1,input=>serial(async()=>{
    const request=memoryId.parse(input);
    const preview=memoryPreview.parse(await backend().memory('preview',request));
    if(preview.id!==request.id)throw new Error('发送预览与当前会话不对应。');
    // 内存中的预览有界，关闭/重连即可丢弃；不把正文写进审批日志。
    reviewed.delete(request.id);
    while(reviewed.size>=8)reviewed.delete(reviewed.keys().next().value!);
    reviewed.set(request.id,{revision:preview.revision,body:JSON.stringify(preview)});
    return preview;
  }));
  handle('orvia:memory-generate',1,input=>serial(async()=>{
    const request=memoryGenerateInput.parse(input),old=reviewed.get(request.id);
    if(!old||old.revision!==request.revision)throw new Error('请重新准备并审查当前会话的发送预览。');
    const fresh=memoryPreview.parse(await backend().memory('preview',{id:request.id}));
    if(fresh.id!==request.id||fresh.revision!==request.revision||JSON.stringify(fresh)!==old.body){reviewed.delete(request.id);throw new Error('会话、来源或发送范围已变化，请重新审查。');}
    // 原生窗口展示完整包，准确正文已在界面预览；只允许固定Main单次请求，无自动重试。
    const choice=await dialog.showMessageBox(window(),{type:'question',title:'批准此批摘要与记忆整理',
      message:'将以下准确内容发送给固定 Main 整理摘要与记忆？',
      detail:old.body+'\n接收方：Main / deepseek-flash / https://api.deepseek.com。用途仅为本批摘要与记忆整理，可能产生供应商费用。取消不会调用模型；失败或结果未知不会自动重试。',
      buttons:['取消','批准此批发送'],defaultId:0,cancelId:0,noLink:true});
    // 每次决定都消耗预览；断线后不能凭旧按钮重发，必须重新审查完整正文。
    reviewed.delete(request.id);
    if(choice.response!==1)return {cancelled:true};
    return {cancelled:false,result:await backend().memory('generate',request)};
  }));
  handle('orvia:memory-correct',1,input=>serial(async()=>{
    const request=memoryCorrectInput.parse(input);reviewed.clear();
    return backend().memory('correct',request);
  }));
  handle('orvia:memory-forget',1,input=>serial(async()=>{
    const request=memoryForgetInput.parse(input);
    const choice=await dialog.showMessageBox(window(),{type:'question',title:'忘记这条派生记忆',
      message:'删除所选派生记忆并停止将其用于上下文？',detail:'原会话正文、原文件和导出成品保留。忘记不表示删除供应商已接收的内容，也不承诺磁盘取证擦除。',
      buttons:['取消','忘记此条'],defaultId:0,cancelId:0,noLink:true});
    if(choice.response!==1)return {cancelled:true};
    reviewed.clear();
    return {cancelled:false,result:await backend().memory('forget',request)};
  }));
  return {clear:()=>reviewed.clear()};
}
