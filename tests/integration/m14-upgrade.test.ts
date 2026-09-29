/** 真实旧版→候选版数据库兼容验证；仅本轮隔离安装和合成资料。 */
import {expect,it} from 'vitest';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {BackendClient} from '../../apps/desktop/src/main/backend';
import {profiles} from '../../apps/desktop/src/main/contracts';
import {documentFixtures} from './m13-fixtures';
const root=path.resolve('artifacts/test-results/M14/upgrade-profile');
const marker=path.resolve('artifacts/test-results/M14/upgrade-seed.json');
const stage=process.env.ORVIA_UPGRADE_STAGE;
const make=()=>new BackendClient(process.cwd(),30000,{dataDirectory:root,credentials:()=>({})},
  {resourcesPath:path.resolve('artifacts/test-results/M14/install-smoke/resources')});
it.skipIf(stage!=='seed')('M14 旧安装版创建合成持久化草稿',async()=>{
 await mkdir(root,{recursive:true});const backend=make();
 try{const mission=await backend.createMission({title:'M14 upgrade synthetic',client_request_id:randomUUID()});
 expect(mission.models).toEqual(profiles);
 await writeFile(marker,JSON.stringify({id:mission.id}),'utf8');
 }finally{await backend.stop();}
},60000);
it.skipIf(stage!=='verify')('M14 升级后读取旧草稿并使用新会话文档与FTS',async()=>{
 const seed=JSON.parse(await readFile(marker,'utf8'));documentFixtures(root);const backend=make();
 try{const old=await backend.getMission(seed.id);expect(old.title).toBe('M14 upgrade synthetic');expect(old.models).toEqual(profiles);
 const conversation=await backend.chat('chat.create',{title:'升级后会话',client_request_id:randomUUID()});
 const attached=await backend.chat('chat.document.attach',{id:conversation.id,request_id:randomUUID(),path:path.join(root,'synthetic.docx')});
 expect(attached.documents).toHaveLength(1);
 const ask=await backend.chat('chat.document.ask',{id:conversation.id,request_id:randomUUID(),query:'许可'});
 expect(ask.messages.at(-1)?.data?.items).toHaveLength(1);
 }finally{await backend.stop();}
},60000);
