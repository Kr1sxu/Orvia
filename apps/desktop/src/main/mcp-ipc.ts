import {dialog,type BrowserWindow} from 'electron';
import {mcpServerInput,mcpApprovalInput,mcpHistoryInput,mcpCallInput,mcpCallApprovalInput,mcpCredentialInput,mcpConfigPreview,mcpConnectPreview,mcpToolReview,mcpCallPreview,mcpList} from './mcp-contracts';
import type {McpToolReview} from './mcp-contracts';
import type {BackendClient} from './backend';
import type {McpCredentialVault} from './mcp-credentials';

/** 外部服务配置、连接、工具清单和每次调用分别原生审查；renderer不能授予路径或协议权限。 */
export function registerMcp({handle,serial,window,backend,vault}:{
  handle:(channel:string,count:number,action:(...args:unknown[])=>Promise<unknown>)=>void;
  serial:<T>(action:()=>Promise<T>)=>Promise<T>;
  window:()=>BrowserWindow;backend:()=>BackendClient;vault:()=>McpCredentialVault;
}){
  const toolReviews=new Map<string,McpToolReview>();
  const calls=new Map<string,{request:ReturnType<typeof mcpCallInput.parse>;revision:string;body:string}>();
  const callKey=(id:string,sid:string)=>id+':'+sid;
  const canonical=(value:unknown):string=>{if(Array.isArray(value))return'['+value.map(canonical).join(',')+']';if(value!==null&&typeof value==='object')return'{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical((value as Record<string,unknown>)[key])).join(',')+'}';return JSON.stringify(value);};
  const invalidate=(sid:string)=>{toolReviews.delete(sid);for(const [key,entry] of calls)if(entry.request.server_id===sid)calls.delete(key);};
  const approve=async(title:string,message:string,detail:string)=>{
    const decision=await dialog.showMessageBox(window(),{type:'question',title,message,detail,buttons:['取消','批准此项'],defaultId:0,cancelId:0,noLink:true});return decision.response===1;
  };
  handle('orvia:mcp-list',0,()=>backend().mcp('list',{}));
  handle('orvia:mcp-history',1,input=>backend().mcp('history',mcpHistoryInput.parse(input)));
  handle('orvia:mcp-credential-status',0,async()=>vault().getStatus());
  handle('orvia:mcp-import',0,()=>serial(async()=>{
    const chosen=await dialog.showOpenDialog(window(),{title:'选择 MCP 服务配置 JSON',properties:['openFile'],filters:[{name:'MCP 配置',extensions:['json']}]});
    if(chosen.canceled||chosen.filePaths.length!==1)return{cancelled:true};
    const preview=mcpConfigPreview.parse(await backend().mcp('preview_config',{path:chosen.filePaths[0]}));
    if(!await approve('登记 MCP 服务配置','登记以下准确服务配置？',JSON.stringify(preview,null,2)+'\n本步骤仅登记。不会连接、执行本地程序或授权工具；配置不得含令牌、env 或角色凭据。'))return{cancelled:true};
    return{cancelled:false,result:await backend().mcp('configure',{review_id:preview.review_id,revision:preview.revision})};
  }));
  handle('orvia:mcp-connect',1,input=>serial(async()=>{
    const request=mcpServerInput.parse(input),preview=mcpConnectPreview.parse(await backend().mcp('connect_preview',request));
    if(preview.server_id!==request.server_id)throw new Error('连接预览与服务身份不对应。');
    const risk=preview.config.transport==='stdio'?'将执行所示本地程序及参数。程序以当前用户权限运行，MCP协议与只读工具限制不是操作系统隔离；请只连接信任的程序。':'将连接所示准确 HTTPS 接收方。已配置的专用令牌只发往该接收方；不允许重定向或自动跟随资源 URI。';
    if(!await approve('连接此 MCP 服务','批准此准确服务连接并发现工具？',JSON.stringify(preview,null,2)+'\n'+risk+'\n工具清单还需单独审查；连接不批准工具调用。'))return{cancelled:true};
    invalidate(request.server_id);
    const review=mcpToolReview.parse(await backend().mcp('connect',{...request,revision:preview.revision}));
    if(review.server_id!==request.server_id)throw new Error('工具审查与连接服务身份不对应。');
    while(toolReviews.size>=5)toolReviews.delete(toolReviews.keys().next().value!);toolReviews.set(request.server_id,review);
    return{cancelled:false,result:review};
  }));
  handle('orvia:mcp-approve-tools',1,input=>serial(async()=>{
    const request=mcpApprovalInput.parse(input),review=toolReviews.get(request.server_id);
    if(!review||review.revision!==request.revision)throw new Error('请重新连接并审查当前服务工具清单。');
    // 一次决定消耗本次清单；后端重新真实分页核对清单和session，变化即拒绝旧批准。
    toolReviews.delete(request.server_id);
    if(!await approve('审查 MCP 只读工具清单','批准以下清单中允许的工具？',JSON.stringify(review,null,2)+'\n只准准确配置allowlist且通过程序规则的工具。readOnlyHint、名称与声明不能证明服务实际没有副作用；被阻止项不会获得许可。每次调用还需准确参数批准。'))return{cancelled:true};
    return{cancelled:false,result:await backend().mcp('approve_tools',request)};
  }));
  handle('orvia:mcp-disconnect',1,input=>serial(async()=>{const request=mcpServerInput.parse(input);invalidate(request.server_id);return backend().mcp('disconnect',request);}));
  handle('orvia:mcp-remove',1,input=>serial(async()=>{
    const request=mcpServerInput.parse(input),listing=mcpList.parse(await backend().mcp('list',{})),server=listing.servers.find(item=>item.id===request.server_id);
    if(!server)throw new Error('待移除服务配置不存在。');
    // 移除只作用于本地登记，程序文件丢失或远端离线不能阻止关闭和撤回配置。
    if(!await approve('移除 MCP 服务配置','移除此准确服务配置与本机专用令牌？',JSON.stringify(server,null,2)+'\n关闭该服务会话并撤回本机工具批准；不删除外部服务的数据、文件或程序。'))return{cancelled:true};
    invalidate(request.server_id);await backend().mcp('disconnect',request);
    if(vault().get(request.server_id)!==undefined)await vault().remove(request.server_id);
    return{cancelled:false,result:await backend().mcp('remove',request)};
  }));
  handle('orvia:mcp-call-preview',1,input=>serial(async()=>{
    const request=mcpCallInput.parse(input),preview=mcpCallPreview.parse(await backend().mcp('call_preview',request));
    if(preview.id!==request.id||preview.server_id!==request.server_id||preview.tool!==request.tool||canonical(preview.arguments)!==canonical(request.arguments))throw new Error('调用预览与会话、工具或准确参数不对应。');
    const key=callKey(request.id,request.server_id);calls.delete(key);while(calls.size>=8)calls.delete(calls.keys().next().value!);
    calls.set(key,{request,revision:preview.revision,body:JSON.stringify(preview)});return preview;
  }));
  handle('orvia:mcp-call',1,input=>serial(async()=>{
    const request=mcpCallApprovalInput.parse(input),key=callKey(request.id,request.server_id),old=calls.get(key);
    if(!old||old.revision!==request.revision)throw new Error('请先完整审查当前服务与工具的调用参数。');
    const fresh=mcpCallPreview.parse(await backend().mcp('call_preview',old.request));
    if(fresh.id!==request.id||fresh.server_id!==request.server_id||fresh.revision!==request.revision||JSON.stringify(fresh)!==old.body){calls.delete(key);throw new Error('服务、工具结构、会话或参数已变化，请重新审查。');}
    calls.delete(key);
    if(!await approve('批准此 MCP 工具调用','批准以下准确只读工具调用？',old.body+'\n只向此已审查服务发送所示参数，不调用角色模型。响应与资源 URI 仅作为数据展示，不授予新权限。失败、断线或未知结果不会自动重试。'))return{cancelled:true};
    return{cancelled:false,result:await backend().mcp('call',request)};
  }));
  async function credentialChange(input:unknown,remove:boolean){
    const request=remove?mcpServerInput.parse(input):mcpCredentialInput.parse(input);
    let detail:string;
    if(remove){const listing=mcpList.parse(await backend().mcp('list',{})),server=listing.servers.find(item=>item.id===request.server_id);if(!server)throw new Error('待移除令牌的服务配置不存在。');detail=JSON.stringify(server,null,2);}
    else{const preview=mcpConnectPreview.parse(await backend().mcp('connect_preview',{server_id:request.server_id}));if(preview.server_id!==request.server_id||preview.config.transport!=='https')throw new Error('专用令牌只允许准确 HTTPS 服务。');detail=JSON.stringify(preview.config,null,2);}
    if(!await approve(remove?'移除 MCP 专用令牌':'保存 MCP 专用令牌',remove?'移除此准确服务的本机令牌？':'将专用令牌加密保存给此准确接收方？',detail+'\n令牌不会显示或写入配置与日志。更新会关闭该服务连接并撤回旧批准；开发版也没有明文存储回退。'))return{cancelled:true};
    invalidate(request.server_id);await backend().mcp('disconnect',{server_id:request.server_id});
    if(remove)await vault().remove(request.server_id);else await vault().save(request.server_id,(request as ReturnType<typeof mcpCredentialInput.parse>).key);
    await backend().mcp('credential_replace',{server_id:request.server_id,credential:vault().get(request.server_id)??null});
    return{cancelled:false,result:vault().getStatus()};
  }
  handle('orvia:mcp-credential-save',1,input=>serial(()=>credentialChange(input,false)));
  handle('orvia:mcp-credential-remove',1,input=>serial(()=>credentialChange(input,true)));
  return{clear:()=>{toolReviews.clear();calls.clear();}};
}
