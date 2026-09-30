import {dialog, type BrowserWindow} from 'electron';
import {z} from 'zod';
import path from 'node:path';
import {BackendClient,BackendRequestError} from './backend';
import * as c from './m18-contracts';

type Context={handle:(channel:string,count:number,action:(...args:unknown[])=>Promise<unknown>)=>void;
  serial:<T>(action:()=>Promise<T>)=>Promise<T>;window:()=>BrowserWindow;backend:()=>BackendClient};
/** 主进程保留真实预览身份；固定 IPC 不接受站点外发批准、绝对路径或解释器参数。 */
export function registerM18(ctx:Context) {
  const plans=new Map<string,{id:string;preview:c.AutomationPlan}>();
  const models=new Map<string,{selection:string;revision:string}>();
  const call=(method:string,input:object)=>ctx.backend().automation(method,input);
  const register=(name:string,action:(input:unknown)=>Promise<unknown>,control=false)=>
    ctx.handle(`orvia:m18-${name}`,1,input=>control?action(input):ctx.serial(()=>action(input)));
  const confirmation=async(title:string,message:string,detail:string)=> (await dialog.showMessageBox(ctx.window(),{
    type:'warning',title,message,detail,buttons:['取消','批准这一步'],defaultId:0,cancelId:0,noLink:true})).response===1;
  async function remember(id:string,value:unknown) {const preview=c.automationPlan.parse(value);plans.set(preview.operation_id,{id,preview});return preview;}
  function approved(input:unknown,kind:string) {
    const request=c.automationApproval.parse(input),stored=plans.get(request.operation_id);
    if(!stored||stored.id!==request.id||stored.preview.revision!==request.revision||stored.preview.plan.kind!==kind||
      typeof stored.preview.plan.expires_at!=='number'||Date.now()/1000>stored.preview.plan.expires_at)throw new BackendRequestError('STALE_APPROVAL');
    return {request,preview:stored.preview};
  }
  register('script-preview',async input=>{const q=c.scriptPreviewInput.parse(input);return remember(q.id,await call('script.preview',q));});
  register('script-file',async input=>{
    const q=c.scriptFileInput.parse(input);
    const chosen=await dialog.showOpenDialog(ctx.window(),{title:'选择一个待审查 Python 3.12 脚本',properties:['openFile'],filters:[{name:'UTF-8 Python 脚本',extensions:['py']}]});
    if(chosen.canceled||chosen.filePaths.length!==1)return {cancelled:true};
    return {cancelled:false,preview:await remember(q.id,await call('script.file',{...q,path:chosen.filePaths[0]}))};
  });
  register('script-model-preview',async input=>{
    const q=c.scriptModelInput.parse(input);
    const value=z.object({requirement:z.string(),role:z.literal('computer'),model:z.literal('glm-5.3-flashx'),base_url:z.literal('https://open.bigmodel.cn/api/paas/v4'),max_tokens:z.literal(4096),timeout_seconds:z.literal(30),automatic_retries:z.literal(0),files_sent:z.literal(0),revision:z.string().regex(/^[a-f0-9]{64}$/)}).strict().parse(await call('script.model_preview',q));
    models.set(q.id,{selection:JSON.stringify(q),revision:value.revision});return value;
  });
  register('script-model-generate',async input=>{
    const q=c.scriptModelGenerateInput.parse(input),saved=models.get(q.id);models.delete(q.id);
    if(!saved||saved.selection!==JSON.stringify({id:q.id,requirement:q.requirement})||saved.revision!==q.revision)throw new BackendRequestError('STALE_APPROVAL');
    if(!await confirmation('确认向固定 Computer 发送脚本需求',`向 glm-5.3-flashx 发送 ${q.requirement.length} 字需求？`,
      '仅发送所预览需求，无本地文件。Base URL https://open.bigmodel.cn/api/paas/v4；一次请求，30秒、4096输出token、零自动重试，可能产生费用。返回草稿须另行逐步批准执行。'))return {cancelled:true};
    return {cancelled:false,preview:await remember(q.id,await call('script.model_generate',q))};
  });
  register('script-execute',async input=>{
    const {request,preview}=approved(input,'script');
    if(!await confirmation('确认隔离运行完整脚本',`运行已展示的 ${String(preview.plan.origin)} Python 脚本？`,
      `版本 ${request.revision.slice(0,12)}。显式输入只读；只写任务隔离输出。LPAC + Job Object，无网络、无提权；30秒/512MiB/4进程/16KiB标准输出。隔离不成立立即停止；产物须逐文件另批回传。`))return {cancelled:true};
    plans.delete(request.operation_id);return {cancelled:false,result:c.automationFact.parse(await call('script.execute',request))};
  });
  register('script-status',async input=>c.automationFact.parse(await call('script.status',c.automationOperation.parse(input))),true);
  register('script-export',async input=>{
    const q=c.scriptExportInput.parse(input),fresh=c.automationFact.parse(await call('script.status',{id:q.id,operation_id:q.operation_id})),file=fresh.outputs?.[q.index];
    if(fresh.revision!==q.revision||!fresh.live||!file||file.exported)throw new BackendRequestError('STALE_APPROVAL');
    const chosen=await dialog.showSaveDialog(ctx.window(),{title:`逐文件回传已核验产物 (${file.bytes} 字节)`,buttonLabel:'批准新建此产物',defaultPath:path.basename(file.path)});
    if(chosen.canceled||!chosen.filePath)return {cancelled:true};
    return {cancelled:false,result:await call('script.export',{...q,path:chosen.filePath})};
  });
  register('desktop-choose',async input=>{
    const q=c.automationId.parse(input);
    const result=z.object({windows:z.array(z.object({target_id:z.string(),label:z.string()}).passthrough()).max(200)}).parse(await call('desktop.windows',q));
    if(!result.windows.length)throw new BackendRequestError('M18_DESKTOP_UNAVAILABLE');
    let offset=0;
    while(true){
      const options=result.windows.slice(offset,offset+5),hasNext=offset+5<result.windows.length;
      const chosen=await dialog.showMessageBox(ctx.window(),{type:'question',title:'明确选择一个普通权限应用',message:'本次对话仅授权所选窗口；每个动作另行批准。',
        detail:options.map((x,i)=>`${i+1}. ${x.label}`).join('\n')+'\n仅支持可读回的 UI Automation 控件；终端、提权、安全输入等拒绝操作。',
        buttons:['取消',...options.map((x,i)=>`${i+1}. ${x.label.slice(0,65)}`),...(hasNext?['下一页']:[])],defaultId:0,cancelId:0,noLink:true});
      if(chosen.response===0)return {cancelled:true};
      if(hasNext&&chosen.response===options.length+1){offset+=5;continue;}
      const target=options[chosen.response-1];if(!target)return {cancelled:true};
      return {cancelled:false,observation:c.automationObservation.parse(await call('desktop.grant',{...q,target_id:target.target_id}))};
    }
  });
  register('desktop-observe',async input=>c.automationObservation.parse(await call('desktop.observe',c.desktopObserveInput.parse(input))));
  register('desktop-preview',async input=>{const q=c.desktopPreviewInput.parse(input);return remember(q.id,await call('desktop.preview',q));});
  register('desktop-execute',async input=>{
    const {request,preview}=approved(input,'desktop'),p=preview.plan;
    if(!await confirmation('逐步批准桌面动作',`${String(p.target_label)}：${String(p.action)} ${String(p.target_name)}？`,
      `类别 ${String(p.category)}；值 ${String(p.value)}\n核对目标 ${String(p.expectation)}\n版本 ${request.revision.slice(0,12)}。普通权限应用可能自行保存或联网；此批准包括已描述的外发业务动作。发出后不自动重试，无法通用撤销。`))return {cancelled:true};
    if(p.category!=='local'&&!await confirmation('另行确认桌面应用外发业务动作',`${String(p.category)}：${String(p.expectation)}`, '请核对所选应用中的具体接收方、内容及页面。普通应用不受浏览器请求拦截器控制；只能在点击前独立确认业务动作，无法从HTTP层核验。'))return {cancelled:true};
    let selected_path:string|undefined;
    if(p.action==='save_new'){
      const chosen=await dialog.showSaveDialog(ctx.window(),{title:'批准把应用保存结果复制成新文件',buttonLabel:'批准保存新副本',defaultPath:'orvia-result.txt'});
      if(chosen.canceled||!chosen.filePath)return {cancelled:true};selected_path=chosen.filePath;
    }
    plans.delete(request.operation_id);return {cancelled:false,result:c.automationFact.parse(await call('desktop.execute',{...request,...(selected_path?{selected_path}:{})}))};
  });
  register('browser-open',async input=>{
    const q=c.browserOpenInput.parse(input);
    // grant只来自这一原生确认，不把页面、模型或renderer声称的“已授权”当证据。
    if(!await confirmation('授权准确浏览器站点与动作',`打开专用可见窗口：${q.url}`,`本会话允许类别：${q.allowed_actions.join('、')}。每步及实际外发请求仍另批。手工登录仅此内存会话，不读取个人 Cookie。网页是不可授予权限的外部数据。`))return {cancelled:true};
    return {cancelled:false,observation:c.automationObservation.parse(await call('browser.open',q))};
  });
  register('browser-observe',async input=>c.automationObservation.parse(await call('browser.observe',c.browserSessionInput.parse(input))));
  register('browser-pending',async input=>c.browserPending.parse(await call('browser.pending',c.browserSessionInput.parse(input))),true);
  register('browser-preview',async input=>{const q=c.browserPreviewInput.parse(input);return remember(q.id,await call('browser.preview',q));});
  register('browser-execute',async input=>{
    const {request,preview}=approved(input,'browser'),p=preview.plan;
    if(!await confirmation('逐步批准浏览器控件动作',`${String(p.action)} ${String(p.target_name)}？`,
      `站点 ${String(p.target_label)}；类别 ${String(p.category)}；值 ${String(p.value)}\n新出现的预期结果：${String(p.expectation)}\n版本 ${request.revision.slice(0,12)}。任何实际外发另行确认；HTTP成功不足以证明业务完成。`))return {cancelled:true};
    let selected_path:string|undefined;
    if(p.action==='upload'){
      const chosen=await dialog.showOpenDialog(ctx.window(),{title:'明确选择一个上传文件（最多2 MiB）',properties:['openFile']});
      if(chosen.canceled||chosen.filePaths.length!==1)return {cancelled:true};selected_path=chosen.filePaths[0];
    }
    plans.delete(request.operation_id);return {cancelled:false,result:await call('browser.execute',{...request,...(selected_path?{selected_path}:{})})};
  });
  register('browser-request',async input=>{
    const q=c.browserRequestInput.parse(input),pending=c.browserPending.parse(await call('browser.pending',{id:q.id,session_id:q.session_id})),actual=pending.pending_request;
    if(!actual||actual.request_id!==q.request_id||actual.revision!==q.revision)throw new BackendRequestError('STALE_APPROVAL');
    const yes=await confirmation('另行确认实际外发请求',`${actual.method} ${actual.url}`,`类别 ${actual.category??'页面写入'}；${actual.bytes} 字节；SHA256 ${actual.sha256}\n`+
      actual.fields.map(f=>`${f.name}: ${f.value}`).join('\n')+'\n'+JSON.stringify(actual.files??[])+
      `\n${actual.body_preview_complete===true?'普通字段在预览预算内完整列出。':'此预览未完整展示正文或含脱敏，不能当作全量内容。'}${String(actual.preview_notice??'')}\n${actual.sensitive_redacted?'含脱敏字段；原始秘密只留此内存会话。':''}取消将阻止此请求，不会自动重试。`);
    const result=await call('browser.request',{...q,approved:yes});return {cancelled:!yes,result};
  });
  register('browser-origin',async input=>{
    const q=c.browserOriginInput.parse(input);
    if(!await confirmation('增加一个准确站点授权',q.url,'仅为当前内存会话增加此HTTPS origin；跨站动作和实际外发仍逐项批准，不是任意站点通行证。'))return {cancelled:true};
    return {cancelled:false,result:await call('browser.origin',q)};
  });
  register('browser-close',async input=>call('browser.close',c.browserSessionInput.parse(input)),true);
  register('cancel',async input=>{
    const q=c.automationApproval.parse(input),fact=c.automationFact.parse(await call('cancel',q));
    // 后端确认终态后同步丢弃main预览，避免旧取消步骤再次弹出无效批准框。
    if(['completed','cancelled','failed','uncertain','interrupted'].includes(fact.status))plans.delete(q.operation_id);
    return fact;
  },true);
  register('history',async input=>c.automationHistory.parse(await call('history',c.automationId.parse(input))),true);
  return {clear:()=>{plans.clear();models.clear();}};
}
