import {EventEmitter} from 'node:events';
import {PassThrough} from 'node:stream';
import {randomUUID} from 'node:crypto';
import {spawn,type ChildProcessWithoutNullStreams} from 'node:child_process';
import {beforeEach,afterEach,expect,it,vi} from 'vitest';
import {BackendClient} from '../src/main/backend';

vi.mock('node:child_process',()=>({spawn:vi.fn()}));
type Request={id:string;method:string;params:Record<string,unknown>};
const cid=randomUUID(),rid=randomUUID(),sid=randomUUID();

async function fixture(){
  const child=Object.assign(new EventEmitter(),{stdin:new PassThrough(),stdout:new PassThrough(),stderr:new PassThrough(),kill:vi.fn(()=>true)});
  const requests:Request[]=[];
  child.stdin.on('data',(data:Buffer)=>requests.push(JSON.parse(data.toString())));
  vi.mocked(spawn).mockReturnValue(child as unknown as ChildProcessWithoutNullStreams);
  const write=(data:unknown)=>child.stdout.write(JSON.stringify(data)+'\n');
  const client=new BackendClient('D:/synthetic-orvia');
  const connected=client.start();
  write({v:1,id:requests[0].id,ok:true,result:{protocol:1,service:'orvia-backend',python:'3.12.6'}});
  await connected;
  const pending=client.chat('chat.natural',{id:cid,request_id:rid,text:'合成自然需求'});
  // 各测试用真实连接关闭收尾，捕获拒绝而不制造未处理Promise。
  const result=pending.catch(error=>error);
  await vi.advanceTimersByTimeAsync(0);
  const transport=requests.at(-1)!.id;
  const event=(seq:number,kind='tool_status',payload:unknown={stage:'scan',label:'合成实际状态'},overrides={})=>({v:1,event:'chat.stream',id:transport,conversation_id:cid,request_id:rid,stream_id:sid,seq,kind,payload,...overrides});
  const flush=()=>vi.advanceTimersByTimeAsync(0);
  const close=async()=>{child.emit('close',1,null);await result;};
  return {child,client,requests,write,event,flush,close,result};
}
beforeEach(()=>{vi.useFakeTimers();vi.mocked(spawn).mockReset();});
afterEach(()=>{vi.clearAllTimers();vi.useRealTimers();});

it('冷握手与初始化各自有20秒，连接后健康期限仍保持短限且不重启',async()=>{
  const child=Object.assign(new EventEmitter(),{stdin:new PassThrough(),stdout:new PassThrough(),stderr:new PassThrough(),kill:vi.fn(()=>true)});
  const requests:Request[]=[];child.stdin.on('data',(value:Buffer)=>requests.push(JSON.parse(value.toString())));
  vi.mocked(spawn).mockReturnValue(child as unknown as ChildProcessWithoutNullStreams);
  const client=new BackendClient('D:/synthetic-orvia',5000,{dataDirectory:'D:/synthetic-profile',credentials:()=>({})});
  const start=client.start();const response=(result:unknown)=>child.stdout.write(JSON.stringify({v:1,id:requests.at(-1)!.id,ok:true,result})+'\n');
  await vi.advanceTimersByTimeAsync(6000);expect(child.kill).not.toHaveBeenCalled();
  response({protocol:1,service:'orvia-backend',python:'3.12.6'});await vi.advanceTimersByTimeAsync(0);
  expect(requests.at(-1)!.method).toBe('initialize');await vi.advanceTimersByTimeAsync(6000);expect(child.kill).not.toHaveBeenCalled();
  response({initialized:true});await start;
  const healthy=client.health();const rejected=expect(healthy).rejects.toMatchObject({code:'BACKEND_TIMEOUT'});
  await vi.advanceTimersByTimeAsync(5000);await rejected;expect(child.kill).toHaveBeenCalledOnce();
  await expect(client.health()).rejects.toMatchObject({code:'BACKEND_TIMEOUT'});expect(spawn).toHaveBeenCalledOnce();
});

it('完成响应前已收到真实事件；pull与ACK只释放本地缓冲，不发送新业务',async()=>{
  const f=await fixture();
  f.write(f.event(1,'started',{label:'实际开始'}));await f.flush();
  expect(f.client.streamPull({id:cid,request_id:rid,after_seq:0})).toMatchObject({events:[{seq:1}],last_seq:1,terminal:false});
  const count=f.requests.length;
  expect(f.client.streamAck({id:cid,request_id:rid,seq:1})).toEqual({acked:true});
  expect(f.requests).toHaveLength(count);
  expect(f.client.streamPull({id:cid,request_id:rid,after_seq:1}).events).toHaveLength(0);
  expect(f.client.streamPull({id:cid,request_id:rid,after_seq:0}).gap).toBe(true);
  await f.close();
});

it('有限乱序恢复为连续序号，同一重复只显示一次，包括ACK后重复',async()=>{
  const f=await fixture();
  f.write(f.event(2));f.write(f.event(1));await f.flush();
  const pulled=f.client.streamPull({id:cid,request_id:rid,after_seq:0});
  expect(pulled.events.map(event=>event.seq)).toEqual([1,2]);
  f.client.streamAck({id:cid,request_id:rid,seq:2});
  f.write(f.event(2));await f.flush();
  expect(f.client.streamPull({id:cid,request_id:rid,after_seq:2}).events).toHaveLength(0);
  expect(f.child.kill).not.toHaveBeenCalled();await f.close();
});

it('ACK后内容变化的同序号被拒绝，连接不重放',async()=>{
  const f=await fixture();f.write(f.event(1));await f.flush();
  f.client.streamPull({id:cid,request_id:rid,after_seq:0});f.client.streamAck({id:cid,request_id:rid,seq:1});
  f.write(f.event(1,'tool_status',{stage:'scan',label:'伪造变化'}));await f.flush();
  expect(f.child.kill).toHaveBeenCalledOnce();expect(await f.result).toMatchObject({code:'BACKEND_PROTOCOL'});
  expect(f.requests.filter(value=>value.method==='chat.natural')).toHaveLength(1);
});

it.each([
  ['会话身份',{conversation_id:randomUUID()}],['业务身份',{request_id:randomUUID()}],['运输身份',{id:randomUUID()}],
  ['额外payload',{payload:{stage:'scan',label:'状态',command:'unsafe'}}],['超帧',{kind:'model_delta',payload:{text:'中'.repeat(5000),provisional:true}}],
])('拒绝%s且不重启进程',async(_title,override)=>{
  const f=await fixture();f.write(f.event(1,'tool_status',undefined,override));await f.flush();
  expect(f.child.kill).toHaveBeenCalledOnce();expect(await f.result).toMatchObject({code:'BACKEND_PROTOCOL'});expect(spawn).toHaveBeenCalledOnce();
});

it('超过16序号重排窗立即拒绝，2秒缺口拒绝，不猜失去的事件',async()=>{
  const first=await fixture();first.write(first.event(17));await first.flush();expect(first.child.kill).toHaveBeenCalledOnce();await first.result;
  const second=await fixture();second.write(second.event(2));await second.flush();await vi.advanceTimersByTimeAsync(2000);
  expect(second.child.kill).toHaveBeenCalledOnce();expect(await second.result).toMatchObject({code:'BACKEND_PROTOCOL'});
});

it('80条队列满时暂停管道；ACK释放后再处理后续真实事件',async()=>{
  const f=await fixture();
  for(let seq=1;seq<=81;seq++)f.write(f.event(seq));await f.flush();
  expect(f.child.stdout.isPaused()).toBe(true);
  const first=f.client.streamPull({id:cid,request_id:rid,after_seq:0});expect(first.events).toHaveLength(40);
  f.client.streamAck({id:cid,request_id:rid,seq:40});await f.flush();
  expect(f.child.stdout.isPaused()).toBe(false);
  const second=f.client.streamPull({id:cid,request_id:rid,after_seq:40});expect(second.events.map(item=>item.seq)).toEqual(Array.from({length:40},(_,index)=>index+41));
  f.client.streamAck({id:cid,request_id:rid,seq:80});
  expect(f.client.streamPull({id:cid,request_id:rid,after_seq:80}).events[0].seq).toBe(81);await f.close();
});

it('总字节背压与48KiB单次pull限制独立；10秒无人消费停止',async()=>{
  const f=await fixture();
  for(let seq=1;seq<=50;seq++)f.write(f.event(seq,'model_delta',{text:'中'.repeat(1500),provisional:true}));await f.flush();
  const result=f.client.streamPull({id:cid,request_id:rid,after_seq:0});
  expect(Buffer.byteLength(JSON.stringify(result))).toBeLessThan(48*1024);expect(result.events.length).toBeLessThan(40);
  expect(f.child.stdout.isPaused()).toBe(true);await vi.advanceTimersByTimeAsync(10000);
  expect(await f.result).toMatchObject({code:'BACKEND_PROTOCOL'});expect(f.child.kill).toHaveBeenCalledOnce();
});

it('未交给renderer的序号不能被ACK；paused后同流继续不被当作完成任务',async()=>{
  const f=await fixture();f.write(f.event(1,'paused',{action:'directory',question:'需要目录'}));await f.flush();
  expect(f.client.streamAck({id:cid,request_id:rid,seq:1})).toEqual({acked:false});
  expect(f.client.streamPull({id:cid,request_id:rid,after_seq:0}).terminal).toBe(true);f.client.streamAck({id:cid,request_id:rid,seq:1});
  f.write(f.event(2));await f.flush();expect(f.client.streamPull({id:cid,request_id:rid,after_seq:1})).toMatchObject({last_seq:2,terminal:false});await f.close();
});
