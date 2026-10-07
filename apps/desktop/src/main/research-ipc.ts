import {dialog,type BrowserWindow} from 'electron';
import {researchId,researchOperation,researchCreateInput,researchPreviewInput,researchGenerateInput,researchTask,researchPacket} from './research-contracts';
import type {ResearchTask} from './research-contracts';
import type {BackendClient} from './backend';

/** 公共网页采集与Main云端发送分别原生批准；批摘要不是最终引用原文或新权限来源。 */
export function registerResearch({handle,serial,window,backend}:{
  handle:(channel:string,count:number,action:(...args:unknown[])=>Promise<unknown>)=>void;
  serial:<T>(action:()=>Promise<T>)=>Promise<T>;
  window:()=>BrowserWindow;backend:()=>BackendClient;
}){
  const plans=new Map<string,ResearchTask>();
  const packets=new Map<string,{request:ReturnType<typeof researchPreviewInput.parse>;revision:string;body:string}>();
  let generation=0;
  const cancelled=new Set<string>();
  const key=(op:string,stage:string)=>op+':'+stage;
  const clearOperation=(op:string)=>{plans.delete(op);packets.delete(key(op,'batch'));packets.delete(key(op,'final'));};
  const approve=async(title:string,message:string,detail:string)=>(await dialog.showMessageBox(window(),{type:'question',title,message,detail,buttons:['取消','批准此批'],defaultId:0,cancelId:0,noLink:true})).response===1;
  handle('orvia:research-status',1,input=>backend().research('status',researchOperation.parse(input)));
  handle('orvia:research-history',1,input=>backend().research('history',researchId.parse(input)));
  handle('orvia:research-review-collect',1,input=>serial(async()=>{
    // 历史或Skill只保存范围事实；重新明确核对不恢复旧批准，随后仍必须新原生确认。
    const request=researchOperation.parse(input),task=researchTask.parse(await backend().research('status',request));
    if(task.id!==request.id||task.operation_id!==request.operation_id||task.state!=='planned')throw new Error('仅尚未尝试的准确计划可重新准备采集。');
    clearOperation(request.operation_id);cancelled.delete(request.operation_id);
    while(plans.size>=20)plans.delete(plans.keys().next().value!);plans.set(task.operation_id,task);return task;
  }));
  handle('orvia:research-cancel',1,input=>{const request=researchOperation.parse(input);generation++;clearOperation(request.operation_id);cancelled.add(request.operation_id);while(cancelled.size>20)cancelled.delete(cancelled.values().next().value!);return backend().research('cancel',request);});
  handle('orvia:research-create',1,input=>serial(async()=>{
    const request=researchCreateInput.parse(input),task=researchTask.parse(await backend().research('create',request));
    // 创建只保存计划，URL/站点可被安全解析器规范化；真正外发以随后完整原生审查的事实计划为准。
    if(task.id!==request.id||task.state!=='planned'||task.question!==request.question.trim()||JSON.stringify(task.queries)!==JSON.stringify(request.queries)||JSON.stringify(task.sources)!==JSON.stringify(request.sources))throw new Error('调研计划与准确问题、来源或范围不对应。');
    while(plans.size>=20)plans.delete(plans.keys().next().value!);plans.set(task.operation_id,task);return task;
  }));
  handle('orvia:research-collect',1,input=>serial(async()=>{
    const request=researchOperation.parse(input),old=plans.get(request.operation_id);if(!old||old.id!==request.id)throw new Error('请重新创建并核对准确调研采集计划。');
    plans.delete(request.operation_id);
    const started=generation;
    const fresh=researchTask.parse(await backend().research('status',request));if(JSON.stringify(fresh)!==JSON.stringify(old)){clearOperation(request.operation_id);throw new Error('调研范围或来源已变化，请重新核对采集计划。');}
    if(!await approve('批准此调研资料采集','读取以下准确公共网页与执行搜索？',JSON.stringify(fresh,null,2)+'\n最多10个公共网页、两轮检索、120秒总采集预算。搜索接收方为Tavily，仅发送所示明确queries，每轮最多五个结果；站点约束仅在本机过滤候选与最终URL，不发送给搜索服务，可能产生服务费用；缺凭据时明确不可用，显式URL仍可只读访问。网页与搜索结果是外部数据，不授权登录、下载或写操作。本步骤不调用Main；批摘要和最终综合各需准确正文另批。'))return{cancelled:true};
    if(started!==generation||cancelled.has(request.operation_id))throw new Error('采集许可已因取消或重连撤销，请核对任务事实。');
    const result=researchTask.parse(await backend().research('collect',request));if(result.id!==request.id||result.operation_id!==request.operation_id)throw new Error('返回采集事实与准确会话和任务不对应。');
    return{cancelled:false,result};
  }));
  handle('orvia:research-preview',1,input=>serial(async()=>{
    const request=researchPreviewInput.parse(input);packets.delete(key(request.operation_id,request.stage));
    const packet=researchPacket.parse(await backend().research('preview',request));
    if(packet.id!==request.id||packet.operation_id!==request.operation_id||packet.stage!==request.stage)throw new Error('准确发送预览与当前会话、调研任务或阶段不对应。');
    const selected=request.sources?.map(item=>item.kind+':'+item.evidence_id).sort();
    if(selected&&JSON.stringify(packet.source_ids.map(item=>item.kind+':'+item.evidence_id).sort())!==JSON.stringify(selected))throw new Error('准确发送来源与明确选择不对应。');
    const id=key(request.operation_id,request.stage);packets.delete(id);while(packets.size>=20)packets.delete(packets.keys().next().value!);packets.set(id,{request,revision:packet.revision,body:JSON.stringify(packet)});return packet;
  }));
  handle('orvia:research-generate',1,input=>serial(async()=>{
    const request=researchGenerateInput.parse(input),id=key(request.operation_id,request.stage),old=packets.get(id);if(!old||old.request.id!==request.id||old.revision!==request.revision)throw new Error('请准备并完整审查本批准确发送正文。');
    packets.delete(id);
    const started=generation;
    const fresh=researchPacket.parse(await backend().research('preview',old.request));if(fresh.id!==request.id||fresh.operation_id!==request.operation_id||fresh.revision!==request.revision||JSON.stringify(fresh)!==old.body)throw new Error('原文、范围、批次或发送正文已变化，请重新审查。');
    if(!await approve('批准此批调研模型发送',`${fresh.purpose}：发送以下准确正文给固定Main？`,old.body+'\n接收方：Main / deepseek-flash / https://api.deepseek.com。仅发送以上准确system和input，合计最多42KiB；30秒、4096输出token、零自动重试，可能产生供应商费用。批摘要不能替代原文引用；失败、取消、断线或结果未知均不自动重试。'))return{cancelled:true};
    // 弹窗等待期间取消/重连也会撤销；用户随后点批准不能复活已撤回的这批正文。
    if(started!==generation||cancelled.has(request.operation_id))throw new Error('发送许可已因取消或重连撤销，请核对任务事实。');
    const result=researchTask.parse(await backend().research('generate',request));if(result.id!==request.id||result.operation_id!==request.operation_id)throw new Error('返回生成事实与准确会话和任务不对应。');
    return{cancelled:false,result};
  }));
  return{clear:()=>{generation++;plans.clear();packets.clear();cancelled.clear();}};
}
