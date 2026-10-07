import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { backendLaunch, type PackagedRuntime } from './runtime';
import { JsonLines, VERSION, MAX_LINE_BYTES, responseSchema, helloSchema, healthSchema } from './protocol';
import { z } from 'zod';
import {auxiliaryStatus, type AuxiliaryConfig} from './auxiliary-contracts';
import {skillList,skillHistory,skillSummary,skillReview,skillPlan,skillExecution,type SkillsMethod} from './skills-contracts';
import {retrievalStatus,retrievalModel,retrievalResult,retrievalRebuild,retrievalClear,type RetrievalMethod} from './retrieval-contracts';
import {memoryList,memoryContext,memoryPreview,memorySearch,type MemoryMethod} from './memory-contracts';
type MemoryResults={list:z.infer<typeof memoryList>;context:z.infer<typeof memoryContext>;preview:z.infer<typeof memoryPreview>;generate:z.infer<typeof memoryList>;search:z.infer<typeof memorySearch>;correct:z.infer<typeof memoryList>;forget:z.infer<typeof memoryList>};
type RetrievalResults={status:z.infer<typeof retrievalStatus>;model:z.infer<typeof retrievalModel>;prepare:z.infer<typeof retrievalStatus>;activate:z.infer<typeof retrievalStatus>;download:z.infer<typeof retrievalStatus>;search:z.infer<typeof retrievalResult>;rebuild:z.infer<typeof retrievalRebuild>;clear:z.infer<typeof retrievalClear>};
type SkillsResults={cancel:z.infer<typeof skillExecution>;history:z.infer<typeof skillHistory>;list:z.infer<typeof skillList>;enable:z.infer<typeof skillSummary>;preview_import:z.infer<typeof skillReview>;register:z.infer<typeof skillSummary>;plan:z.infer<typeof skillPlan>;execute:z.infer<typeof skillExecution>;execution:z.infer<typeof skillExecution>};
import { documentEvidenceSchema, documentPreviewSchema, browserEvidenceSchema, chatSnapshotSchema, chatListSchema, synthesisPreviewSchema, publicationPreviewSchema, developmentContextSchema, developmentDraftSchema, cleanupPlanSchema } from './chat-contracts';
import { m20StreamEventSchema, m20ScanPageSchema, streamPullInput, streamAckInput, type M20StreamEvent, type StreamPull } from './m20-contracts';

/** 仅传递后端固定错误码；正文可能含输入或供应商回显，禁止转发。 */
export class BackendRequestError extends Error {
  constructor(public readonly code: string) { super(`后端拒绝请求：${code}`); }
}
export class BackendConnectionError extends Error {
  constructor(public readonly code: 'BACKEND_TIMEOUT' | 'BACKEND_DISCONNECTED' | 'BACKEND_PROTOCOL', message: string) { super(message); }
}
import { configurationSchema, missionSchema, missionCreateSchema, grantStatusSchema, scanEnvelopeSchema, type MissionCreate, type GrantStatus, type ScanEnvelope } from './contracts';

type Secrets = Partial<Record<'main' | 'computer' | 'browser' | 'tavily' | 'redis', string>>;
type Initialization = { dataDirectory: string; credentials: () => Secrets };

type Pending = { resolve: (value: unknown) => void; reject: (reason: Error) => void; timer: NodeJS.Timeout; business?: {id:string;request_id:string} };
type BufferedStream = { events:M20StreamEvent[]; reorder:Map<number,M20StreamEvent>; recent:Map<number,string>; streamId:string; lastSeq:number; acked:number; delivered:number; terminal:boolean; finished:boolean; gapTimer?:NodeJS.Timeout };
const STREAM_EVENTS=80, STREAM_BYTES=128*1024, STREAM_PULL_BYTES=48*1024;

/** 开发使用固定虚拟环境，发布使用 ASAR 外的自带后端；失败不会回退系统 Python。 */
export class BackendClient {
  private child?: ChildProcessWithoutNullStreams;
  private pending = new Map<string, Pending>();
  private ready?: Promise<void>;
  private failed?: Error;
  private closing = false;
  private exited?: Promise<void>;
  private connected = false;
  private stopped?: Promise<void>;
  private streams=new Map<string,BufferedStream>();
  private streamBytes=0;
  private streamCount=0;
  private consumerWait?:{resolve:()=>void;reject:(error:Error)=>void;timer:NodeJS.Timeout};
  /** 只投影连接事实，不暴露子进程、路径或待处理请求内容。 */
  get connectionState(): 'ready' | 'starting' | 'disconnected' {
    return this.failed || this.closing ? 'disconnected' : this.connected ? 'ready' : 'starting';
  }
  constructor(private readonly root: string, private readonly timeoutMs = 5000, private readonly initialization?: Initialization, private readonly packaged?: PackagedRuntime) {}

  start(): Promise<void> {
    // 退出可能先于首次健康检查；阻止排队 IPC 在退出期间创建孤儿进程。
    if (this.failed || this.closing) return Promise.reject(this.failed ?? new Error('应用正在退出'));
    if (this.ready) return this.ready;
    const launch = backendLaunch(this.root, this.packaged);
    this.child = spawn(launch.executable, launch.args, {
      cwd: launch.cwd, shell: false, windowsHide: true, env: launch.env, stdio: 'pipe',
    });
    const lines = new JsonLines();
    this.exited = new Promise((resolve) => {
      this.child!.once('close', () => {
        this.fail(new BackendConnectionError('BACKEND_DISCONNECTED', '本地后端连接已关闭'));
        resolve();
      });
    });
    this.child.on('error', () => this.fail(new Error(this.packaged ? '安装包后端无法启动，请检查安装文件完整性' : '无法启动本地 Python 3.12 后端，请先按 README 安装环境')));
    this.child.stdin.on('error', () => this.fail(new Error('本地后端输入管道已关闭')));
    this.child.stdout.on('data', (chunk: Buffer) => {
      // 一次只解析一个Node输入块；有界事件队列满时保持pause，将背压传回Python管道。
      // 除128KiB队列外仅持有当前输入块与操作系统管道，不向renderer无限发送IPC。
      this.child!.stdout.pause();
      try {
        void this.consumeFrames(lines.push(chunk)).then(()=>{
          if(!this.failed&&!this.closing)this.child?.stdout.resume();
        }).catch(()=>this.fail(new BackendConnectionError('BACKEND_PROTOCOL','本地事件身份、顺序或消费预算无效；未自动重放')));
      } catch { this.fail(new BackendConnectionError('BACKEND_PROTOCOL', '本地后端协议无效或版本不兼容')); }
    });
    // 持续消费 stderr，避免管道堵塞；不把原始后端内容泄漏到 UI 或日志。
    this.child.stderr.on('data', () => {});
    this.ready = this.request('hello').then(async (value) => {
      try { helloSchema.parse(value); }
      catch { const error = new Error('后端协议或 Python 版本不兼容'); this.fail(error); throw error; }
      if (this.initialization) {
        // 敏感配置只经私有 stdio 发送，不放进命令行、环境变量或通用日志。
        z.object({ initialized: z.literal(true) }).strict().parse(await this.request('initialize', {
          data_directory: this.initialization.dataDirectory, credentials: this.initialization.credentials(),
        }));
      }
      this.connected = true;
    }).catch(() => {
      // 初始化失败后不留下仍运行但永远不可用的子进程，也不切换空白数据库。
      if (!this.failed) this.fail(new Error('本地后端初始化失败，请检查应用数据版本或重启'));
      throw this.failed!;
    });
    return this.ready;
  }

  /** 握手成功后才开放健康检查；连接失败不自动重放请求。 */
  async health() {
    await this.start();
    return healthSchema.parse(await this.request('health'));
  }

  async configuration() { await this.start(); return configurationSchema.parse(await this.request('configuration.status')); }
  /** 固定记忆方法族和响应预算；不暴露通用方法、来源或批准透传。 */
  async memory<M extends MemoryMethod>(method:M,params:object):Promise<MemoryResults[M]>{
    await this.start();
    const schemas={list:memoryList,context:memoryContext,preview:memoryPreview,generate:memoryList,search:memorySearch,correct:memoryList,forget:memoryList};
    return schemas[method].parse(await this.request(`memory.${method}`,params)) as MemoryResults[M];
  }
  async retrieval<M extends RetrievalMethod>(method:M,params:object):Promise<RetrievalResults[M]>{
    await this.start();const schemas={status:retrievalStatus,model:retrievalModel,prepare:retrievalStatus,activate:retrievalStatus,download:retrievalStatus,search:retrievalResult,rebuild:retrievalRebuild,clear:retrievalClear};
    return schemas[method].parse(await this.request(`retrieval.${method}`,params)) as RetrievalResults[M];
  }
  async skills<M extends SkillsMethod>(method:M,params:object):Promise<SkillsResults[M]>{
    await this.start();
    const schemas={cancel:skillExecution,history:skillHistory,list:skillList,enable:skillSummary,preview_import:skillReview,register:skillSummary,plan:skillPlan,execute:skillExecution,execution:skillExecution};
    return schemas[method].parse(await this.request(`skills.${method}`,params)) as SkillsResults[M];
  }
  async revokeComputer(mission_id:string){await this.start();return grantStatusSchema.parse(await this.request('computer.revoke',{mission_id}));}
  async auxiliaryStatus() { await this.start(); return auxiliaryStatus.parse(await this.request('auxiliary.status')); }
  async auxiliaryProbe() { await this.start(); return auxiliaryStatus.parse(await this.request('auxiliary.probe')); }
  async auxiliaryConfigure(config:AuxiliaryConfig) { await this.start(); return auxiliaryStatus.parse(await this.request('auxiliary.configure',config)); }
  async chatDeleteCheck(params:{id:string}) {await this.start();return z.object({id:z.string().uuid(),title:z.string(),blocked:z.boolean()}).strict().parse(await this.request('chat.delete_check',params));}
  async chatDelete(params:{id:string}) {
    await this.start();const result=z.object({id:z.string().uuid(),deleted:z.literal(true)}).strict().parse(await this.request('chat.delete',params));
    // 删除后同时释放主进程中尚未ACK的正文；其他会话的流继续保留。
    for(const [key,state] of this.streams){if(!key.startsWith(`${result.id}:`))continue;
      const events=[...state.events,...state.reorder.values()];
      this.streamBytes-=events.reduce((sum,event)=>sum+this.eventBytes(event),0);this.streamCount-=events.length;
      if(state.gapTimer)clearTimeout(state.gapTimer);this.streams.delete(key);
    }
    if(this.consumerWait){const waiting=this.consumerWait;this.consumerWait=undefined;clearTimeout(waiting.timer);waiting.resolve();}
    return result;
  }
  async chatList() { await this.start(); return chatListSchema.parse(await this.request('chat.list')); }
  async chatCancel(params: { id: string; request_id: string }) {
    await this.start();
    return z.object({ cancelled: z.boolean() }).strict().parse(await this.request('chat.cancel', params));
  }
  private async consumeFrames(values:unknown[]) {
    for(const value of values){
      if(typeof value==='object'&&value!==null&&'event' in value){
        const event=m20StreamEventSchema.parse(value);
        const pending=this.pending.get(event.id);
        if(!pending?.business||pending.business.id!==event.conversation_id||pending.business.request_id!==event.request_id)
          throw new Error('事件不属于活动请求');
        await this.bufferEvent(event);
        continue;
      }
      const response=responseSchema.parse(value);
      const pending=response.id?this.pending.get(response.id):undefined;
      if(!pending)throw new Error('响应ID不匹配');
      this.pending.delete(response.id!);clearTimeout(pending.timer);
      if(response.ok)pending.resolve(response.result);else pending.reject(new BackendRequestError(response.error.code));
    }
  }
  private streamKey(id:string,requestId:string){return `${id}:${requestId}`;}
  private eventBytes(event:M20StreamEvent){return Buffer.byteLength(JSON.stringify(event),'utf8');}
  private async bufferEvent(event:M20StreamEvent){
    const key=this.streamKey(event.conversation_id,event.request_id);
    let state=this.streams.get(key);
    if(!state){
      // 已ACK的旧终态只保留有限数量；waiting阶段保留序号供一次性continue核对。
      if(this.streams.size>=16){
        for(const [oldKey,old] of this.streams){
          if(old.finished&&old.events.length===0&&old.reorder.size===0){this.streams.delete(oldKey);break;}
        }
      }
      if(this.streams.size>=16)throw new Error('流身份预算已满');
      state={events:[],reorder:new Map(),recent:new Map(),streamId:event.stream_id,lastSeq:0,acked:0,delivered:0,terminal:false,finished:false};
      this.streams.set(key,state);
    }
    if(state.streamId!==event.stream_id)throw new Error('同请求流身份已变化');
    if(event.seq<=state.lastSeq){
      const prior=state.recent.get(event.seq);
      // ACK不意味着可以改变旧事实；仅在16项有界重复窗口内容忍相同事件。
      // 更早的帧停止连接，不为未知来源猜测、接续或自动重放。
      if(!prior||prior!==createHash('sha256').update(JSON.stringify(event)).digest('hex'))throw new Error('重复事件内容不一致或超出窗口');
      return;
    }
    if(state.reorder.has(event.seq)){
      if(JSON.stringify(state.reorder.get(event.seq))!==JSON.stringify(event))throw new Error('重复乱序事件不一致');
      return;
    }
    if(event.seq-state.lastSeq>16||state.reorder.size>=16)throw new Error('事件缺口超过有界重排预算');
    const bytes=this.eventBytes(event);
    while(this.streamCount>=STREAM_EVENTS||this.streamBytes+bytes>STREAM_BYTES){
      clearTimeout(state.gapTimer);state.gapTimer=undefined;
      await new Promise<void>((resolve,reject)=>{
        if(this.consumerWait){reject(new Error('并行消费等待无效'));return;}
        const timer=setTimeout(()=>{
          this.consumerWait=undefined;
          reject(new Error('流式消费超时'));
        },10000);
        this.consumerWait={resolve,reject,timer};
      });
      if(this.failed||this.closing)throw new Error('连接不可用');
    }
    this.streamBytes+=bytes;this.streamCount++;
    state.reorder.set(event.seq,event);
    while(state.reorder.has(state.lastSeq+1)){
      const next=state.reorder.get(state.lastSeq+1)!;state.reorder.delete(next.seq);
      state.events.push(next);state.lastSeq=next.seq;
      state.recent.set(next.seq,createHash('sha256').update(JSON.stringify(next)).digest('hex'));
      if(state.recent.size>16)state.recent.delete(state.recent.keys().next().value!);
      state.terminal=['paused','completed','failed','cancelled'].includes(next.kind);
      state.finished=['completed','failed','cancelled'].includes(next.kind);
    }
    if(state.reorder.size&&!state.gapTimer){
      state.gapTimer=setTimeout(()=>this.fail(new BackendConnectionError('BACKEND_PROTOCOL','流式事件序号缺口超时；请读取历史事实，未自动重发')),2000);
    }else if(!state.reorder.size&&state.gapTimer){clearTimeout(state.gapTimer);state.gapTimer=undefined;}
  }
  /** 只拉取本机已经收到的真实事件；不向后端重发任务或执行工具。 */
  streamPull(params:{id:string;request_id:string;after_seq:number;limit?:40}):StreamPull {
    const input=streamPullInput.parse(params),state=this.streams.get(this.streamKey(input.id,input.request_id));
    if(!state)return {events:[],last_seq:0,terminal:false,gap:false};
    const events:M20StreamEvent[]=[];
    for(const event of state.events){
      if(event.seq<=input.after_seq)continue;
      if(events.length>=40||Buffer.byteLength(JSON.stringify({events:[...events,event]}),'utf8')>STREAM_PULL_BYTES-512)break;
      events.push(event);
    }
    if(events.length)state.delivered=Math.max(state.delivered,events[events.length-1].seq);
    // 临时乱序尚未确认丢失，留给2秒有界重排；不让renderer提前误停正常流。
    return {events,last_seq:state.lastSeq,terminal:state.terminal,gap:input.after_seq<state.acked};
  }
  /** ACK只回收传输缓冲；不授予目录、正文发送、脚本或任何业务审批。 */
  streamAck(params:{id:string;request_id:string;seq:number}):{acked:boolean}{
    const input=streamAckInput.parse(params),state=this.streams.get(this.streamKey(input.id,input.request_id));
    if(!state||input.seq>state.delivered||input.seq<state.acked)return {acked:false};
    const removed=state.events.filter(event=>event.seq<=input.seq);
    this.streamBytes-=removed.reduce((total,event)=>total+this.eventBytes(event),0);this.streamCount-=removed.length;
    state.events=state.events.filter(event=>event.seq>input.seq);state.acked=input.seq;
    if(this.consumerWait){const waiting=this.consumerWait;this.consumerWait=undefined;clearTimeout(waiting.timer);waiting.resolve();}
    return {acked:true};
  }
  async scanPage(params:{id:string;scan_id:string;offset?:number}){
    await this.start();return m20ScanPageSchema.parse(await this.request('chat.scan.page',params));
  }
  /** 方法名仅供主进程固定业务入口使用；preload 不暴露此分发器。 */
  async chatSource(params: {id:string;evidence_id:string}) {
    await this.start(); return browserEvidenceSchema.parse(await this.request('chat.browser.source',params));
  }
  async chatDocumentSource(params: {id:string;evidence_id:string}) {
    await this.start();return documentEvidenceSchema.parse(await this.request('chat.document.source',params));
  }
  async chatDocumentPreview(params: {id:string;evidence_id:string;format:'md'|'json'}) {
    await this.start();return documentPreviewSchema.parse(await this.request('chat.document.preview',params));
  }
  async chatSynthesisPreview(params:{id:string;mode:'summary'|'answer';question:string;sources:{kind:'document'|'browser';evidence_id:string}[]}) {
    await this.start();return synthesisPreviewSchema.parse(await this.request('chat.synthesis.preview',params));
  }
  async chatPublicationPreview(params:object) {
    await this.start();return publicationPreviewSchema.parse(await this.request('chat.publication.preview',params));
  }
  async developmentContext(params:object) { await this.start();return developmentContextSchema.parse(await this.request('chat.development.context',params)); }
  async developmentGenerate(params:object) { await this.start();return developmentDraftSchema.parse(await this.request('chat.development.generate',params)); }
  async developmentDraft(params:object) { await this.start();return developmentDraftSchema.parse(await this.request('chat.development.draft',params)); }
  async developmentApply(params:object) { await this.start();return z.object({path:z.string(),bytes:z.number(),verified:z.literal(true),draft_id:z.string().uuid(),remaining:z.number()}).parse(await this.request('chat.development.apply',params)); }
  async cleanupScan(params:object) { await this.start();return cleanupPlanSchema.parse(await this.request('chat.cleanup.scan',params)); }
  async cleanupPlan(params:object) { await this.start();return cleanupPlanSchema.parse(await this.request('chat.cleanup.plan',params)); }
  async cleanupExecute(params:object) { await this.start();return cleanupPlanSchema.parse(await this.request('chat.cleanup.execute',params)); }
  async cleanupRestore(params:object) { await this.start();return cleanupPlanSchema.parse(await this.request('chat.cleanup.restore',params)); }
  /** 仅主进程固定 handler 使用，preload 不暴露方法名转发器。 */
  async automation(suffix: string, params: object): Promise<unknown> {
    const allowed=['script.preview','script.file','script.model_preview','script.model_generate','script.execute','script.status','script.export',
      'desktop.windows','desktop.grant','desktop.observe','desktop.preview','desktop.execute',
      'browser.open','browser.observe','browser.pending','browser.preview','browser.execute','browser.request','browser.origin','browser.close','cancel','history'];
    if(!allowed.includes(suffix))throw new BackendRequestError('METHOD_NOT_FOUND');
    await this.start();return this.request(`chat.automation.${suffix}`,params);
  }
  async chat(method: 'chat.rename' | 'chat.pin' | 'chat.create' | 'chat.get' | 'chat.send' | 'chat.natural' | 'chat.continue' | 'chat.fallback.confirm' | 'chat.material.remove' | 'chat.revoke' | 'chat.grant' | 'chat.inspect' | 'chat.browser.search' | 'chat.browser.read' | 'chat.browser.ask' | 'chat.document.attach' | 'chat.document.ask' | 'chat.document.export' | 'chat.synthesis.generate' | 'chat.publication.save' | 'chat.approve' | 'chat.resume' | 'chat.undo', params: object) {
    await this.start(); return chatSnapshotSchema.parse(await this.request(method, params));
  }
  async missions() { await this.start(); return z.object({ missions: z.array(missionSchema) }).strict().parse(await this.request('missions.list')); }
  async createMission(input: MissionCreate) { await this.start(); return missionSchema.parse(await this.request('missions.create', missionCreateSchema.parse(input))); }
  async getMission(id: string) { await this.start(); return missionSchema.parse(await this.request('missions.get', { id: z.string().uuid().parse(id) })); }
  async grantComputer(input: { mission_id: string; root: string }) {
    await this.start();
    return grantStatusSchema.parse(await this.request('computer.grant', { mission_id: z.string().uuid().parse(input.mission_id), root: input.root, allow_text: false, allow_system: false }));
  }
  async computerStatus(missionId: string) { await this.start(); return grantStatusSchema.parse(await this.request('computer.status', { mission_id: z.string().uuid().parse(missionId) })); }
  async executeComputer(input: { mission_id: string; grant_id: string; call: object }): Promise<ScanEnvelope> {
    await this.start();
    return scanEnvelopeSchema.parse(await this.request('computer.execute', { mission_id: z.string().uuid().parse(input.mission_id), grant_id: z.string().uuid().parse(input.grant_id), call: input.call }));
  }
  /** 凭据变更不改变已保存 Mission 的模型快照。 */
  async replaceCredentials(credentials: Secrets) { await this.start(); return z.object({ updated: z.literal(true) }).strict().parse(await this.request('credentials.replace', { credentials })); }

  private request(method: `memory.${MemoryMethod}` | `retrieval.${RetrievalMethod}` | 'computer.revoke' | `skills.${SkillsMethod}` | 'auxiliary.status' | 'auxiliary.configure' | 'auxiliary.probe' | 'chat.rename' | 'chat.pin' | 'chat.delete' | 'chat.delete_check' | 'hello' | 'health' | 'initialize' | 'configuration.status' | 'missions.list' | 'missions.create' | 'missions.get' | 'credentials.replace' | 'computer.grant' | 'computer.status' | 'computer.execute' | 'chat.list' | 'chat.create' | 'chat.get' | 'chat.send' | 'chat.natural' | 'chat.continue' | 'chat.fallback.confirm' | 'chat.material.remove' | 'chat.revoke' | 'chat.scan.page' | 'chat.grant' | 'chat.inspect' | 'chat.browser.search' | 'chat.browser.read' | 'chat.browser.ask' | 'chat.document.attach' | 'chat.document.ask' | 'chat.document.export' | 'chat.synthesis.preview' | 'chat.synthesis.generate' | 'chat.publication.preview' | 'chat.publication.save' | 'chat.development.context' | 'chat.development.generate' | 'chat.development.draft' | 'chat.development.apply' | 'chat.cleanup.scan' | 'chat.cleanup.plan' | 'chat.cleanup.execute' | 'chat.cleanup.restore' | 'chat.browser.source' | 'chat.document.source' | 'chat.document.preview' | 'chat.approve' | 'chat.resume' | 'chat.undo' | 'chat.cancel' | `chat.automation.${string}`, params: object = {}): Promise<unknown> {
    if (this.failed) return Promise.reject(this.failed);
    if (this.closing || !this.child) return Promise.reject(new Error('后端不可用'));
    if (this.pending.size >= 16) return Promise.reject(new Error('健康检查请求过于频繁'));
    const id = randomUUID();
    const payload=JSON.stringify({v:VERSION,id,method,params})+'\n';
    // 先按最终JSON字节预算拒绝，避免32KiB源码经转义放大而让后端失去响应身份。
    if(Buffer.byteLength(payload,'utf8')>MAX_LINE_BYTES)return Promise.reject(new BackendRequestError('OUTPUT_LIMIT'));
    return new Promise((resolve, reject) => {
      // Main 单轮有50秒总预算；会话请求额外留出持久化与协议返回时间。
      // 完整M15–M20冷启动加载锁定解析/隔离依赖，给握手和初始化独立20秒。
      // 健康检查保留短期限；这只等待自有进程，不延长模型预算或自动重启。
      const timeout=method==='retrieval.download'?1100000:method.startsWith('retrieval.')?190000:method.startsWith('memory.')?45000:method.startsWith('skills.')?15000:method.startsWith('chat.')?65000:['hello','initialize'].includes(method)?Math.max(this.timeoutMs,20000):this.timeoutMs;
      const timer = setTimeout(() => this.fail(new BackendConnectionError('BACKEND_TIMEOUT', '本地后端响应超时')),timeout);
      const business=params as {id?:unknown;request_id?:unknown};
      this.pending.set(id, { resolve, reject, timer,...(typeof business.id==='string'&&typeof business.request_id==='string'?{business:{id:business.id,request_id:business.request_id}}:{}) });
      this.child!.stdin.write(payload);
    });
  }

  private fail(error: Error) {
    this.failed ??= error;
    for (const pending of this.pending.values()) { clearTimeout(pending.timer); pending.reject(this.failed); }
    this.pending.clear();
    for(const stream of this.streams.values())clearTimeout(stream.gapTimer);
    this.streams.clear();this.streamBytes=0;this.streamCount=0;
    if(this.consumerWait){const waiting=this.consumerWait;this.consumerWait=undefined;clearTimeout(waiting.timer);waiting.reject(this.failed);}
    if (!this.closing) this.child?.kill();
  }

  /** 退出先发送 EOF，超时才终止本应用拥有的子进程。 */
  stop(): Promise<void> {
    // 重连、窗口关闭和凭据失败可能同时收尾；只关闭一次，且必须确认旧进程退出。
    return this.stopped ??= this.stopOwnedProcess();
  }

  private async stopOwnedProcess() {
    this.closing = true;
    this.fail(new Error('应用正在退出'));
    this.child?.stdin.end();
    if (!this.exited) return;
    const timer = setTimeout(() => this.child?.kill(), 1500);
    let deadline: NodeJS.Timeout | undefined;
    try {
      await Promise.race([this.exited, new Promise<never>((_, reject) => {
        deadline = setTimeout(() => reject(new Error('旧后端尚未确认退出，拒绝启动第二个后端')), 4000);
      })]);
    } finally { clearTimeout(timer); clearTimeout(deadline); }
  }
}
