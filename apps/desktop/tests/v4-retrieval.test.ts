import {describe,it,expect} from 'vitest';
import {retrievalId,retrievalQuery,retrievalResult,retrievalStatus} from '../src/main/retrieval-contracts';
import fs from 'node:fs';

describe('V4-004固定本地检索边界',()=>{
  it('renderer不携带路径、来源扩权、URL或批准',()=>{
    const id='11111111-1111-4111-8111-111111111111';
    expect(retrievalId.parse({id})).toEqual({id});
    for(const extra of [{path:'C:/private'},{sources:['history']},{approved:true},{url:'https://other'}])expect(retrievalQuery.safeParse({id,query:'合成',...extra}).success).toBe(false);
    const source=fs.readFileSync('apps/desktop/src/main/preload.ts','utf8');
    expect(source).toContain("retrievalDownload:()=>ipcRenderer.invoke('orvia:retrieval-download')");
    expect(source).not.toMatch(/retrievalDownload:\s*\(input/);
    expect(retrievalStatus.safeParse({ready:true,reason:null,signature:'fixed',peak_bytes:1,memory_limit_bytes:2,threads:4,batch:4,max_tokens:1024,password:'private'}).success).toBe(false);
  });
  it('合法非BMP片段使用码点契约、拒绝超长或非有限rank',()=>{
    const hit={source:'document:synthetic:1',chunk_index:0,chunk_id:1,text:'😀'.repeat(600),content_hash:'a'.repeat(64),model_revision:null,channels:['keyword'],score:.1,provenance_count:1,supporting_sources:[],provenance_truncated:false};
    const result={mission_id:'synthetic',query:'合成',status:'keyword_only',reason:'MODEL_MISSING',evidence:[hit],coverage:{indexed_chunks:0,candidate_chunks:1,scope_sources:1,output_limited:false}};
    expect(retrievalResult.parse(result).evidence[0].text).toEqual(hit.text);
    expect(retrievalResult.safeParse({...result,evidence:[{...hit,text:'😀'.repeat(601)}]}).success).toBe(false);
    expect(retrievalResult.safeParse({...result,evidence:[{...hit,score:Infinity}]}).success).toBe(false);
  });
});
