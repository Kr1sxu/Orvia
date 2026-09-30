import React,{useEffect,useRef,useState} from 'react';
import type {AutomationCategory,AutomationFact,AutomationObservation,AutomationPlan,BrowserPending} from '../main/m18-contracts';
import type {Reply,ScriptModelPreview} from '../shared/api';

const categoryNames:Record<AutomationCategory|string,string>={local:'本地动作',form:'填写与提交表单',message:'发送消息',upload:'上传单文件',delete:'删除记录',transaction:'购买或交易'};
const categories:AutomationCategory[]=['form','message','upload','delete','transaction'];
const labels:Record<string,string>={awaiting_approval:'等待步骤审批',running:'正在执行',awaiting_request:'等待实际外发审批',awaiting_verification:'等待业务核验',response_received:'已收到HTTP回执，尚未核验',completed:'程序核验完成',failed:'失败',uncertain:'结果不确定',cancel_requested:'取消中',cancelled:'已取消',interrupted:'已中断',verified:'程序核验通过',ready:'可继续观察',rejected:'已拒绝'};
const statusText=(value:string)=>labels[value]??value;
const split=(value:string)=>value.split(/[\n,]/).map(x=>x.trim()).filter(Boolean);
const text=(value:unknown)=>typeof value==='string'?value:'';
type DesktopAction='invoke'|'set_value'|'select'|'toggle'|'focus'|'save_new';
type BrowserAction='fill'|'select'|'check'|'click'|'upload';
type DesktopControl=AutomationObservation['controls'][number];

/** 保存框只有明确识别的Save按钮可供save_new选择；其他受保护项继续禁用。 */
export function desktopControlAvailable(observation:AutomationObservation,control:DesktopControl,action:DesktopAction){
  if(control.disabled||control.enabled===false||control.offscreen===true)return false;
  if(action==='save_new')return observation.file_dialog===true&&control.blocked_reason==='file_dialog'&&control.save_button===true;
  if(control.blocked_reason||observation.file_dialog)return false;
  const pattern={invoke:'invoke',set_value:'value',select:'select',toggle:'toggle',focus:'focus'}[action];
  return control.patterns?.includes(pattern)===true;
}
export function pickDesktopControl(observation:AutomationObservation,current:string,action:DesktopAction){
  const choices=observation.controls.filter(control=>desktopControlAvailable(observation,control,action));
  return choices.find(control=>control.control_id===current)?.control_id??choices[0]?.control_id??'';
}
export function M18DesktopControlOptions({observation,action}:{observation:AutomationObservation;action:DesktopAction}){
  return <>{observation.controls.map(control=><option key={control.control_id} value={control.control_id} disabled={!desktopControlAvailable(observation,control,action)}>{control.name||control.control_type||'无名称控件'} · {control.control_id.slice(0,8)}</option>)}</>;
}

/** 计划原文始终用React转义；源码与网页不进入eval、HTML或通用IPC。 */
export function M18PlanReview({plan,label,blocked,approve}:{plan:AutomationPlan;label:string;blocked:boolean;approve:()=>void}){
  const source=text(plan.plan.source);
  const rest=Object.fromEntries(Object.entries(plan.plan).filter(([key])=>key!=='source'));
  return <section aria-label={`${label}审批预览`}><h4>{label} · 等待原生逐步确认</h4><p>版本 {plan.revision}。目标、原文、输入或权限改变后必须重新预览。</p>
    {source&&<><h5>完整Python源码</h5><pre>{source}</pre></>}
    <h5>完整计划与权限</h5><pre>{JSON.stringify(rest,null,2)}</pre>
    <button className="primary" disabled={blocked} onClick={approve}>原生确认此{label}步骤</button>
  </section>;
}

export function M18RequestReview({pending,blocked,decide}:{pending:BrowserPending;blocked:boolean;decide:()=>void}){
  const request=pending.pending_request;
  if(!request)return null;
  return <section aria-label="浏览器实际外发预览"><h4>实际外发请求 · 尚未发送</h4>
    <p>{request.method} {request.url} · {request.bytes} 字节 · {categoryNames[request.category??'']??'手工或页面触发动作'}</p>
    <pre>{JSON.stringify(request.fields,null,2)}</pre><p>正文SHA256 {request.sha256}；审批版本 {request.revision}。</p>
    {text(request.preview_notice)&&<p>{text(request.preview_notice)}</p>}
    {(request.fields_truncated===true||request.body_preview_complete===false)&&<p>此预览不能视作全量正文；请检查标注、专用页面与文件字节摘要后决定。</p>}
    {Array.isArray(request.files)&&request.files.length>0&&<><h5>实际待上传文件</h5><pre>{JSON.stringify(request.files,null,2)}</pre></>}
    {request.sensitive_redacted&&<p>密码、令牌、支付字段或无法安全辨识的正文已遮盖；请结合专用窗口中实际填写的内容核对。</p>}
    <p>填写、勾选也可能自动保存。原生框可拒绝此实际请求；拒绝不会发送。已外发的请求无法承诺撤销，不自动重试。</p>
    <button disabled={blocked} onClick={decide}>原生决定此实际外发请求</button>
  </section>;
}

export function M18Workspace({cid,authorized,disabled,notice,refresh}:{cid:string;authorized:boolean;disabled:boolean;notice:(value:string)=>void;refresh:()=>Promise<void>}){
  const [working,setWorking]=useState(false);
  const [source,setSource]=useState('');
  const [inputs,setInputs]=useState('');
  const [requirement,setRequirement]=useState('');
  const [model,setModel]=useState<ScriptModelPreview>();
  const [scriptPlan,setScriptPlan]=useState<AutomationPlan>();
  const [scriptFact,setScriptFact]=useState<AutomationFact>();
  const [desktop,setDesktop]=useState<AutomationObservation>();
  const [desktopControl,setDesktopControl]=useState('');
  const [desktopAction,setDesktopAction]=useState<DesktopAction>('focus');
  const [desktopValue,setDesktopValue]=useState('');
  const [desktopCategory,setDesktopCategory]=useState('local');
  const [desktopExpectation,setDesktopExpectation]=useState('');
  const [desktopPlan,setDesktopPlan]=useState<AutomationPlan>();
  const [url,setUrl]=useState('');
  const [allowed,setAllowed]=useState<AutomationCategory[]>(['form']);
  const [getPaths,setGetPaths]=useState('');
  const [browser,setBrowser]=useState<AutomationObservation>();
  const [browserControl,setBrowserControl]=useState('');
  const [browserAction,setBrowserAction]=useState<BrowserAction>('fill');
  const [browserValue,setBrowserValue]=useState('');
  const [browserCategory,setBrowserCategory]=useState<AutomationCategory>('form');
  const [browserExpectation,setBrowserExpectation]=useState('');
  const [browserPlan,setBrowserPlan]=useState<AutomationPlan>();
  const [pending,setPending]=useState<BrowserPending>();
  const [extraOrigin,setExtraOrigin]=useState('');
  const [history,setHistory]=useState<AutomationFact[]>([]);
  const live=useRef(true),activeCid=useRef(cid),polling=useRef(false);
  useEffect(()=>{live.current=true;activeCid.current=cid;return()=>{live.current=false};},[cid]);
  const active=()=>live.current&&activeCid.current===cid;
  const blocked=disabled||working;
  const inputPaths=split(inputs);
  const selectedBrowser=browser?.controls.find(x=>x.control_id===browserControl);
  const browserActions=(selectedBrowser?.actions??[]).filter((x):x is BrowserAction=>['fill','select','check','click','upload'].includes(x));

  function accept<T>(reply:Reply<T>):T|undefined{if(!active())return;if(!reply.ok){notice(reply.message);return;}return reply.result;}
  async function guard(action:()=>Promise<void>){if(blocked)return;setWorking(true);try{await action();}catch{if(active())notice('自动化步骤未完成，请刷新程序事实并核对现场；不要重复提交。');}finally{if(active())setWorking(false);}}
  async function facts(){
    const result=accept(await window.orvia.m18History({id:cid}));if(result)setHistory(result.operations);
    if(scriptFact){const item=accept(await window.orvia.m18ScriptStatus({id:cid,operation_id:scriptFact.operation_id}));if(item)setScriptFact(item);}
  }
  function chooseBrowserObservation(value:AutomationObservation){setBrowser(value);if(!value.controls.some(x=>x.control_id===browserControl)){const first=value.controls[0];setBrowserControl(first?.control_id??'');setBrowserAction((first?.actions?.[0] as BrowserAction)??'click');}}
  async function pollBrowser(){if(!browser?.session_id)return;const result=accept(await window.orvia.m18BrowserPending({id:cid,session_id:browser.session_id}));if(result){setPending(result);if(result.observation)chooseBrowserObservation(result.observation);}}
  const unfinished=history.some(item=>['running','awaiting_request','cancel_requested'].includes(item.status));
  useEffect(()=>{
    if(disabled)return;
    let stopped=false;
    async function poll(){if(stopped||polling.current||working)return;polling.current=true;try{await facts();if(browser?.session_id)await pollBrowser();}catch{}finally{polling.current=false;}}
    void poll();
    if(!browser?.session_id&&!unfinished)return()=>{stopped=true};
    const timer=setInterval(()=>void poll(),1500);
    return()=>{stopped=true;clearInterval(timer)};
  },[cid,disabled,working,browser?.session_id,unfinished,scriptFact?.operation_id]);

  async function previewScript(){await guard(async()=>{const result=accept(await window.orvia.m18ScriptPreview({id:cid,source,inputs:inputPaths}));if(result){setScriptPlan(result);setScriptFact(undefined);await facts();}});}
  async function chooseScript(){await guard(async()=>{const result=accept(await window.orvia.m18ScriptFile({id:cid,inputs:inputPaths}));if(result?.preview){setScriptPlan(result.preview);setSource(text(result.preview.plan.source));setScriptFact(undefined);await facts();}else if(result?.cancelled)notice('已取消脚本文件选择。');});}
  async function previewModel(){await guard(async()=>{const result=accept(await window.orvia.m18ScriptModelPreview({id:cid,requirement:requirement.trim()}));if(result)setModel(result);});}
  async function generateModel(){if(!model)return;await guard(async()=>{const result=accept(await window.orvia.m18ScriptModelGenerate({id:cid,requirement:requirement.trim(),revision:model.revision,request_id:crypto.randomUUID()}));if(active())setModel(undefined);if(result?.preview){setScriptPlan(result.preview);setSource(text(result.preview.plan.source));setScriptFact(undefined);await facts();await refresh();}else if(result?.cancelled)notice('已取消向固定Computer发送需求。');});}
  async function executeScript(){if(!scriptPlan)return;await guard(async()=>{const plan=scriptPlan;const result=accept(await window.orvia.m18ScriptExecute({id:cid,operation_id:plan.operation_id,revision:plan.revision}));if(result&&!result.cancelled){setScriptPlan(undefined);const fact=accept(await window.orvia.m18ScriptStatus({id:cid,operation_id:plan.operation_id}));if(fact)setScriptFact(fact);await facts();await refresh();}else if(result?.cancelled)notice('已取消脚本执行审批。');});}
  function chooseDesktopObservation(observation:AutomationObservation){
    const action=observation.file_dialog&&observation.controls.some(control=>desktopControlAvailable(observation,control,'save_new'))?'save_new':desktopAction;
    setDesktop(observation);setDesktopAction(action);setDesktopControl(pickDesktopControl(observation,desktopControl,action));setDesktopPlan(undefined);
  }
  async function chooseDesktop(){await guard(async()=>{const result=accept(await window.orvia.m18DesktopChoose({id:cid}));if(result?.observation)chooseDesktopObservation(result.observation);else if(result?.cancelled)notice('已取消应用窗口授权。');});}
  async function observeDesktop(){if(!desktop?.grant_id)return;await guard(async()=>{const result=accept(await window.orvia.m18DesktopObserve({id:cid,grant_id:desktop.grant_id!}));if(result)chooseDesktopObservation(result);});}
  async function previewDesktop(){if(!desktop?.grant_id)return;await guard(async()=>{const result=accept(await window.orvia.m18DesktopPreview({id:cid,grant_id:desktop.grant_id!,control_id:desktopControl,action:desktopAction,value:desktopAction==='set_value'?desktopValue:'',state_hash:desktop.state_hash,category:desktopCategory as 'local'|AutomationCategory,expectation:desktopExpectation}));if(result){setDesktopPlan(result);await facts();}});}
  async function executeDesktop(){if(!desktopPlan)return;await guard(async()=>{const plan=desktopPlan;const result=accept(await window.orvia.m18DesktopExecute({id:cid,operation_id:plan.operation_id,revision:plan.revision}));if(result&&!result.cancelled){setDesktopPlan(undefined);await facts();await refresh();}else if(result?.cancelled)notice('已取消桌面步骤审批。');});}
  async function openBrowser(){await guard(async()=>{const result=accept(await window.orvia.m18BrowserOpen({id:cid,url:url.trim(),allowed_actions:allowed,get_write_paths:split(getPaths)}));if(result?.observation){chooseBrowserObservation(result.observation);setBrowserPlan(undefined);setPending(undefined);}else if(result?.cancelled)notice('已取消专用浏览器任务授权。');});}
  async function observeBrowser(){if(!browser?.session_id)return;await guard(async()=>{const result=accept(await window.orvia.m18BrowserObserve({id:cid,session_id:browser.session_id!}));if(result){chooseBrowserObservation(result);setBrowserPlan(undefined);}await pollBrowser();});}
  async function previewBrowser(){if(!browser?.session_id)return;await guard(async()=>{const result=accept(await window.orvia.m18BrowserPreview({id:cid,session_id:browser.session_id!,control_id:browserControl,action:browserAction,value:browserValue,state_hash:browser.state_hash,category:browserCategory,expectation:browserExpectation}));if(result){setBrowserPlan(result);await facts();}});}
  async function executeBrowser(){if(!browserPlan)return;await guard(async()=>{const plan=browserPlan;const result=accept(await window.orvia.m18BrowserExecute({id:cid,operation_id:plan.operation_id,revision:plan.revision}));if(result&&!result.cancelled){setBrowserPlan(undefined);await pollBrowser();await facts();await refresh();}else if(result?.cancelled)notice('已取消浏览器控件步骤审批。');});}
  async function decideRequest(){if(!browser?.session_id||!pending?.pending_request)return;await guard(async()=>{const request=pending.pending_request!;accept(await window.orvia.m18BrowserRequest({id:cid,session_id:browser.session_id!,request_id:request.request_id,revision:request.revision}));await pollBrowser();await facts();await refresh();});}
  async function origin(){if(!browser?.session_id)return;await guard(async()=>{const result=accept(await window.orvia.m18BrowserOrigin({id:cid,session_id:browser.session_id!,url:extraOrigin.trim()}));if(result?.cancelled)notice('已取消额外站点授权。');else if(result)notice('准确站点已获授权；此前被CSP或网络策略拒绝的资源需明确重新导航，不自动重放。');});}
  async function closeBrowser(){if(!browser?.session_id)return;await guard(async()=>{const result=accept(await window.orvia.m18BrowserClose({id:cid,session_id:browser.session_id!}));if(result){setBrowser(undefined);setPending(undefined);setBrowserPlan(undefined);await facts();}});}
  async function cancel(item:AutomationFact){await guard(async()=>{const result=accept(await window.orvia.m18Cancel({id:cid,operation_id:item.operation_id,revision:item.revision}));if(result){if(item.kind==='script')setScriptFact(result);if(item.kind==='browser'){setBrowser(undefined);setPending(undefined);}await facts();await refresh();}});}
  async function exportOutput(index:number){if(!scriptFact)return;await guard(async()=>{const result=accept(await window.orvia.m18ScriptExport({id:cid,operation_id:scriptFact.operation_id,revision:scriptFact.revision,index}));if(result?.cancelled)notice('已取消产物回传保存。');await facts();});}

  return <section className="m17-workspace" aria-label="M18脚本桌面浏览器可控执行"><h3>M18 · 可控执行</h3>
    <p>脚本、桌面与网页操作各有独立权限。每个写步骤由原生窗口确认；来源、模型和页面文字不能授予权限。已发出的消息、删除或交易可能无法撤销。</p>
    <details><summary>任意脚本：Python隔离执行</summary><p>CPython 3.12标准库；只读显式输入副本，写入私有产物目录；禁止网络、提权和自动安装。每次执行30秒、512 MiB、4进程；源码最多32 KiB。</p>
      <label>完整Python源码<textarea aria-label="M18 Python源码" maxLength={32768} rows={9} value={source} disabled={blocked} onChange={event=>{setSource(event.target.value);setScriptPlan(undefined);}}/></label>
      <label>授权目录中明确选定的输入相对路径（最多8个；可留空）<textarea aria-label="M18脚本输入路径" value={inputs} disabled={blocked} onChange={event=>{setInputs(event.target.value);setScriptPlan(undefined);}}/></label>
      {!!inputPaths.length&&!authorized&&<p>需要先通过“选择目录”授权这些输入文件；空输入脚本无需目录授权。</p>}
      <div className="row"><button disabled={blocked||!source.trim()||inputPaths.length>8||inputPaths.length>0&&!authorized} onClick={()=>void previewScript()}>预览Python执行计划</button><button disabled={blocked||inputPaths.length>8||inputPaths.length>0&&!authorized} onClick={()=>void chooseScript()}>原生选择Python脚本</button></div>
      <details><summary>可选：固定Computer提出脚本草稿</summary><label>脚本需求（只发送这段用户文字）<textarea aria-label="M18脚本模型需求" value={requirement} maxLength={1000} disabled={blocked} onChange={event=>{setRequirement(event.target.value);setModel(undefined);}}/></label><button disabled={blocked||!requirement.trim()} onClick={()=>void previewModel()}>预览脚本模型发送范围</button>
        {model&&<section aria-label="脚本模型发送预览"><pre>{model.requirement}</pre><p>{model.model} · {model.base_url}；最多{model.max_tokens}输出token，等待{model.timeout_seconds}秒，0自动重试。只生成草稿，可能收费。</p><button disabled={blocked} onClick={()=>void generateModel()}>原生确认后生成Python草稿</button></section>}
      </details>
      {scriptPlan&&<M18PlanReview plan={scriptPlan} label="脚本" blocked={blocked} approve={()=>void executeScript()}/>}
      {scriptFact&&<section aria-label="Python实际运行结果"><h4>实际状态：{statusText(scriptFact.status)}</h4><p>任务 {scriptFact.operation_id}。下列输出来自程序读回；退出码不证明任意业务语义正确。</p>
        <pre>{JSON.stringify(scriptFact.result??{},null,2)}</pre>{scriptFact.outputs?.map(output=><div key={output.index}><p>{output.path} · {output.bytes}字节 · SHA256 {output.sha256}</p><button disabled={blocked||output.exported||scriptFact.status!=='completed'} onClick={()=>void exportOutput(output.index)}>原生确认回传此产物</button></div>)}
        <button disabled={blocked} onClick={()=>void guard(facts)}>刷新Python实际状态</button>
      </section>}
    </details>
    <details><summary>桌面点击：准确应用与控件</summary><p>先在原生选择器授权当前应用窗口，再观察UI Automation控件。错窗、未知弹窗、密码框和状态变化会停止；不使用盲点坐标。</p><button disabled={blocked} onClick={()=>void chooseDesktop()}>原生选择并授权桌面应用</button>
      {desktop&&<section aria-label="桌面控件观察"><h4>{desktop.label}</h4><p>{desktop.notice}</p><button disabled={blocked} onClick={()=>void observeDesktop()}>重新观察桌面控件</button>
        <label>准确控件<select aria-label="M18桌面控件" value={desktopControl} disabled={blocked} onChange={event=>{setDesktopControl(event.target.value);setDesktopPlan(undefined);}}><M18DesktopControlOptions observation={desktop} action={desktopAction}/></select></label>
        <label>单步动作<select aria-label="M18桌面动作" value={desktopAction} disabled={blocked} onChange={event=>{const action=event.target.value as DesktopAction;setDesktopAction(action);setDesktopControl(pickDesktopControl(desktop,desktopControl,action));setDesktopPlan(undefined);}}><option value="focus">聚焦控件</option><option value="invoke">调用按钮或点击</option><option value="set_value">填写文本</option><option value="select">选择条目</option><option value="toggle">切换勾选</option><option value="save_new">应用保存为新副本</option></select></label>
        {desktopAction==='set_value'&&<label>拟填写文字<textarea aria-label="M18桌面填写值" maxLength={2048} value={desktopValue} disabled={blocked} onChange={event=>{setDesktopValue(event.target.value);setDesktopPlan(undefined);}}/></label>}
        <label>本步骤副作用<select aria-label="M18桌面副作用" value={desktopCategory} disabled={blocked} onChange={event=>{setDesktopCategory(event.target.value);setDesktopPlan(undefined);}}>{['local',...categories].map(category=><option key={category} value={category}>{categoryNames[category]}</option>)}</select></label>
        <label>预期结果（供审批与人工业务核对）<input aria-label="M18桌面预期结果" maxLength={300} value={desktopExpectation} disabled={blocked} onChange={event=>{setDesktopExpectation(event.target.value);setDesktopPlan(undefined);}}/></label>
        <button disabled={blocked||!desktopControl||!desktopExpectation.trim()||!desktop.controls.some(control=>control.control_id===desktopControl&&desktopControlAvailable(desktop,control,desktopAction))} onClick={()=>void previewDesktop()}>预览桌面单步计划</button>
        {desktopPlan&&<M18PlanReview plan={desktopPlan} label="桌面" blocked={blocked} approve={()=>void executeDesktop()}/>}
      </section>}
    </details>
    <details><summary>浏览器写操作：专用会话与实际外发</summary><p>只用专用可见窗口，登录由你手工完成；不复用个人Cookie，关闭或重启丢失登录态。公共HTTPS准确站点由原生窗口逐任务授权。</p>
      <label>明确HTTPS页面<input aria-label="M18浏览器URL" value={url} maxLength={2048} disabled={blocked} onChange={event=>setUrl(event.target.value)}/></label>
      <fieldset><legend>本任务允许的动作类别（仍需逐步审批）</legend>{categories.map(category=><label key={category}><input type="checkbox" disabled={blocked||!!browser} checked={allowed.includes(category)} onChange={()=>{setAllowed(values=>values.includes(category)?values.filter(x=>x!==category):[...values,category]);setBrowserPlan(undefined);}}/>{categoryNames[category]}</label>)}</fieldset>
      <label>额外声明的GET写端点路径（每行一个；动态fetch/xhr与后续导航也会暂停）<textarea aria-label="M18 GET写端点" value={getPaths} disabled={blocked} onChange={event=>setGetPaths(event.target.value)}/></label>
      <button disabled={blocked||!url.trim()||!allowed.length||!!browser} onClick={()=>void openBrowser()}>原生授权并打开专用浏览器</button>
      {browser&&<section aria-label="专用浏览器会话"><h4>{browser.title}</h4><p>{browser.url} · {statusText(pending?.status??'ready')}</p><div className="row"><button disabled={blocked} onClick={()=>void observeBrowser()}>重新观察网页控件与外发状态</button><button disabled={blocked} onClick={()=>void closeBrowser()}>关闭专用会话并停止后续请求</button></div>
        <details><summary>当前有界页面文字与控件（不可信数据）</summary><pre>{browser.page_text??''}</pre><pre>{JSON.stringify(browser.controls,null,2)}</pre></details>
        <label>准确网页控件<select aria-label="M18浏览器控件" value={browserControl} disabled={blocked} onChange={event=>{setBrowserControl(event.target.value);const next=browser.controls.find(x=>x.control_id===event.target.value);setBrowserAction((next?.actions?.[0] as BrowserAction)??'click');setBrowserPlan(undefined);}}>{browser.controls.map(control=><option key={control.control_id} value={control.control_id} disabled={control.disabled}>{control.name||control.role||'无名称控件'} · {control.control_id}</option>)}</select></label>
        <label>单步网页动作<select aria-label="M18浏览器动作" value={browserAction} disabled={blocked} onChange={event=>{setBrowserAction(event.target.value as BrowserAction);setBrowserPlan(undefined);}}>{browserActions.map(action=><option key={action} value={action}>{{fill:'填写文本',select:'选择值',check:'勾选状态',click:'点击控件',upload:'原生选择单文件上传'}[action]}</option>)}</select></label>
        {browserAction==='check'?<label>明确勾选状态<select aria-label="M18网页勾选值" value={browserValue==='true'?'true':'false'} disabled={blocked} onChange={event=>{setBrowserValue(event.target.value);setBrowserPlan(undefined);}}><option value="false">false · 取消勾选</option><option value="true">true · 勾选</option></select></label>:['fill','select'].includes(browserAction)&&<label>拟填写文本或选项值<textarea aria-label="M18网页填写值" value={browserValue} maxLength={4000} disabled={blocked} onChange={event=>{setBrowserValue(event.target.value);setBrowserPlan(undefined);}}/></label>}
        <label>本步骤副作用<select aria-label="M18浏览器副作用" value={browserCategory} disabled={blocked} onChange={event=>{setBrowserCategory(event.target.value as AutomationCategory);setBrowserPlan(undefined);}}>{categories.map(category=><option key={category} value={category}>{categoryNames[category]}</option>)}</select></label>
        <label>核验条件：提交后新出现的精确文字子串<input aria-label="M18浏览器核验文字" value={browserExpectation} maxLength={300} disabled={blocked} onChange={event=>{setBrowserExpectation(event.target.value);setBrowserPlan(undefined);}}/></label><p>HTTP成功不等于业务完成。外发核验必须已有本步回执，且此文字不在提交前正文中、提交后真实页面出现；交易结算等语义仍需人工核对。</p>
        <button disabled={blocked||!!pending?.pending_request||!browserControl||!browserExpectation.trim()||!allowed.includes(browserCategory)||browserAction==='upload'&&browserCategory!=='upload'} onClick={()=>void previewBrowser()}>预览网页单步计划</button>
        {browserPlan&&<M18PlanReview plan={browserPlan} label="浏览器" blocked={blocked} approve={()=>void executeBrowser()}/>}
        {pending&&<M18RequestReview pending={pending} blocked={blocked} decide={()=>void decideRequest()}/>}
        {pending?.result&&<section aria-label="浏览器程序核验事实"><pre>{JSON.stringify(pending.result,null,2)}</pre></section>}
        <label>另行授权准确跨源站点<input aria-label="M18额外站点" value={extraOrigin} maxLength={2048} disabled={blocked} onChange={event=>setExtraOrigin(event.target.value)}/></label><button disabled={blocked||!extraOrigin.trim()} onClick={()=>void origin()}>原生确认额外准确站点</button>
      </section>}
    </details>
    <details><summary>执行账本与取消</summary><button disabled={blocked} onClick={()=>void guard(facts)}>读取最新执行账本</button><p>历史记录只保存事实，不能恢复权限或重复执行；结果不确定时先核对现场。</p>
      {history.map(item=><section key={item.operation_id} aria-label="M18执行记录"><p>{item.kind} · {statusText(item.status)} · {item.operation_id}</p><details><summary>最小审计证据</summary><pre>{JSON.stringify(item.audit,null,2)}</pre></details>{item.kind==='script'&&<button disabled={blocked} onClick={()=>void guard(async()=>{const result=accept(await window.orvia.m18ScriptStatus({id:cid,operation_id:item.operation_id}));if(result)setScriptFact(result);})}>读取此脚本事实</button>}{['awaiting_approval','running','awaiting_request','awaiting_verification','cancel_requested'].includes(item.status)&&<button disabled={blocked} onClick={()=>void cancel(item)}>取消此步骤并停止后续动作</button>}</section>)}
    </details>
  </section>;
}
