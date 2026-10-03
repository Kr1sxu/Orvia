import {streamEventSchema,scanEntrySchema,type StreamEvent,type ScanEntry} from '../main/m20-contracts';

export type LiveStream={id:string;request_id:string;stream_id?:string;seq:number;entries:ScanEntry[];text:string;status:string;terminal:boolean;paused?:boolean;error?:string;scan_id?:string;summary:Record<string,unknown>};
export function newStream(id:string,request_id:string):LiveStream{return{id,request_id,seq:0,entries:[],text:'',status:'正在理解需求',terminal:false,summary:{}};}
/** 严格按已落盘序号消费；不补造缺口，不把未知流内容归入当前会话。 */
export function applyStream(current:LiveStream,value:unknown):LiveStream{
  const parsed=streamEventSchema.safeParse(value);if(!parsed.success)return{...current,error:'事件结构无效，已停止流式显示，请读取任务事实。',terminal:true};
  const event=parsed.data;
  if(event.conversation_id!==current.id||event.request_id!==current.request_id)return current;
  if(current.stream_id&&event.stream_id!==current.stream_id)return{...current,error:'流身份发生变化，请读取任务事实。',terminal:true};
  if(event.seq<=current.seq)return current;
  if(event.seq!==current.seq+1)return{...current,error:'流事件存在缺口，已停止追加，请读取已保存事实。',terminal:true};
  // paused只是等待外部资料/审批，同一请求接续不保证重新发送started；真正终态和协议错误不可复活。
  if(current.terminal&&(!current.paused||current.error))return current;
  const next={...current,stream_id:event.stream_id,seq:event.seq,terminal:false,paused:false},payload:Record<string,unknown>=event.payload;
  if(event.kind==='scan_batch'){
    const items=Array.isArray(payload.entries)?payload.entries.map(item=>scanEntrySchema.safeParse(item)):[];
    if(items.length>40||items.some(item=>!item.success)||next.entries.length+items.length>5000)return{...next,error:'条目流超过预算或结构无效，请读取完整清单。',terminal:true};
    next.entries=[...next.entries,...items.map(item=>item.success?item.data:neverEntry())];
    if(typeof payload.scan_id==='string')next.scan_id=payload.scan_id;
    next.status='正在扫描，显示实际发现条目';
  }
  if(event.kind==='model_delta'){
    const delta=typeof payload.text==='string'?payload.text:typeof payload.delta==='string'?payload.delta:'';
    if(Array.from(next.text+delta).length>16000)return{...next,error:'文本流超过显示预算，请读取已保存事实。',terminal:true};
    next.text+=delta;next.status='生成中，引用待校验';
  }
  if(event.kind==='tool_status')next.status=String(payload.label??payload.text??payload.status??'工具正在处理').slice(0,300);
  if(payload.summary&&typeof payload.summary==='object'&&!Array.isArray(payload.summary))next.summary=payload.summary as Record<string,unknown>;
  if(['paused','completed','failed','cancelled'].includes(event.kind)){next.terminal=true;next.paused=event.kind==='paused';next.status={paused:'等待必要资料或独立确认',completed:'已收到终态，正在读取程序核验事实',failed:'未完成；部分结果仅供核对',cancelled:'已取消；部分结果仅供核对'}[event.kind as 'paused'|'completed'|'failed'|'cancelled'];}
  return next;
}
function neverEntry():ScanEntry{throw new Error('无效条目不会被接收');}
export function consumeStream(current:LiveStream,events:StreamEvent[]){return events.reduce(applyStream,current);}
