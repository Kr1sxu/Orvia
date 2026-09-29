import {expect,it} from 'vitest';
import {mkdir,mkdtemp} from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {BackendClient} from '../../apps/desktop/src/main/backend';
import {documentFixtures} from './m13-fixtures';

it('M15 真实 stdio/SQLite/文档提取的预览、缺钥和跨会话拒绝',async()=>{
  const results=path.resolve(process.env.ORVIA_TEST_RESULTS??'artifacts/test-results/M15');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'stdio-'));documentFixtures(work);
  const backend=new BackendClient(process.cwd(),10000,{dataDirectory:path.join(work,'profile'),credentials:()=>({})});
  try{
    const id=(await backend.chat('chat.create',{client_request_id:randomUUID(),title:'M15 synthetic'})).id;
    const attached=await backend.chat('chat.document.attach',{id,request_id:randomUUID(),path:path.join(work,'synthetic.docx')});
    const source={kind:'document' as const,evidence_id:attached.documents![0].evidence_id};
    const request={id,mode:'summary' as const,question:'概括合成内容',sources:[source]};
    const preview=await backend.chatSynthesisPreview(request);
    expect(preview.fragments.length).toBeGreaterThan(0);expect(preview.fragments[0].locator).toContain('段落');
    expect(preview.supplier).toContain('deepseek-flash');
    const missing=await backend.chat('chat.synthesis.generate',{...request,revision:preview.revision,request_id:randomUUID()});
    expect(missing.messages.at(-1)?.data?.code).toBe('MISSING_CREDENTIAL');
    expect(missing.operation).toBeNull();
    const other=(await backend.chat('chat.create',{client_request_id:randomUUID(),title:'isolated'})).id;
    await expect(backend.chatSynthesisPreview({...request,id:other})).rejects.toThrow();
  }finally{await backend.stop();}
},30000);
