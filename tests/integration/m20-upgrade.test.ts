/** M20独立0.2基线→0.3完整候选版：真实安装冻结服务、SQLite和历史权限失效；无云调用。 */
import {expect,it} from 'vitest';
import {mkdir,readFile,writeFile,stat} from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {BackendClient,BackendRequestError} from '../../apps/desktop/src/main/backend';
import {profiles} from '../../apps/desktop/src/main/contracts';
import {documentFixtures} from './m13-fixtures';

const result=path.resolve('artifacts/test-results/M20');
const profile=path.join(result,'upgrade-profile');
const marker=path.join(result,'upgrade-seed.json');
const sentinel=path.join(profile,'synthetic-preserved.txt');
const stage=process.env.ORVIA_M20_UPGRADE_STAGE;
const make=()=>new BackendClient(process.cwd(),30000,{dataDirectory:profile,credentials:()=>({})},
  {resourcesPath:path.join(result,'install-smoke/resources')});

async function identity(version:string,status='installed'){
  const record=JSON.parse((await readFile(path.join(result,'installation.json'),'utf8')).replace(/^\uFEFF/,''));
  expect(record.module).toBe('M20');expect(record.appId).toBe('cn.orvia.m20.fulltest');
  expect(record.status).toBe(status);expect(record.version).toBe(version);
  expect(record.installRoot).toBe(path.join(result,'install-smoke'));
  return record;
}

it.skipIf(stage!=='seed')('M20旧基线创建可保留的合成草稿、会话、附件证据和临时目录授权',async()=>{
  const record=await identity('0.2.0-rc.1');expect(record.stage).toBe('InstallBaseline');
  await expect(stat(marker)).rejects.toMatchObject({code:'ENOENT'});
  await mkdir(profile,{recursive:true});documentFixtures(profile);
  await writeFile(sentinel,'M20 synthetic profile must remain after upgrade and uninstall','utf8');
  const backend=make();
  try{
    const mission=await backend.createMission({title:'M20 upgrade synthetic mission',client_request_id:randomUUID()});
    expect(mission.models).toEqual(profiles);
    const conversation=await backend.chat('chat.create',{title:'M20升级保留合成会话',client_request_id:randomUUID()});
    const granted=await backend.chat('chat.grant',{id:conversation.id,root:profile});expect(granted.grant).not.toBeNull();
    const attached=await backend.chat('chat.document.attach',{id:conversation.id,request_id:randomUUID(),path:path.join(profile,'synthetic.docx')});
    const evidence=attached.documents?.find(item=>item.title==='synthetic.docx');expect(evidence).toBeTruthy();
    const asked=await backend.chat('chat.document.ask',{id:conversation.id,request_id:randomUUID(),query:'许可'});
    expect(asked.messages.at(-1)?.data?.items).toHaveLength(1);
    await writeFile(marker,JSON.stringify({module:'M20',runId:record.runId,mission:mission.id,conversation:conversation.id,
      evidence:evidence!.evidence_id,messages:asked.messages.map(message=>message.id),sentinel:await readFile(sentinel,'utf8')},null,2),'utf8');
  }finally{await backend.stop();}
},90000);

it.skipIf(stage!=='verify')('M20真实版本升级保留草稿/引用/历史，旧目录授权失效且不自动执行',async()=>{
  const record=await identity('0.3.0-rc.1');expect(record.stage).toBe('Upgrade');
  expect(record.previousInstallation.version).toBe('0.2.0-rc.1');
  const seed=JSON.parse(await readFile(marker,'utf8'));expect(record.runId).toBe(seed.runId);
  expect(await readFile(sentinel,'utf8')).toBe(seed.sentinel);
  const backend=make();
  try{
    const old=await backend.getMission(seed.mission);expect(old.title).toBe('M20 upgrade synthetic mission');expect(old.models).toEqual(profiles);
    const history=await backend.chat('chat.get',{id:seed.conversation});
    expect(history.messages.map(message=>message.id)).toEqual(seed.messages);expect(history.grant).toBeNull();
    expect(history.documents?.some(item=>item.evidence_id===seed.evidence)).toBe(true);
    await expect(backend.chat('chat.inspect',{id:seed.conversation,tool:'list_directory',arguments:{path:'.',limit:10}}))
      .rejects.toMatchObject({code:'PERMISSION_DENIED'} satisfies Partial<BackendRequestError>);
    const evidence=await backend.chatDocumentSource({id:seed.conversation,evidence_id:seed.evidence});
    expect(evidence.units.some(unit=>unit.text.includes('保留来源'))).toBe(true);
    const preview=await backend.chatDocumentPreview({id:seed.conversation,evidence_id:seed.evidence,format:'md'});
    expect(preview.content).toContain('保留来源');
    await writeFile(path.join(result,'upgrade-verification.json'),JSON.stringify({module:'M20',from:'0.2.0-rc.1',to:'0.3.0-rc.1',
      realFrozenBackend:true,realModels:0,persistedMessages:history.messages.length,persistedEvidence:true,oldDirectoryGrantExpired:true,
      automaticReplay:false,profilePreserved:true},null,2),'utf8');
  }finally{await backend.stop();}
},90000);

it.skipIf(stage!=='preserved')('M20自有卸载后合成profile与旧证据数据库继续保留',async()=>{
  const record=await identity('0.3.0-rc.1','uninstalled');
  const seed=JSON.parse(await readFile(marker,'utf8'));expect(record.runId).toBe(seed.runId);
  expect(await readFile(sentinel,'utf8')).toBe(seed.sentinel);
  expect((await stat(path.join(profile,'app.sqlite'))).size).toBeGreaterThan(0);
  await expect(stat(path.join(result,'install-smoke/Orvia M20 Full Test.exe'))).rejects.toMatchObject({code:'ENOENT'});
  await writeFile(path.join(result,'uninstall-profile-verification.json'),JSON.stringify({module:'M20',syntheticProfilePreserved:true,
    sqlitePreserved:true,ownExecutableRemoved:true,personalData:'not inspected or deleted'},null,2),'utf8');
});
