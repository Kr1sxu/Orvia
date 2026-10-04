import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,readFile,writeFile,open,stat} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {documentFixtures} from '../integration/m13-fixtures';
import type {} from '../../apps/desktop/src/shared/api';

const mode=process.env.ORVIA_M20_LIVE_MODE;
test.skip(process.env.ORVIA_M20_LIVE!=='1'||!['development','installed'].includes(mode??''),'只有已说明两次总预算后显式选择真实Main才执行');

test(`M20 ${mode} 固定Main真实SSE、引用核验和真业务链`,async()=>{
  test.setTimeout(90000);
  const root=path.resolve('.'),results=path.join(root,'artifacts/test-results/M20');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,`live-${mode}-`)),profile=path.join(work,'profile');documentFixtures(work);
  const input=path.join(work,'synthetic.docx');
  // 两条链合计最多两次，失败也计次数；重跑测试不会悄悄重置消费账本。
  async function consumeBudget(){const budgetFile=path.join(results,'live-budget.json'),lock=await open(path.join(results,'live-budget.lock'),'wx');try{
    let budget:{attempts:{mode:string;time:string;maxTokens?:number}[]};try{budget=JSON.parse(await readFile(budgetFile,'utf8'));}catch(error){if((error as NodeJS.ErrnoException).code!=='ENOENT')throw error;budget={attempts:[]};}
    if(!Array.isArray(budget.attempts)||budget.attempts.some(item=>!['development','installed'].includes(item.mode)||typeof item.time!=='string'))throw Error('真实调用预算账本结构无效；关闭调用，不重置次数');
    if(budget.attempts.length>=2||budget.attempts.some(item=>item.mode===mode))throw Error('本轮真实Main两次总预算或本链一次预算已用完；没有重试');
    budget.attempts.push({mode:mode!,time:new Date().toISOString(),maxTokens:mode==='installed'?4096:1024});await writeFile(budgetFile,JSON.stringify(budget,null,2));
  }finally{await lock.close();await import('node:fs/promises').then(fs=>fs.unlink(path.join(results,'live-budget.lock')));}}
  const env:NodeJS.ProcessEnv={...process.env,ORVIA_DEV_DATA_DIR:profile};
  delete env.ELECTRON_RUN_AS_NODE;for(const name of ['DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','PYTHONPATH','PLAYWRIGHT_BROWSERS_PATH'])delete env[name];
  const installed=mode==='installed';
  if(installed){
    const record=JSON.parse((await readFile(path.join(results,'installation.json'),'utf8')).replace(/^\uFEFF/,''));expect(record.status).toBe('installed');expect(record.version).toBe('0.3.0-rc.1');
    execFileSync(path.resolve('node_modules/electron/dist/electron.exe'),[path.resolve('tests/e2e/m20-credential-seed.cjs'),profile],{env:{...env,ORVIA_M20_LIVE:'1'},windowsHide:true,stdio:'pipe'});
    delete env.ORVIA_DEV_DATA_DIR;env.PATH=path.join(process.env.SystemRoot!,'System32');
  }
  const executable=path.join(results,'install-smoke/Orvia M20 Full Test.exe');
  const launchEnv=Object.fromEntries(Object.entries(env).filter((entry):entry is [string,string]=>typeof entry[1]==='string'));
  const app=await electron.launch(installed?{executablePath:executable,args:[`--user-data-dir=${profile}`],env:launchEnv}:{args:[path.resolve('tests/e2e/m20-live-launch.cjs'),`--user-data-dir=${profile}`],env:launchEnv});
  try{
    await app.evaluate(({app,dialog},{input,root,work})=>{
      const load=(process as any).getBuiltinModule('node:module').createRequire(app.isPackaged?process.resourcesPath+'/app.asar/dist/main/main.js':root+'/apps/desktop/dist/main/main.js');
      const path=load('node:path'),modulePath=app.isPackaged?path.join(app.getAppPath(),'dist/main/backend.js'):path.join(root,'apps/desktop/dist/main/backend.js');
      const {BackendClient}=load(modulePath);const facts={calls:0,deltaCount:0,deltaCharacters:0,firstTextAt:0,lastTextAt:0,finishedAt:0,streamId:'',requestId:'',sequences:[] as number[]};(globalThis as any).__m20_liveFacts=facts;
      const chat=BackendClient.prototype.chat;BackendClient.prototype.chat=async function(method:string,params:any){if(method==='chat.synthesis.generate')facts.calls++;try{return await chat.call(this,method,params);}finally{if(method==='chat.synthesis.generate')facts.finishedAt=Date.now();}};
      const buffer=BackendClient.prototype.bufferEvent;BackendClient.prototype.bufferEvent=async function(event:any){if(event.kind==='model_delta'){const now=Date.now();facts.deltaCount++;facts.deltaCharacters+=Array.from(event.payload.text).length;facts.firstTextAt ||=now;facts.lastTextAt=now;facts.streamId=event.stream_id;facts.requestId=event.request_id;facts.sequences.push(event.seq);}return buffer.call(this,event);};
      dialog.showOpenDialog=(async()=>({canceled:false,filePaths:[input]})) as typeof dialog.showOpenDialog;
      dialog.showMessageBox=(async(_window:any,options:any)=>{if(options.title!=='确认向固定 Main 模型发送证据片段')throw Error('未声明的真实调用审批');return{response:1,checkboxChecked:false};}) as typeof dialog.showMessageBox;
      dialog.showSaveDialog=(async(_window:any,options:any)=>{if(options.title!=='保存已预览简报成品（不能覆盖）')throw Error('未声明成品保存');return{canceled:false,filePath:path.join(work,'real-brief.'+options.filters[0].extensions[0])};}) as typeof dialog.showSaveDialog;
    },{input,root,work});
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible({timeout:30000});
    const settings=await page.evaluate(()=>window.orvia.settings());expect(settings.ok).toBe(true);
    // 安装链是独立请求，已另行说明恢复M15既有4096上限；不重放开发失败。
    await page.getByLabel('输入需求').fill('总结这份文档，只给1条结论，回答不超过30字，使用最少必要引用');await page.getByLabel('输入需求').press('Enter');await expect(page.getByLabel('当前需求待办')).toContainText('添加本地资料');
    await page.getByRole('button',{name:'添加本地资料',exact:true}).click();await page.getByRole('menuitem',{name:'添加文件（最多3个）'}).click();
    const preview=page.getByLabel('模型发送范围预览');await expect(preview).toContainText('deepseek-flash');
    await consumeBudget();
    await preview.getByRole('button',{name:'确认发送并生成回答'}).click();
    await expect(page.getByLabel('模型综合回答')).toBeVisible({timeout:40000});
    const state=await page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok)throw Error('list');const answer=await window.orvia.chatGet({id:list.result.conversations[0].id});if(!answer.ok)throw Error('get');return answer.result;});
    const saved=state.messages.find(item=>item.kind==='synthesis')!.data as any;
    const facts=await app.evaluate(()=>(globalThis as any).__m20_liveFacts);
    const streamEvidence={module:'M20',mode,role:'main',model:'deepseek-flash',baseUrl:'https://api.deepseek.com',requests:1,retries:0,maxTokens:installed?4096:1024,networkTimeoutSeconds:20,generationTimeoutSeconds:30,
      realBackend:true,frozenBackend:installed,realSupplier:true,syntheticDataOnly:true,nativeApproval:'test decision after exact preview',...facts,usage:saved.usage,citationCount:saved.citations.length,finalAnswerStored:true};
    // 供应商请求已消费后先保存真实流事实；本地成品失败不能抹掉证据或触发再次上云。
    await writeFile(path.join(results,`live-stream-${mode}.json`),JSON.stringify({...streamEvidence,streamVerified:false,productAuditState:'pending',products:[]},null,2));
    expect(facts.calls).toBe(1);expect(facts.deltaCount).toBeGreaterThan(1);expect(facts.firstTextAt).toBeLessThan(facts.finishedAt);expect(saved.model).toBe('deepseek-flash');expect(saved.citations.length).toBeGreaterThan(0);
    await writeFile(path.join(results,`live-stream-${mode}.json`),JSON.stringify({...streamEvidence,streamVerified:true,productAuditState:'pending',products:[]},null,2));
    await expect.poll(async()=>{const reply=await page.evaluate(id=>window.orvia.chatGet({id}),state.id);return reply.ok?reply.result.workflow:undefined;}).toBeNull();
    // 三格式复用刚存的真实回答，只有本地生成与保存，没有新增模型请求。
    await page.getByLabel('模型综合回答').getByRole('button',{name:'制作 Word／PPT／PDF 简报'}).click();
    for(const format of ['docx','pptx','pdf']){
      const composer=page.getByLabel('简报成品制作');await composer.getByLabel('成品格式').selectOption(format);
      await composer.getByRole('button',{name:'预览内容与版面'}).click();
      await page.getByLabel('简报版式预览').getByRole('button',{name:'选择新文件路径并确认保存'}).click();
      const file=path.join(work,'real-brief.'+format);await expect.poll(async()=>{try{return(await stat(file)).size;}catch{return 0;}}).toBeGreaterThan(1000);
      const signature=(await readFile(file)).subarray(0,format==='pdf'?4:2).toString();expect(signature).toBe(format==='pdf'?'%PDF':'PK');
      await expect(composer.getByRole('button',{name:'预览内容与版面'})).toBeEnabled();
      const current=await page.evaluate(async id=>{const reply=await window.orvia.chatGet({id});if(!reply.ok)throw Error('publication ledger');return reply.result;},state.id);
      expect(current.messages.some(item=>item.kind==='publication'&&item.data?.format===format&&item.data?.message_id===state.messages.find(message=>message.kind==='synthesis')!.id)).toBe(true);
    }
    const expected=path.join(work,'expected-citations.json');await writeFile(expected,JSON.stringify(saved.citations.map((item:any)=>item.citation)));
    // 独立审计已创建文件，不参与产品生成、不作为安装版运行时；仅返回结构／引用／hash。
    const products=JSON.parse(execFileSync(path.resolve('backend/.venv/Scripts/python.exe'),['-X','utf8',path.resolve('backend/tests/m20_publication_evidence.py'),'--directory',work,'--expected',expected],{windowsHide:true,stdio:'pipe'}).toString('utf8'));
    expect((await app.evaluate(()=>(globalThis as any).__m20_liveFacts.calls))).toBe(1);
    await writeFile(path.join(results,`live-stream-${mode}.json`),JSON.stringify({...streamEvidence,streamVerified:true,productAuditState:'verified',products},null,2));
    await page.screenshot({path:path.join(results,`live-stream-${mode}.png`)});
  }finally{
    // 成功标签缺失或本地成品核验失败也保存实际观察元数据；绝不保存模型原文。
    try{
      const facts=await app.evaluate(()=>(globalThis as any).__m20_liveFacts);
      const page=await app.firstWindow();
      const terminal=await page.evaluate(async()=>{
        const list=await window.orvia.chatList();if(!list.ok||!list.result.conversations[0])return{available:false};
        const reply=await window.orvia.chatGet({id:list.result.conversations[0].id});if(!reply.ok)return{available:false};
        return{available:true,conversationId:reply.result.id,errors:reply.result.messages.filter(item=>item.kind==='error').map(item=>({code:item.data?.code,time:item.created_at})),
          synthesisCount:reply.result.messages.filter(item=>item.kind==='synthesis').length,publicationCount:reply.result.messages.filter(item=>item.kind==='publication').length};
      });
      await writeFile(path.join(work,'observed-stream-metadata.json'),JSON.stringify({module:'M20',mode,model:'deepseek-flash',baseUrl:'https://api.deepseek.com',syntheticDataOnly:true,retries:0,...facts,terminal},null,2));
    }finally{await app.close();}
  }
});
