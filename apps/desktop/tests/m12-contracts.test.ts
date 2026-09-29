import {describe,it,expect} from 'vitest';
import {chatBrowserSearchSchema,chatBrowserReadSchema,chatBrowserAskSchema,chatBrowserSourceSchema,browserEvidenceSchema,chatMessageSchema} from '../src/main/chat-contracts';
const id='6f1b7524-1eac-4567-a6b5-c3c9f563052c';
describe('M12 受限来源契约',()=>{
  it('拒绝脚本、Cookie、上传和自选任务根',()=>{
    const good={id,request_id:id,url:'https://example.com/'};
    expect(chatBrowserReadSchema.parse(good).mode).toBe('auto');
    for(const field of ['script','cookie','headers','method','root','upload'])expect(chatBrowserReadSchema.safeParse({...good,[field]:'synthetic'}).success).toBe(false);
    expect(chatBrowserReadSchema.safeParse({...good,mode:'click'}).success).toBe(false);
  });
  it('限制搜索和追问预算，所有网络请求要求幂等标识',()=>{
    expect(chatBrowserSearchSchema.safeParse({id,query:'合成'}).success).toBe(false);
    expect(chatBrowserSearchSchema.safeParse({id,request_id:id,query:'a'.repeat(501)}).success).toBe(false);
    expect(chatBrowserSearchSchema.safeParse({id,request_id:id,query:'合成',max_results:6}).success).toBe(false);
    expect(chatBrowserAskSchema.safeParse({id,request_id:id,query:'a'.repeat(201)}).success).toBe(false);
    expect(chatBrowserSourceSchema.safeParse({id,evidence_id:'../other'}).success).toBe(false);
  });
  it('来源响应必须有哈希、身份、访问时间且不超过正文上限',()=>{
    const source={evidence_id:'a'.repeat(64),content_hash:'b'.repeat(64),source_url:'https://example.com/',accessed_at:'2026-09-29',mode:'http',content:'合成'};
    expect(browserEvidenceSchema.safeParse(source).success).toBe(true);
    expect(browserEvidenceSchema.safeParse({...source,content:'a'.repeat(8001)}).success).toBe(false);
    expect(browserEvidenceSchema.safeParse({...source,content:'😀'.repeat(8000)}).success).toBe(true);
    expect(browserEvidenceSchema.safeParse({...source,content:'😀'.repeat(8001)}).success).toBe(false);
    const message={id,role:'assistant',text:'来源',kind:'source',created_at:'2026-09-29',data:{items:[source],operation:'read',error:null}};
    expect(chatMessageSchema.safeParse(message).success).toBe(true);
    expect(chatMessageSchema.safeParse({...message,data:{items:[{}]}}).success).toBe(false);
  });
});
