/** 只备份已核验的合成mock回答；M20路由/M16三格式生成/保存/读回使用真实开发或冻结安装后端。 */
import {_electron as electron,expect,test,type ElectronApplication,type Page} from '@playwright/test';
import {mkdir,mkdtemp,readFile,writeFile,stat} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import path from 'node:path';
import type {Conversation} from '../../apps/desktop/src/main/chat-contracts';
import type {} from '../../apps/desktop/src/shared/api';

const mode=process.env.ORVIA_M20_PUBLICATION_MODE;
test.skip(!['development','installed'].includes(mode??''),'须显式选择M20成品开发/安装版对照');
const python=path.resolve('backend/.venv/Scripts/python.exe');
type Seed={conversation_id:string;message_id:string;title:string;citations:string[];answerRevision:string;sourceRevision:string;seededAnswerOrigin:string;[key:string]:unknown};

async function fixture(){
  const results=path.resolve('artifacts/test-results/M20');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,`publication-parity-${mode}-`)),profile=path.join(work,'profile');await mkdir(profile);
  // 检验及一致性备份仅使用固定合成seed，绝不复制credentials文件或恢复目录原生授权。
  const seedArgs=['-X','utf8','backend/tests/m20_publication_seed.py','--profile',profile];
  if(process.env.ORVIA_M20_PUBLICATION_SEED_PROFILE)seedArgs.push('--seed-profile',process.env.ORVIA_M20_PUBLICATION_SEED_PROFILE);
  const seed=JSON.parse(execFileSync(python,seedArgs,{windowsHide:true,encoding:'utf8'})) as Seed;
  expect(seed.seededAnswerOrigin).toBe('verified mock synthetic answer');expect(seed.citations.length).toBeGreaterThan(0);
  await writeFile(path.join(work,'seed.json'),JSON.stringify(seed,null,2));
  const installed=mode==='installed';let installation:Record<string,unknown>|undefined;
  const env:NodeJS.ProcessEnv={...process.env,ORVIA_DEV_DATA_DIR:profile};
  for(const key of Object.keys(env))if(key==='ELECTRON_RUN_AS_NODE'||/^(DEEPSEEK|ZHIPU|MIMO|TAVILY|PYTHON|PLAYWRIGHT)_/.test(key)||key.startsWith('ORVIA_M18_')||key.startsWith('ORVIA_M20_'))delete env[key];
  const executable=path.join(results,'install-smoke/Orvia M20 Full Test.exe');
  if(installed){
    const record=path.join(results,'installation.json');test.skip(!await stat(record).then(()=>true,()=>false),'尚无隔离安装准入记录');
    installation=JSON.parse((await readFile(record,'utf8')).replace(/^\uFEFF/,'')) as Record<string,unknown>;
    expect(installation).toMatchObject({module:'M20',appId:'cn.orvia.m20.fulltest',version:'0.3.0-rc.1',status:'installed'});
    expect(installation.installRoot).toBe(path.join(results,'install-smoke'));
    expect(createHash('sha256').update(await readFile(executable)).digest('hex')).toBe(String(installation.executableSha256).toLowerCase());
    env.PATH=path.join(process.env.SystemRoot!,'System32');delete env.ORVIA_DEV_DATA_DIR;
  }
  const launchEnv=Object.fromEntries(Object.entries(env).filter((entry):entry is [string,string]=>typeof entry[1]==='string'));
  const app=await electron.launch(installed?{executablePath:executable,args:[`--user-data-dir=${profile}`],env:launchEnv}:
    {args:[path.resolve('tests/e2e/m20-runtime-parity-launch.cjs'),`--user-data-dir=${profile}`],env:launchEnv});
  return{work,profile,seed,app,installation};
}
async function ready(page:Page){try{await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible({timeout:30000});}
  catch(error){await test.info().attach('publication-parity-ui-state',{body:await page.locator('body').innerText(),contentType:'text/plain'});throw error;}}
async function snapshot(page:Page,id:string):Promise<Conversation>{return page.evaluate(async id=>{const result=await window.orvia.chatGet({id});if(!result.ok)throw Error(result.message);return result.result;},id);}
async function chooseSave(app:ElectronApplication,output:string,format:'docx'|'pptx'|'pdf'){
  await app.evaluate(({dialog},selection)=>{
    // 所有云发送、普通写审批和文件选择一律拒绝；仅本轮准确M16新文件保存框可返回此路径。
    dialog.showMessageBox=(async()=>{throw Error('离线成品验收不允许云调用审批');}) as typeof dialog.showMessageBox;
    dialog.showOpenDialog=(async()=>{throw Error('离线成品验收不允许新文件读取');}) as typeof dialog.showOpenDialog;
    dialog.showSaveDialog=(async(_window:unknown,options:any)=>{
      if(options.title!=='保存已预览简报成品（不能覆盖）'||options.buttonLabel!=='确认创建新文件'||options.filters?.[0]?.extensions?.[0]!==selection.format)throw Error('未预期保存请求');
      return{canceled:false,filePath:selection.output};
    }) as typeof dialog.showSaveDialog;
  },{output,format});
}

test(`M20 ${mode} 历史合法回答经自然需求制作真实Word/PPT/PDF并核验引用`,async()=>{
  test.setTimeout(180000);const f=await fixture(),app=f.app;
  try{
    const page=await app.firstWindow();await ready(page);
    const settings=await page.evaluate(()=>window.orvia.settings());if(!settings.ok)throw Error(settings.message);
    expect(settings.result.credentials.every(item=>!item.configured)).toBe(true);
    await page.getByRole('navigation',{name:'历史会话'}).getByRole('button',{name:f.seed.title,exact:true}).click();
    let state=await snapshot(page,f.seed.conversation_id);expect(state.grant).toBeNull();expect(state.workflow).toBeNull();
    expect(state.messages.filter(item=>item.kind==='synthesis')).toHaveLength(1);
    const baseline=new Set(state.messages.map(item=>item.id)),revisions:Record<string,string>={};
    for(const format of ['docx','pptx','pdf'] as const){
      await chooseSave(app,path.join(f.work,`real-brief.${format}`),format);
      const input={docx:'把刚才回答生成Word简报',pptx:'把刚才回答生成PPT简报',pdf:'把刚才回答生成PDF简报'}[format];
      await page.getByLabel('输入需求').fill(input);await expect(page.getByLabel('发送',{exact:true})).toBeEnabled();await page.getByLabel('输入需求').press('Enter');
      const composer=page.getByLabel('简报成品制作');await expect(composer).toBeVisible();await expect(composer.getByLabel('成品格式')).toHaveValue(format);
      await expect(composer.getByLabel('简报标题')).toHaveValue('资料简报');await composer.getByRole('button',{name:'预览内容与版面'}).click();
      const preview=page.getByLabel('简报版式预览');await expect(preview).toContainText('来源与引用');
      for(const citation of f.seed.citations)await expect(preview).toContainText(citation);
      await preview.getByRole('button',{name:'选择新文件路径并确认保存'}).click();
      await expect.poll(async()=>{
        const current=await snapshot(page,f.seed.conversation_id);
        return current.workflow===null&&current.messages.some(item=>!baseline.has(item.id)&&item.kind==='publication'&&item.data?.format===format);
      },{timeout:65000}).toBe(true);
      state=await snapshot(page,f.seed.conversation_id);
      const created=state.messages.filter(item=>!baseline.has(item.id)&&item.kind==='publication'&&item.data?.format===format);expect(created).toHaveLength(1);
      expect(created[0].data?.message_id).toBe(f.seed.message_id);expect(created[0].data?.filename).toBe(`real-brief.${format}`);
      expect(created[0].data?.source_revision).toBe(f.seed.sourceRevision);
      revisions[format]=String(created[0].data?.revision);expect(revisions[format]).toMatch(/^[a-f0-9]{64}$/);
      await expect(page.getByLabel('成品核验结果').last()).toContainText(`${format.toUpperCase()} 已创建并读回核验`);
    }
    state=await snapshot(page,f.seed.conversation_id);expect(state.grant).toBeNull();expect(state.operation).toBeNull();expect(state.workflow).toBeNull();
    expect(state.messages.filter(item=>item.kind==='synthesis')).toHaveLength(1);
    const recent=state.messages.filter(item=>!baseline.has(item.id));expect(recent.filter(item=>item.kind==='natural_request')).toHaveLength(3);
    expect(recent.filter(item=>['synthesis_request','synthesis','natural_answer','model_partial','error'].includes(item.kind))).toHaveLength(0);
    await writeFile(path.join(f.work,'expected-citations.json'),JSON.stringify(f.seed.citations));
    // 独立开发Python只审计已保存文件，绝非安装版解释器/PATH回退，产品后端未替换。
    const fileFacts=JSON.parse(execFileSync(python,['-X','utf8','backend/tests/m20_publication_evidence.py','--directory',f.work,'--expected',path.join(f.work,'expected-citations.json')],{windowsHide:true,encoding:'utf8'})) as {format:string;sha256:string;pagesOrPlannedBreaks:number;readBackVerified:boolean}[];
    expect(fileFacts.map(item=>item.format)).toEqual(['docx','pptx','pdf']);expect(fileFacts.every(item=>item.readBackVerified)).toBe(true);
    const appFacts=await app.evaluate(({app})=>({packaged:app.isPackaged,version:app.getVersion(),profile:app.getPath('userData')}));
    expect(appFacts.profile).toBe(f.profile);expect(appFacts.packaged).toBe(mode==='installed');if(mode==='installed')expect(appFacts.version).toBe('0.3.0-rc.1');
    await page.screenshot({path:path.join(f.work,'three-formats.png')});
    await writeFile(path.join(f.work,'publication-parity.json'),JSON.stringify({module:'M20',mode,seededAnswerOrigin:f.seed.seededAnswerOrigin,realBackend:true,frozenBackend:mode==='installed',modelCalls:0,networkCalls:0,nativeSave:'fixed synthetic exact new-file path selector; not actual native UI interaction',source:f.seed,app:appFacts,installedRecordRunId:f.installation?.runId,publicationLedgerCount:3,previewRevisions:revisions,files:fileFacts,independentReadback:'pinned development Python audits outputs only; all PDF pages rendered'},null,2));
  }finally{await app.close();}
});
