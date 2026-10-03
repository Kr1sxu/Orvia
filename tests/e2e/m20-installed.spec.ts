/** M20开发/安装版真实离线对照。原生选择/确切新文件保存使用合成替身，后端/模型/业务不替换。 */
import {_electron as electron,expect,test,type ElectronApplication,type Page} from '@playwright/test';
import {mkdir,mkdtemp,writeFile,readFile,stat} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import path from 'node:path';
import {documentFixtures} from '../integration/m13-fixtures';
import type {Conversation} from '../../apps/desktop/src/main/chat-contracts';
import type {} from '../../apps/desktop/src/shared/api';

const mode=process.env.ORVIA_M20_OFFLINE_MODE;
test.skip(!['development','installed'].includes(mode??''),'显式设置真实后端离线对照模式后才执行');

async function fixture(){
  const results=path.resolve('artifacts/test-results/M20');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,`offline-${mode}-`)),profile=path.join(work,'profile');
  const env:NodeJS.ProcessEnv={...process.env,ORVIA_DEV_DATA_DIR:profile};
  for(const key of Object.keys(env))if(key==='ELECTRON_RUN_AS_NODE'||/^(DEEPSEEK|ZHIPU|MIMO|TAVILY|PYTHON|PLAYWRIGHT)_/.test(key)||key.startsWith('ORVIA_M18_')||key.startsWith('ORVIA_M20_'))delete env[key];
  const installed=mode==='installed';let installation:any;
  if(installed){
    const record=path.join(results,'installation.json');
    const present=await stat(record).then(()=>true,()=>false);test.skip(!present,'尚未安装隔离M20全功能候选包');
    installation=JSON.parse((await readFile(record,'utf8')).replace(/^\uFEFF/,''));
    expect(installation).toMatchObject({module:'M20',appId:'cn.orvia.m20.fulltest',version:'0.3.0-rc.1',status:'installed'});
    expect(installation.installRoot).toBe(path.join(results,'install-smoke'));
    expect(String(installation.executableSha256)).toMatch(/^[a-fA-F0-9]{64}$/);
    expect(createHash('sha256').update(await readFile(path.join(results,'install-smoke/Orvia M20 Full Test.exe'))).digest('hex')).toBe(String(installation.executableSha256).toLowerCase());
    env.PATH=path.join(process.env.SystemRoot!,'System32');delete env.ORVIA_DEV_DATA_DIR;
  }
  const executable=path.join(results,'install-smoke/Orvia M20 Full Test.exe');
  const launchEnv=Object.fromEntries(Object.entries(env).filter((entry):entry is [string,string]=>typeof entry[1]==='string'));
  const launch=()=>electron.launch(installed?{executablePath:executable,args:[`--user-data-dir=${profile}`],env:launchEnv}:
    {args:[path.resolve('tests/e2e/m20-runtime-parity-launch.cjs'),`--user-data-dir=${profile}`],env:launchEnv});
  const record=async(name:string,facts:Record<string,unknown>)=>writeFile(path.join(work,`${name}.json`),JSON.stringify({module:'M20',mode,realBackend:true,frozenBackend:installed,installedRecordRunId:installation?.runId,installedExecutableSha256:installation?.executableSha256,modelCalls:0,networkCalls:0,nativeDialogs:'only synthetic file/directory choices and exact M13 new-file save; cloud approvals forbidden',...facts},null,2),'utf8');
  return{work,profile,launch,record,installation};
}
async function ready(page:Page){try{await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible({timeout:30000});}
  catch(error){await test.info().attach('offline-ui-state',{body:await page.locator('body').innerText(),contentType:'text/plain'});throw error;}}
async function choose(app:ElectronApplication,directory:string,files:string[]=[],exports:Partial<Record<'md'|'json',string>>={}){
  await app.evaluate(({dialog},selection)=>{
    dialog.showOpenDialog=(async(_window:unknown,options:any)=>({canceled:false,filePaths:options.properties.includes('openDirectory')?[selection.directory]:selection.files})) as typeof dialog.showOpenDialog;
    // 模型和其他写操作均不批准；下方仅允许两个准确的M13新文件保存路径。
    dialog.showMessageBox=(async()=>{throw Error('离线验收出现未预期审批');}) as typeof dialog.showMessageBox;
    dialog.showSaveDialog=(async(_window:unknown,options:any)=>{
      const format=options.filters?.[0]?.extensions?.[0] as 'md'|'json';
      if(options.title!=='确认保存已预览的引用文档（不覆盖已有文件）'||!['md','json'].includes(format)||!selection.exports[format])throw Error('离线验收出现未预期保存');
      return{canceled:false,filePath:selection.exports[format]};
    }) as typeof dialog.showSaveDialog;
  },{directory,files,exports});
}
async function plus(page:Page,kind:'directory'|'file'){
  await page.getByRole('button',{name:'添加本地资料',exact:true}).click();
  await page.getByRole('menuitem',{name:kind==='file'?'添加文件（最多3个）':'选择并授权文件夹'}).click();
}
async function send(page:Page,text:string){await page.getByLabel('输入需求').fill(text);await expect(page.getByLabel('发送',{exact:true})).toBeEnabled();await page.getByLabel('输入需求').press('Enter');}
async function current(page:Page):Promise<Conversation>{return page.evaluate(async()=>{
  const list=await window.orvia.chatList();if(!list.ok)throw Error(list.message);
  const snapshot=await window.orvia.chatGet({id:list.result.conversations[0].id});if(!snapshot.ok)throw Error(snapshot.message);return snapshot.result;
});}
async function missingSettings(page:Page){
  const reply=await page.evaluate(()=>window.orvia.settings());if(!reply.ok)throw Error(reply.message);
  expect(reply.result.profiles.map(({role,model,base_url})=>({role,model,base_url}))).toEqual([
    {role:'main',model:'deepseek-flash',base_url:'https://api.deepseek.com'},
    {role:'computer',model:'glm-5.3-flashx',base_url:'https://open.bigmodel.cn/api/paas/v4'},
    {role:'browser',model:'mimo-v2.6-flash',base_url:'https://api.xiaomimimo.com/v1'}]);
  expect(reply.result.credentials.every(item=>!item.configured)).toBe(true);return reply.result;
}

test(`M20 ${mode} 离线先请求后授权、空目录、真实6000项截断与完整发现分页、重启不重放`,async()=>{
  test.setTimeout(180000);const f=await fixture();const empty=path.join(f.work,'empty'),large=path.join(f.work,'large');
  await mkdir(empty);await mkdir(large);
  for(let offset=0;offset<6000;offset+=100)await Promise.all(Array.from({length:100},(_,index)=>writeFile(path.join(large,`synthetic-${String(offset+index).padStart(4,'0')}.${index%2?'txt':'csv'}`),'synthetic only')));
  let app=await f.launch();let cid='',beforeMessages=0,scanId='',count=0,originalRequest='';
  try{
    let page=await app.firstWindow();await ready(page);await choose(app,empty);await missingSettings(page);
    await expect(page.getByLabel('输入需求')).toHaveAttribute('placeholder','你想做些什么');await expect(page.getByLabel('需求类型')).toHaveCount(0);
    await send(page,'列出目录中的文件');await expect(page.getByLabel('当前需求待办')).toContainText('原请求已保留');
    originalRequest=(await current(page)).workflow!.request_id;await plus(page,'directory');
    await expect(page.getByLabel('目录直接回答').last()).toContainText('实际发现0项');
    let snapshot=await current(page);expect(snapshot.workflow).toBeNull();expect(snapshot.messages.filter(item=>item.kind==='natural_request')).toHaveLength(1);
    await page.getByRole('button',{name:'撤销目录授权',exact:true}).click();await choose(app,large);
    await send(page,'列出目录中的文件');await expect(page.getByLabel('当前需求待办')).toBeVisible();await plus(page,'directory');
    await expect(page.getByLabel('目录直接回答').last()).toContainText('本次扫描未覆盖全部范围',{timeout:65000});
    snapshot=await current(page);const directory=snapshot.messages.filter(item=>item.kind==='directory_result').at(-1)!.data!;
    const summary=directory.summary as Record<string,unknown>;count=Number(summary.discovered);scanId=String(directory.scan_id);cid=snapshot.id;
    expect(count).toBeGreaterThan(100);expect(count).toBeLessThanOrEqual(5000);expect(summary.complete).toBe(false);expect(summary.truncated).toBe(true);expect(summary.depth).toBe(1);
    const answer=page.getByLabel('目录直接回答').last();await answer.getByRole('button',{name:/完整已发现清单/}).click();await answer.getByRole('button',{name:'下一页',exact:true}).click();await expect(answer).toContainText('条目101');
    const paging=await page.evaluate(async({cid,scanId})=>{
      const paths:string[]=[],offsets:number[]=[];let offset=0;
      for(let pageIndex=0;pageIndex<51;pageIndex++){
        const reply=await window.orvia.chatScanPage({id:cid,scan_id:scanId,offset});if(!reply.ok)throw Error(reply.message);
        offsets.push(offset);paths.push(...reply.result.entries.map(item=>item.path));
        if(reply.result.next_offset===null)return{paths,offsets,total:reply.result.total};
        if(reply.result.next_offset<=offset)throw Error('分页未推进');offset=reply.result.next_offset;
      }throw Error('分页预算超过全部已发现条目');
    },{cid,scanId});expect(paging.total).toBe(count);expect(paging.paths).toHaveLength(count);expect(new Set(paging.paths).size).toBe(count);
    await page.getByRole('button',{name:'撤销目录授权',exact:true}).click();
    const denied=await page.evaluate(id=>window.orvia.chatInspect({id,tool:'list_directory',arguments:{path:'.',limit:20}}),cid);expect(denied.ok).toBe(false);
    await send(page,'列出目录中的文件');await expect(page.getByLabel('当前需求待办')).toBeVisible();beforeMessages=(await current(page)).messages.filter(item=>item.kind==='directory_result').length;
    await page.screenshot({path:path.join(f.work,'directory-before-restart.png')});await app.close();app=await f.launch();page=await app.firstWindow();await ready(page);
    await page.getByRole('navigation',{name:'历史会话'}).getByRole('button').first().click();snapshot=await current(page);
    expect(snapshot.id).toBe(cid);expect(snapshot.grant).toBeNull();expect(snapshot.workflow).toBeNull();expect(snapshot.stream?.state).toBe('interrupted');
    expect(snapshot.messages.filter(item=>item.kind==='directory_result')).toHaveLength(beforeMessages);
    const pageReply=await page.evaluate(({cid,scanId})=>window.orvia.chatScanPage({id:cid,scan_id:scanId,offset:0}),{cid,scanId});expect(pageReply.ok&&pageReply.result.total).toBe(count);
    await f.record('directory',{originalRequest,cid,emptyDiscovered:0,fixtureEntries:6000,discovered:count,summary,pages:paging.offsets.length,allDiscoveredListed:true,grantRevoked:true,restartNoAuthorityNoReplay:true});
  }finally{await app.close();}
});

test(`M20 ${mode} 真实DOCX/PPTX/OCR解析、引用导出、有效资料移除、逐项失败和10MiB拒绝`,async()=>{
  test.setTimeout(180000);const f=await fixture();documentFixtures(f.work);
  execFileSync(path.resolve('backend/.venv/Scripts/python.exe'),['-X','utf8','-c',String.raw`import sys,zipfile
from pathlib import Path
p=Path(sys.argv[1])
with zipfile.ZipFile(p/'synthetic.pptx','w') as z:
 z.writestr('ppt/presentation.xml','<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId r:id="r1"/></p:sldIdLst></p:presentation>')
 z.writestr('ppt/_rels/presentation.xml.rels','<Relationships><Relationship Id="r1" Target="slides/slide1.xml"/></Relationships>')
 z.writestr('ppt/slides/slide1.xml','<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:t>Orvia SYNTHETIC PPTX 2026</a:t></a:p>')`,f.work],{windowsHide:true,stdio:'pipe'});
  await writeFile(path.join(f.work,'broken.pdf'),'synthetic-invalid-pdf');await writeFile(path.join(f.work,'too-large.pdf'),Buffer.alloc(10*1024*1024+1));
  const app=await f.launch();
  try{
    const page=await app.firstWindow();await ready(page);await choose(app,f.work,['synthetic.docx','synthetic.pptx','synthetic.png'].map(name=>path.join(f.work,name)));await missingSettings(page);await plus(page,'file');
    await expect.poll(async()=>(await current(page)).materials?.filter(item=>item.status==='ready').length,{timeout:90000}).toBe(3);
    const snapshot=await current(page),cid=snapshot.id,details=[];
    for(const item of snapshot.materials!){const source=await page.evaluate(q=>window.orvia.chatDocumentSource(q),{id:cid,evidence_id:item.evidence_id});if(!source.ok)throw Error(source.message);details.push(source.result);}
    const docx=details.find(item=>item.title==='synthetic.docx')!,pptx=details.find(item=>item.title==='synthetic.pptx')!,ocr=details.find(item=>item.title==='synthetic.png')!;
    expect(docx.units.map(item=>item.text).join('\n')).toContain('保留来源');expect(pptx.units[0].text).toContain('SYNTHETIC PPTX');
    expect(ocr.units[0].method).toBe('ocr');expect(ocr.units[0].text).toContain('ORVIA');expect(ocr.units[0].confidence).toBeGreaterThanOrEqual(0);
    expect(snapshot.grant).toBeNull();expect(snapshot.operation).toBeNull();
    const exports={md:path.join(f.work,'saved-document.md'),json:path.join(f.work,'saved-document.json')};
    await choose(app,f.work,[],exports);const exported=[];
    for(const format of ['md','json'] as const){
      const preview=await page.evaluate(q=>window.orvia.chatDocumentPreview(q),{id:cid,evidence_id:docx.evidence_id,format});if(!preview.ok)throw Error(preview.message);
      expect(preview.result.coverage).toEqual({cited:docx.units.length,total:docx.units.length});expect(preview.result.content).toContain('保留来源');
      const saved=await page.evaluate(q=>window.orvia.chatDocumentExport(q),{id:cid,evidence_id:docx.evidence_id,format,revision:preview.result.revision,request_id:crypto.randomUUID()});
      expect(saved.ok&&!saved.result.cancelled).toBe(true);const data=await readFile(exports[format]);expect(createHash('sha256').update(data).digest('hex')).toBe(preview.result.revision);
      if(format==='md'){const text=data.toString('utf8');expect(text).toContain(`引用 ${docx.evidence_id}:1`);expect(text).toContain(docx.file_hash);expect(text).toContain(docx.units[0].locator);}
      else{const value=JSON.parse(data.toString('utf8'));expect(value.schema).toBe('orvia.document.export.v1');expect(value.source.evidence_id).toBe(docx.evidence_id);expect(value.source.file_hash).toBe(docx.file_hash);expect(value.source.units[0].text).toBe(docx.units[0].text);}
      exported.push({format,revision:preview.result.revision,bytes:data.length,coverage:preview.result.coverage});
    }
    const savedBytes=await readFile(exports.md),fresh=await page.evaluate(q=>window.orvia.chatDocumentPreview(q),{id:cid,evidence_id:docx.evidence_id,format:'md' as const});if(!fresh.ok)throw Error(fresh.message);
    const overwrite=await page.evaluate(q=>window.orvia.chatDocumentExport(q),{id:cid,evidence_id:docx.evidence_id,format:'md' as const,revision:fresh.result.revision,request_id:crypto.randomUUID()});
    expect(overwrite.ok&&overwrite.result.conversation?.messages.at(-1)?.data?.code).toBe('EXPORT_EXISTS');expect(await readFile(exports.md)).toEqual(savedBytes);
    expect((await current(page)).messages.filter(item=>item.kind==='export')).toHaveLength(2);
    for(const item of snapshot.materials!){const removed=await page.evaluate(q=>window.orvia.chatMaterialRemove(q),{id:cid,kind:'document' as const,evidence_id:item.evidence_id});expect(removed.ok).toBe(true);}
    expect((await current(page)).materials).toHaveLength(0);expect((await page.evaluate(q=>window.orvia.chatDocumentSource(q),{id:cid,evidence_id:docx.evidence_id})).ok).toBe(true);
    await choose(app,f.work,[path.join(f.work,'broken.pdf'),path.join(f.work,'synthetic.docx')]);
    const failed=await page.evaluate(id=>window.orvia.chatAddFiles({id,request_id:crypto.randomUUID()}),cid);if(!failed.ok)throw Error(failed.message);
    expect(failed.result.items.map(item=>({title:item.title,status:item.status}))).toEqual([{title:'broken.pdf',status:'failed'},{title:'synthetic.docx',status:'ready'}]);
    const before=(await current(page)).materials!.length;await choose(app,f.work,[path.join(f.work,'too-large.pdf')]);
    const tooLarge=await page.evaluate(id=>window.orvia.chatAddFiles({id,request_id:crypto.randomUUID()}),cid);expect(tooLarge.ok).toBe(false);expect((await current(page)).materials).toHaveLength(before);
    await page.screenshot({path:path.join(f.work,'real-attachments.png')});await f.record('attachments',{cid,formats:['docx','pptx','png'],realOCR:true,ocrConfidence:ocr.units[0].confidence,realCitationExports:exported,overwriteDenied:true,removedHistoryRetained:true,partialBatchStates:failed.result.items,oversizedRejected:true,noDirectoryGranted:true});
  }finally{await app.close();}
});

test(`M20 ${mode} 固定角色缺凭据明确失败、非法路径IPC拒绝与未开放通用接口`,async()=>{
  const f=await fixture(),app=await f.launch();
  try{
    const page=await app.firstWindow();await ready(page);const settings=await missingSettings(page);await send(page,'你好');
    await expect(page.getByText(/固定Main凭据缺失/)).toBeVisible();const snapshot=await current(page);
    expect(snapshot.messages.at(-1)?.data?.code).toBe('MISSING_CREDENTIAL');expect(snapshot.workflow).toBeNull();expect(snapshot.grant).toBeNull();
    const denied=await page.evaluate(async id=>{
      const api=window.orvia as any;return Promise.all([
        api.chatNatural({id,request_id:crypto.randomUUID(),text:'列出目录',root:'C:/',approved:true}),
        api.chatChooseDirectory({id,path:'C:/'}),api.chatAddFiles({id,request_id:crypto.randomUUID(),path:'C:/synthetic.pdf'}),
        api.chatScanPage({id,scan_id:crypto.randomUUID(),offset:0,path:'../../'}),api.chatContinue({id,request_id:crypto.randomUUID(),continuation_id:crypto.randomUUID(),approved:true}),
      ]);
    },snapshot.id);expect(denied.every(reply=>!reply.ok)).toBe(true);
    expect(await page.evaluate(()=>({node:typeof (window as any).require,ipc:typeof (window.orvia as any).invoke}))).toEqual({node:'undefined',ipc:'undefined'});
    const appFacts=await app.evaluate(({app})=>({packaged:app.isPackaged,version:app.getVersion(),profile:app.getPath('userData')}));expect(appFacts.profile).toBe(f.profile);expect(appFacts.packaged).toBe(mode==='installed');
    if(mode==='installed')expect(appFacts.version).toBe('0.3.0-rc.1');
    await f.record('credentials-ipc',{roles:settings.profiles.map(({role,model,base_url})=>({role,model,base_url})),allCredentialsMissing:true,failure:'MISSING_CREDENTIAL',illegalParametersRefused:denied.length,app:appFacts});
  }finally{await app.close();}
});
