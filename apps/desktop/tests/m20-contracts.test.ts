import {describe,it,expect} from 'vitest';
import {naturalInput,continuationInput,materialRemoveInput,streamPullInput,streamAckInput,m20StreamEventSchema,scanPageInput} from '../src/main/m20-contracts';
import {chatSynthesisGenerateSchema} from '../src/main/chat-contracts';

const id='6f1b7524-1eac-4567-a6b5-c3c9f563052c';
describe('M20 strict入口与流边界（合成，无模型）',()=>{
  it('统一输入不允许路径、方法、模型或授权字段',()=>{
    const request={id,request_id:id,text:'看看这里有哪些文件'};expect(naturalInput.parse(request)).toEqual(request);
    for(const extra of [{path:'C:/private'},{method:'execute'},{model:'other'},{approved:true},{sources:[]}])expect(naturalInput.safeParse({...request,...extra}).success).toBe(false);
    expect(continuationInput.safeParse({id,request_id:id,continuation_id:id,success:true}).success).toBe(false);
    expect(materialRemoveInput.safeParse({id,kind:'document',evidence_id:'a'.repeat(64),delete_file:true}).success).toBe(false);
  });
  it('固定pull/ACK/分页预算，不开放任意方法或无限批次',()=>{
    expect(streamPullInput.safeParse({id,request_id:id,after_seq:0,limit:41}).success).toBe(false);
    expect(streamAckInput.safeParse({id,request_id:id,seq:-1}).success).toBe(false);
    expect(scanPageInput.safeParse({id,scan_id:id,offset:5001}).success).toBe(false);
    expect(scanPageInput.safeParse({id,scan_id:id,offset:0,limit:10000}).success).toBe(false);
  });
  it('每类payload严格且12KiB最终帧；增量必须标为待核验',()=>{
    const identity={v:1,event:'chat.stream',id,conversation_id:id,request_id:id,stream_id:id,seq:1};
    expect(m20StreamEventSchema.safeParse({...identity,kind:'model_delta',payload:{text:'真实增量',provisional:true}}).success).toBe(true);
    expect(m20StreamEventSchema.safeParse({...identity,kind:'model_delta',payload:{text:'已核验',provisional:false}}).success).toBe(false);
    expect(m20StreamEventSchema.safeParse({...identity,kind:'tool_status',payload:{stage:'scan',label:'扫描',approved:true}}).success).toBe(false);
    expect(m20StreamEventSchema.safeParse({...identity,kind:'scan_batch',payload:{scan_id:id,entries:Array.from({length:40},(_,i)=>({path:('合成'.repeat(100))+i,kind:'file',size:1,category:'文档'})),discovered:40,visited:40}}).success).toBe(false);
  });
  it('SSE降级只能明确指定固定策略，不能指定另一供应商',()=>{
    const input={id,request_id:id,mode:'summary',question:'合成问题',sources:[{kind:'document',evidence_id:'a'.repeat(64)}],revision:'b'.repeat(64)};
    expect(chatSynthesisGenerateSchema.safeParse({...input,stream_mode:'confirmed_nonstream'}).success).toBe(true);
    expect(chatSynthesisGenerateSchema.safeParse({...input,stream_mode:'auto'}).success).toBe(false);
    expect(chatSynthesisGenerateSchema.safeParse({...input,base_url:'https://other.example'}).success).toBe(false);
  });
});
