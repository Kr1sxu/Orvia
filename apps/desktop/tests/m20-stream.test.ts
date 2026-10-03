import {describe,it,expect} from 'vitest';
import {applyStream,newStream,consumeStream} from '../src/renderer/m20-state';

const id='6f1b7524-1eac-4567-a6b5-c3c9f563052c',other='11111111-1111-4111-8111-111111111111';
function event(seq:number,kind:string,payload:unknown){return{v:1,event:'chat.stream',id,conversation_id:id,request_id:id,stream_id:id,seq,kind,payload};}
describe('M20增量状态（仅真实事件投影，mock事件）',()=>{
  it('旧paused和同请求接续可同批消费，没有started也确认完整序号',()=>{
    const state=consumeStream(newStream(id,id),[
      event(1,'started',{label:'开始'}),event(2,'paused',{action:'directory',question:'选择目录'}),event(3,'tool_status',{stage:'scan',label:'已授权扫描'}),
      event(4,'model_delta',{text:'真实增量',provisional:true}),event(5,'completed',{label:'完成'})
    ] as any);
    expect(state.seq).toBe(5);expect(state.text).toBe('真实增量');expect(state.terminal).toBe(true);expect(state.paused).toBe(false);
  });
  it.each(['completed','failed','cancelled'])('paused可直接接续%s但真正终态不得复活',kind=>{
    const paused=applyStream(newStream(id,id),event(1,'paused',{action:'directory',question:'选择目录'}));
    const final=applyStream(paused,event(2,kind,kind==='failed'?{code:'FAILED',message:'失败'}:{label:'结束'}));expect(final.seq).toBe(2);expect(final.paused).toBe(false);
    expect(applyStream(final,event(3,'tool_status',{stage:'scan',label:'不能复活'}))).toBe(final);
    const broken=applyStream(paused,event(3,'tool_status',{stage:'scan',label:'有缺口'}));
    expect(applyStream(broken,event(2,'model_delta',{text:'不可复活',provisional:true})).text).toBe('');
  });
  it('模型delta在终态前追加，工具批次只接受实际条目，不合并其他会话',()=>{
    let state=applyStream(newStream(id,id),event(1,'started',{label:'开始'}));
    state=applyStream(state,event(2,'model_delta',{text:'合成中文',provisional:true}));expect(state.text).toBe('合成中文');expect(state.terminal).toBe(false);expect(state.status).toContain('引用待校验');
    state=applyStream(state,event(3,'scan_batch',{scan_id:id,entries:[{path:'合成.txt',kind:'file',size:5,category:'文档'}],discovered:1,visited:1}));expect(state.entries).toHaveLength(1);
    expect(applyStream(state,{...event(4,'model_delta',{text:'其他会话',provisional:true}),conversation_id:other})).toBe(state);
  });
  it('重复忽略、缺口停止、流身份变化停止，不自造补齐或重试',()=>{
    const original=applyStream(newStream(id,id),event(1,'model_delta',{text:'一',provisional:true}));
    expect(applyStream(original,event(1,'model_delta',{text:'重复',provisional:true}))).toBe(original);
    const gap=applyStream(original,event(3,'model_delta',{text:'三',provisional:true}));expect(gap.text).toBe('一');expect(gap.error).toContain('缺口');expect(gap.terminal).toBe(true);
    expect(applyStream(original,{...event(2,'model_delta',{text:'错误流',provisional:true}),stream_id:other}).error).toContain('身份');
  });
  it('失败或取消终态保留待核对部分；终态后不会继续展示',()=>{
    let state=applyStream(newStream(id,id),event(1,'model_delta',{text:'尚未完成',provisional:true}));
    state=applyStream(state,event(2,'cancelled',{label:'取消'}));expect(state.text).toBe('尚未完成');expect(state.terminal).toBe(true);expect(state.status).toContain('部分结果');
    expect(applyStream(state,event(3,'model_delta',{text:'后续',provisional:true}))).toBe(state);
  });
  it('累计文本有界，拒绝预算之外的合法小增量',()=>{
    let state=newStream(id,id);for(let i=1;i<=3;i++)state=applyStream(state,event(i,'model_delta',{text:'x'.repeat(6000),provisional:true}));
    expect(state.text.length).toBe(12000);expect(state.error).toContain('预算');expect(state.terminal).toBe(true);
  });
});
