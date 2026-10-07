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
    const {conversation_id,choose_directory,...workflow}=request;
    if(conversation_id){
      // 会话必须实际存在。无文件grant仅由后端对展开后的每个leaf核验，声明不能自授权限。
      await backend().chat('chat.get',{id:conversation_id});
      let grantId:string|null=null;
      if(choose_directory){
        const selected=await dialog.showOpenDialog(window(),{title:'为此会话组合明确选择只读目录',properties:['openDirectory']});
        if(selected.canceled||selected.filePaths.length!==1)return{cancelled:true};
        const access=await dialog.showMessageBox(window(),{type:'question',title:'选择本次目录只读范围',message:'批准此目录的哪些读取？',detail:selected.filePaths[0]+'\n只允许本次准确会话。读取文本不会自动发送模型；不得移动、删除、运行文件或扩大到目录之外。',buttons:['取消','仅清单与属性','清单、属性与文本读取'],defaultId:0,cancelId:0,noLink:true});
        if(access.response!==1&&access.response!==2)return{cancelled:true};
        grantId=(await backend().grantComputer({mission_id:conversation_id,root:selected.filePaths[0],allow_text:access.response===2})).grant_id;
      }
      try{
      const plan=await backend().skills('plan',{...workflow,mission_id:conversation_id,grant_id:grantId});
      const approval={plan_id:plan.plan_id,revision:plan.revision,mission_id:conversation_id,grant_id:grantId};
      const decision=await dialog.showMessageBox(window(),{type:'question',title:'确认本地 Skill 执行计划',
        message:'执行所示会话和已明确选择目录的只读步骤？',detail:JSON.stringify(plan,null,2)+'\n只消费本地事实或准备调研/简报预览，不调用模型，不保存文件。采集、云正文和成品保存分别批准；待批准或受限结果停止后续步骤。',
        buttons:['取消','执行此计划'],defaultId:0,cancelId:0,noLink:true});
      if(decision.response!==1){await backend().skills('cancel',approval);return{cancelled:true};}
      return{cancelled:false,result:await backend().skills('execute',approval)};
      }finally{if(grantId)await backend().revokeComputer(conversation_id);}
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
