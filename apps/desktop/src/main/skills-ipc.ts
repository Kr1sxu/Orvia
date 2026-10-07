import {dialog,BrowserWindow} from 'electron';
import {randomUUID} from 'node:crypto';
import {skillToggle,skillRun} from './skills-contracts';
import {z} from 'zod';
import type {BackendClient} from './backend';

/** 导入路径与目录权限只来自原生选择；声明、renderer和执行结果不能授予权限。 */
export function registerSkills({handle,serial,window,backend}:{
  handle:(channel:string,count:number,action:(...args:unknown[])=>Promise<unknown>)=>void;
  serial:<T>(action:()=>Promise<T>)=>Promise<T>;
  window:()=>BrowserWindow;backend:()=>BackendClient;
}){
  handle('orvia:skills-list',1,input=>backend().skills('list',z.object({offset:z.number().int().min(0).max(36)}).strict().parse(input)));
  handle('orvia:skills-history',0,()=>backend().skills('history',{}));
  handle('orvia:skills-execution',1,input=>backend().skills('execution',z.object({plan_id:z.string().uuid()}).strict().parse(input)));
  handle('orvia:skills-toggle',1,input=>serial(()=>backend().skills('enable',skillToggle.parse(input))));
  handle('orvia:skills-import',0,()=>serial(async()=>{
    const chosen=await dialog.showOpenDialog(window(),{title:'选择 Orvia Skill 包目录',properties:['openDirectory']});
    if(chosen.canceled||chosen.filePaths.length!==1)return{cancelled:true};
    const preview=await backend().skills('preview_import',{path:chosen.filePaths[0]});
    const decision=await dialog.showMessageBox(window(),{type:'question',title:'审查 Skill 包',
      message:'登记此版本声明式工作流？',detail:JSON.stringify(preview,null,2)+'\n说明为不可信数据。不会执行脚本、安装依赖或授予工具权限。',
      buttons:['取消','登记此版本'],defaultId:0,cancelId:0,noLink:true});
    if(decision.response!==1)return{cancelled:true};
    return{cancelled:false,result:await backend().skills('register',{review_id:preview.review_id,revision:preview.revision})};
  }));
  handle('orvia:skills-run',1,input=>serial(async()=>{
    const request=skillRun.parse(input);
    const {conversation_id,...workflow}=request;
    if(conversation_id){
      // 会话必须实际存在。无文件grant仅由后端对展开后的每个leaf核验，声明不能自授权限。
      await backend().chat('chat.get',{id:conversation_id});
      const plan=await backend().skills('plan',{...workflow,mission_id:conversation_id,grant_id:null});
      const approval={plan_id:plan.plan_id,revision:plan.revision,mission_id:conversation_id,grant_id:null};
      const decision=await dialog.showMessageBox(window(),{type:'question',title:'确认本地 Skill 执行计划',
        message:'读取明确选择的会话上下文与当前有效资料？',detail:JSON.stringify(plan,null,2)+'\n仅消费本地已核验事实。不调用模型，不授予文件目录权限；生成新改写需另行准确正文批准。受限结果会停止后续步骤。',
        buttons:['取消','执行此计划'],defaultId:0,cancelId:0,noLink:true});
      if(decision.response!==1){await backend().skills('cancel',approval);return{cancelled:true};}
      return{cancelled:false,result:await backend().skills('execute',approval)};
    }
    const chosen=await dialog.showOpenDialog(window(),{title:'授权本次 Skill 只读目录',properties:['openDirectory']});
    if(chosen.canceled||chosen.filePaths.length!==1)return{cancelled:true};
    const mission=await backend().createMission({client_request_id:randomUUID(),title:'Skill 只读工作流'});
    const grant=await backend().grantComputer({mission_id:mission.id,root:chosen.filePaths[0]});
    try{
    const plan=await backend().skills('plan',{...workflow,mission_id:mission.id,grant_id:grant.grant_id});
    const decision=await dialog.showMessageBox(window(),{type:'question',title:'确认 Skill 执行计划',
      message:'执行此版本的只读步骤？',detail:'目录：'+chosen.filePaths[0]+'\n'+JSON.stringify(plan,null,2)+'\n只覆盖本次选择的目录；正文读取仍须单独权限。不调用模型、不移动或重命名文件。',
      buttons:['取消','执行此计划'],defaultId:0,cancelId:0,noLink:true});
    const approval={plan_id:plan.plan_id,revision:plan.revision,mission_id:mission.id,grant_id:grant.grant_id};
    if(decision.response!==1){await backend().skills('cancel',approval);return{cancelled:true};}
    return{cancelled:false,result:await backend().skills('execute',approval)};
    }finally{await backend().revokeComputer(mission.id);}
  }));
}
