import {dialog,type BrowserWindow} from 'electron';
import {promises as fs} from 'node:fs';
import path from 'node:path';
import {shellPreviewInput,shellOperation,shellApproval,shellId,shellExportInput,shellPreview,shellRun,shellExportPreview} from './shell-contracts';
import type {ShellPreview} from './shell-contracts';
import type {BackendClient} from './backend';

/** Shell以普通账户执行；原生批准绑定完整脚本与实际解释器，路径只来自本次原生选择。 */
export function registerShell({handle,serial,window,backend}:{
  handle:(channel:string,count:number,action:(...args:unknown[])=>Promise<unknown>)=>void;
  serial:<T>(action:()=>Promise<T>)=>Promise<T>;
  window:()=>BrowserWindow;backend:()=>BackendClient;
}){
  const previews=new Map<string,ShellPreview>();
  const samePath=(left:string,right:string)=>path.win32.normalize(left).toLowerCase()===path.win32.normalize(right).toLowerCase();
  const approve=async(title:string,message:string,detail:string)=>(await dialog.showMessageBox(window(),{type:'warning',title,message,detail,buttons:['取消','批准此项'],defaultId:0,cancelId:0,noLink:true})).response===1;
  handle('orvia:shell-detect',0,()=>backend().shell('detect',{}));
  handle('orvia:shell-history',1,input=>backend().shell('history',shellId.parse(input)));
  handle('orvia:shell-status',1,input=>backend().shell('status',shellOperation.parse(input)));
  // 取消不得排在长执行的serial后面，否则无法及时关闭本次Job及自有后代。
  handle('orvia:shell-cancel',1,async input=>{const request=shellOperation.parse(input);previews.delete(request.run_id);return backend().shell('cancel',request);});
  handle('orvia:shell-preview',1,input=>serial(async()=>{
    const {choose_cwd,choose_inputs,...request}=shellPreviewInput.parse(input);let cwd:string|null=null;let inputs:string[]=[];
    if(choose_cwd){const chosen=await dialog.showOpenDialog(window(),{title:'明确选择本次 Shell 工作目录',properties:['openDirectory']});if(chosen.canceled||chosen.filePaths.length!==1)return{cancelled:true};cwd=chosen.filePaths[0];}
    if(choose_inputs){const chosen=await dialog.showOpenDialog(window(),{title:'选择 Shell 显式输入（最多3个，单个10MiB，合计30MiB）',properties:['openFile','multiSelections']});if(chosen.canceled||!chosen.filePaths.length)return{cancelled:true};if(chosen.filePaths.length>3)throw new Error('最多明确选择三个输入文件。');inputs=chosen.filePaths;}
    const preview=shellPreview.parse(await backend().shell('preview',{...request,cwd,inputs}));
    if(preview.id!==request.id||preview.interpreter.id!==request.interpreter_id||preview.script!==request.script||preview.timeout_seconds!==request.timeout_seconds||preview.expected_stdout!==(request.expected_stdout??null)||JSON.stringify(preview.output_names)!==JSON.stringify(request.output_names)||preview.inputs.length!==inputs.length||preview.inputs.some(item=>!inputs.some(filename=>samePath(filename,item.path)))||(cwd!==null&&!samePath(cwd,preview.cwd)))throw new Error('Shell预览与准确脚本、解释器、选择或预算不对应。');
    while(previews.size>=20)previews.delete(previews.keys().next().value!);previews.set(preview.run_id,preview);
    return{cancelled:false,result:preview};
  }));
  handle('orvia:shell-execute',1,input=>serial(async()=>{
    const request=shellApproval.parse(input),old=previews.get(request.run_id);
    if(!old||old.id!==request.id||old.revision!==request.revision)throw new Error('请先重新准备并完整审查本次Shell脚本。');
    const fresh=shellPreview.parse(await backend().shell('review',{id:request.id,run_id:request.run_id}));
    if(fresh.id!==request.id||fresh.run_id!==request.run_id||fresh.revision!==request.revision||JSON.stringify(fresh)!==JSON.stringify(old)){previews.delete(request.run_id);throw new Error('脚本、解释器身份、工作目录或显式输入已变化，请重新审查。');}
    // 原生决定开始即消耗本次许可；窗口异常、取消、失联或结果未知不能重用旧按钮。
    previews.delete(request.run_id);
    if(!await approve('批准此完整 Shell 脚本','以当前普通账户运行以下准确脚本？',JSON.stringify(fresh,null,2)+'\n完整脚本原文：\n'+fresh.script+'\n普通账户执行，不是 LPAC 或文件/网络隔离。脚本可使用当前用户的文件和网络权限；Job仅限制本次进程及自有后代生命周期。完整脚本、解释器身份、cwd、显式输入、超时和输出预算均以上文为准。ORVIA_INPUT_DIR/ORVIA_OUTPUT_DIR为本次输入/产物目录。退出码0只说明进程退出；仅核验列出的stdout与产物，不代表全部业务目标完成。超时、取消或未知结果不自动重试，也不承诺通用撤销。'))return{cancelled:true};
    return{cancelled:false,result:shellRun.parse(await backend().shell('execute',request))};
  }));
  handle('orvia:shell-export',1,input=>serial(async()=>{
    const request=shellExportInput.parse(input),preview=shellExportPreview.parse(await backend().shell('export_preview',request));
    if(preview.id!==request.id||preview.run_id!==request.run_id||preview.name!==request.name)throw new Error('产物回传预览与所选文件不对应。');
    const chosen=await dialog.showSaveDialog(window(),{title:'选择一个新的 Shell 产物保存位置',buttonLabel:'选择新文件',defaultPath:preview.name});if(chosen.canceled||!chosen.filePath)return{cancelled:true};
    try{await fs.lstat(chosen.filePath);throw new Error('SHELL_DESTINATION_EXISTS: 请选择不存在的新文件，不覆盖已有内容');}catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;}
    const fresh=shellExportPreview.parse(await backend().shell('export_preview',request));if(JSON.stringify(fresh)!==JSON.stringify(preview))throw new Error('产物身份、哈希、大小或版本已变化，请重新核对。');
    if(!await approve('逐文件批准 Shell 产物回传','将以下已核验产物保存为新文件？',JSON.stringify(fresh,null,2)+'\n明确新位置：'+chosen.filePath+'\n只回传所示单个产物，不覆盖现有文件。后端仍会在写入前重核当前产物版本、身份与哈希，写入后再次核验。'))return{cancelled:true};
    return{cancelled:false,result:await backend().shell('export',{...request,revision:fresh.revision,path:chosen.filePath})};
  }));
  return{clear:()=>previews.clear()};
}
