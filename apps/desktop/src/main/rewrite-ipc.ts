import {dialog,type BrowserWindow} from 'electron';
import {rewriteId,rewritePreviewInput,rewriteGenerateInput,rewriteSearchInput,rewritePreview} from './rewrite-contracts';
import type {BackendClient} from './backend';

/** 改写只影响检索表达；一次外发许可绑定原问题、选定记忆和当前有效资料范围。 */
export function registerRewrite({handle,serial,window,backend}:{
  handle:(channel:string,count:number,action:(...args:unknown[])=>Promise<unknown>)=>void;
  serial:<T>(action:()=>Promise<T>)=>Promise<T>;
  window:()=>BrowserWindow;backend:()=>BackendClient;
}){
  const reviewed=new Map<string,{revision:string;body:string;request:ReturnType<typeof rewritePreviewInput.parse>}>();
  handle('orvia:rewrite-history',1,input=>backend().rewrite('history',rewriteId.parse(input)));
  handle('orvia:rewrite-search',1,input=>serial(()=>backend().rewrite('search',rewriteSearchInput.parse(input))));
  handle('orvia:rewrite-preview',1,input=>serial(async()=>{
    const request=rewritePreviewInput.parse(input),preview=rewritePreview.parse(await backend().rewrite('preview',request));
    if(preview.id!==request.id||preview.input.original!==request.query||preview.input.memories.length!==(request.memory_ids??[]).length||preview.input.memories.some(item=>!request.memory_ids?.includes(item.id)))throw new Error('改写预览与当前问题或明确选中的记忆不对应。');
    reviewed.delete(request.id);
    while(reviewed.size>=8)reviewed.delete(reviewed.keys().next().value!);
    if(preview.status==='ready')reviewed.set(request.id,{revision:preview.revision,body:JSON.stringify(preview),request});
    return preview;
  }));
  handle('orvia:rewrite-generate',1,input=>serial(async()=>{
    const request=rewriteGenerateInput.parse(input),old=reviewed.get(request.id);
    if(!old||old.revision!==request.revision)throw new Error('请重新准备并完整审查此问题的改写预览。');
    const fresh=rewritePreview.parse(await backend().rewrite('preview',old.request));
    if(fresh.id!==request.id||fresh.revision!==request.revision||JSON.stringify(fresh)!==old.body){reviewed.delete(request.id);throw new Error('问题、选中记忆或当前资料已变化，请重新审查。');}
    // 弹窗开始即消耗许可；取消、窗口异常、失联或未知结果均不自动重新发送。
    reviewed.delete(request.id);
    const choice=await dialog.showMessageBox(window(),{type:'question',title:'批准此批查询改写',message:'将以下准确内容发送给固定 Main 生成检索候选？',
      detail:old.body+'\n接收方：Main / deepseek-flash / https://api.deepseek.com。用途仅为检索查询改写，可能产生供应商费用。原问题始终保留；候选不授予文件或执行权限。取消不会调用模型；失败或结果未知不会自动重试。',
      buttons:['取消','批准此批发送'],defaultId:0,cancelId:0,noLink:true});
    if(choice.response!==1)return {cancelled:true};
    return {cancelled:false,result:await backend().rewrite('generate',request)};
  }));
  return {clear:()=>reviewed.clear()};
}
