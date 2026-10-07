import {dialog,type BrowserWindow} from 'electron';
import path from 'node:path';
import {processId,processOperation,processApproval,processLaunchInput,processActionInput,processPreview,processExecution} from './process-contracts';
import type {ProcessPreview} from './process-contracts';
import type {BackendClient} from './backend';

/** 每次动作绑定准确PID/创建时间/程序哈希，不能凭旧列表、退出码或模型声明扩大权限。 */
export function registerProcesses({handle,serial,window,backend}:{
  handle:(channel:string,count:number,action:(...args:unknown[])=>Promise<unknown>)=>void;
  serial:<T>(action:()=>Promise<T>)=>Promise<T>;
  window:()=>BrowserWindow;backend:()=>BackendClient;
}){
  const previews=new Map<string,ProcessPreview>();
  const samePath=(left:string,right:string)=>path.win32.normalize(left).toLowerCase()===path.win32.normalize(right).toLowerCase();
  const remember=(preview:ProcessPreview)=>{while(previews.size>=20)previews.delete(previews.keys().next().value!);previews.set(preview.operation_id,preview);};
  handle('orvia:process-list',1,input=>backend().processes('list',processId.parse(input)));
  handle('orvia:process-status',1,input=>backend().processes('status',processOperation.parse(input)));
  handle('orvia:process-history',1,input=>backend().processes('history',processId.parse(input)));
  handle('orvia:process-launch-preview',1,input=>serial(async()=>{
    const {choose_cwd,...request}=processLaunchInput.parse(input);
    const chosen=await dialog.showOpenDialog(window(),{title:'明确选择启动的普通权限 EXE',properties:['openFile'],filters:[{name:'Windows 程序',extensions:['exe']}]});if(chosen.canceled||chosen.filePaths.length!==1)return{cancelled:true};
    let cwd:string|null=null;if(choose_cwd){const selected=await dialog.showOpenDialog(window(),{title:'明确选择此次程序工作目录',properties:['openDirectory']});if(selected.canceled||selected.filePaths.length!==1)return{cancelled:true};cwd=selected.filePaths[0];}
    const preview=processPreview.parse(await backend().processes('preview_launch',{...request,executable:chosen.filePaths[0],cwd}));
    if(preview.id!==request.id||preview.action!=='launch'||!preview.launch||!samePath(preview.launch.executable,chosen.filePaths[0])||JSON.stringify(preview.launch.args)!==JSON.stringify(request.args)||preview.wait_seconds!==request.wait_seconds||(cwd!==null&&!samePath(preview.launch.cwd,cwd)))throw new Error('启动预览与准确原生程序、参数或目录不对应。');
    remember(preview);return{cancelled:false,result:preview};
  }));
  handle('orvia:process-action-preview',1,input=>serial(async()=>{
    const request=processActionInput.parse(input),preview=processPreview.parse(await backend().processes('preview_action',request));
    if(preview.id!==request.id||preview.action!==request.action||!preview.target||preview.target.pid!==request.pid||preview.target.create_time!==request.create_time||preview.target.creation_ticks!==request.creation_ticks||preview.wait_seconds!==request.wait_seconds)throw new Error('进程预览与准确PID、创建时间或动作不对应。');
    remember(preview);return preview;
  }));
  handle('orvia:process-execute',1,input=>serial(async()=>{
    const request=processApproval.parse(input),old=previews.get(request.operation_id);if(!old||old.id!==request.id||old.revision!==request.revision)throw new Error('请重新准备并完整核对本次准确进程动作。');
    const fresh=processPreview.parse(await backend().processes('review',{id:request.id,operation_id:request.operation_id}));
    if(fresh.id!==request.id||fresh.operation_id!==request.operation_id||fresh.revision!==request.revision||JSON.stringify(fresh)!==JSON.stringify(old)){previews.delete(request.operation_id);throw new Error('进程创建时间、程序身份、参数或动作已变化，请重新核对。');}
    // 开始原生决定即消耗许可；窗口异常、取消和未知结果均不自动重放。
    previews.delete(request.operation_id);
    const risk=fresh.action==='terminate'?'终止仅针对所示单个PID，不递归、不批量；可能丢失未保存内容，无法撤销。':fresh.action==='close'?'仅请求温和关闭目标窗口。应用可能显示未保存提示；需要用户自行处理。未退出会明确仍运行，不自动升级为终止。':fresh.action==='launch'?'程序以当前普通用户权限启动，可能使用该账户文件和网络权限；不接管现有个人终端，不提权。':'只等待所示准确进程最多约定秒数，等待结束仍运行不会自动关闭或终止。';
    const decision=await dialog.showMessageBox(window(),{type:'warning',title:'批准此次准确进程动作',message:`批准 ${fresh.action==='launch'?'启动':fresh.action==='wait'?'等待':fresh.action==='close'?'温和关闭':'终止'}此准确普通用户进程？`,detail:JSON.stringify(fresh,null,2)+'\n'+risk+'\nPID、创建时间和程序SHA256均须重新核对。审批只限此一步；失败、断线或结果未知不自动重试。进程已退出或核验通过均不表示业务全部完成。',buttons:['取消','批准此一步'],defaultId:0,cancelId:0,noLink:true});
    if(decision.response!==1)return{cancelled:true};
    const result=processExecution.parse(await backend().processes('execute',request));
    // 返回事实也必须对应这次批准；不能把其它会话或复用PID的新进程当作本次结果。
    if(result.id!==request.id||result.operation_id!==request.operation_id||result.revision!==request.revision||result.action!==fresh.action||(fresh.target&&result.target&&(fresh.target.pid!==result.target.pid||fresh.target.creation_ticks!==result.target.creation_ticks||fresh.target.sha256!==result.target.sha256)))throw new Error('返回进程事实与本次准确批准不对应，请核对本机记录。');
    return{cancelled:false,result};
  }));
  return{clear:()=>previews.clear()};
}
