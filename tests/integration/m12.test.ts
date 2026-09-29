import {expect,it} from 'vitest';
import {mkdir,mkdtemp} from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {BackendClient} from '../../apps/desktop/src/main/backend';

it('M12 真实 Python/stdio 无 Key、拒绝 URL、引用隔离与重启持久化，无联网',async()=>{
  const results=path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M12');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'stdio-'));
  const make=()=>new BackendClient(process.cwd(),5000,{dataDirectory:work,credentials:()=>({})});
  const backend=make();let id='',evidence_id='';
  try{
    id=(await backend.chat('chat.create',{client_request_id:randomUUID(),title:'M12 synthetic stdio'})).id;
    const search=await backend.chat('chat.browser.search',{id,request_id:randomUUID(),query:'synthetic'});
    expect(search.sources?.[0].error?.code).toBe('SEARCH_UNAVAILABLE');expect(search.grant).toBeNull();
    const read=await backend.chat('chat.browser.read',{id,request_id:randomUUID(),url:'file:///C:/synthetic'});
    expect(read.sources?.[0].error?.code).toBe('URL_BLOCKED');
    evidence_id=read.sources![0].evidence_id;
    expect((await backend.chatSource({id,evidence_id})).error?.code).toBe('URL_BLOCKED');
    const other=(await backend.chat('chat.create',{client_request_id:randomUUID(),title:'other synthetic'})).id;
    await expect(backend.chatSource({id:other,evidence_id})).rejects.toThrow();
    const ask=await backend.chat('chat.browser.ask',{id,request_id:randomUUID(),query:'no evidence'});
    expect(ask.messages.at(-1)?.data?.items).toEqual([]);
  }finally{await backend.stop();}
  const reopened=make();
  try{expect((await reopened.chatSource({id,evidence_id})).error?.code).toBe('URL_BLOCKED');}
  finally{await reopened.stop();}
},20000);
