import {expect,it} from 'vitest';
import {mkdir,mkdtemp,readFile} from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {BackendClient} from '../../apps/desktop/src/main/backend';
import {documentFixtures} from './m13-fixtures';

it('M13 真实 stdio 附件、引用、导出与隔离重启；无云端调用',async()=>{
  const results=path.resolve(process.env.ORVIA_TEST_RESULTS ?? 'artifacts/test-results/M13');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'stdio-'));documentFixtures(work);
  const make=()=>new BackendClient(process.cwd(),10000,{dataDirectory:path.join(work,'profile'),credentials:()=>({})});
  const backend=make();let id='',eid='';
  try{
    id=(await backend.chat('chat.create',{client_request_id:randomUUID(),title:'M13 synthetic'})).id;
    const attached=await backend.chat('chat.document.attach',{id,request_id:randomUUID(),path:path.join(work,'synthetic.docx')});
    expect(attached.grant).toBeNull();expect(attached.operation).toBeNull();
    eid=attached.documents![0].evidence_id;
    const source=await backend.chatDocumentSource({id,evidence_id:eid});
    expect(source.units[0].text).toContain('许可');expect(source.units[0].method).toBe('text');
    const ask=await backend.chat('chat.document.ask',{id,request_id:randomUUID(),query:'许可'});
    expect(ask.messages.at(-1)?.data?.items).toHaveLength(1);
    const preview=await backend.chatDocumentPreview({id,evidence_id:eid,format:'json'});
    expect(preview.coverage).toEqual({cited:2,total:2});
    const output=path.join(work,'result.json');
    const exported=await backend.chat('chat.document.export',{id,evidence_id:eid,format:'json',revision:preview.revision,request_id:randomUUID(),path:output});
    expect(exported.messages.at(-1)?.kind).toBe('export');expect(await readFile(output,'utf8')).toBe(preview.content);
    const denied=await backend.chat('chat.document.export',{id,evidence_id:eid,format:'json',revision:preview.revision,request_id:randomUUID(),path:output});
    expect(denied.messages.at(-1)?.data?.code).toBe('EXPORT_EXISTS');
    const other=(await backend.chat('chat.create',{client_request_id:randomUUID(),title:'isolated'})).id;
    await expect(backend.chatDocumentSource({id:other,evidence_id:eid})).rejects.toThrow();
  }finally{await backend.stop();}
  const reopened=make();try{
    expect((await reopened.chatDocumentSource({id,evidence_id:eid})).units).toHaveLength(2);
    expect((await reopened.chat('chat.get',{id})).grant).toBeNull();
  }finally{await reopened.stop();}
},30000);
