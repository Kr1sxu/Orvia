import {beforeEach,afterEach,describe,it,expect,vi} from 'vitest';
import {randomUUID} from 'node:crypto';
import {promises as fs} from 'node:fs';
import path from 'node:path';
import type {BackendClient} from '../src/main/backend';
import type {BrowserWindow} from 'electron';
import type {SafeStorageAdapter} from '../src/main/credentials';
const native=vi.hoisted(()=>({message:vi.fn(),open:vi.fn()}));
vi.mock('electron',()=>({dialog:{showMessageBox:native.message,showOpenDialog:native.open}}));
import {registerMcp} from '../src/main/mcp-ipc';
import {McpCredentialVault} from '../src/main/mcp-credentials';
import {mcpServerInput,mcpApprovalInput,mcpHistoryInput,mcpCallInput,mcpCallApprovalInput,mcpCredentialInput,mcpConfig,mcpToolReview,mcpExecution,mcpHistory} from '../src/main/mcp-contracts';

const cid=randomUUID(),sid=randomUUID(),revision='a'.repeat(64),session=randomUUID();
const config={name:'合成只读服务',transport:'stdio',executable:'C:\\synthetic\\reader.exe',args:['synthetic.py'],allowed_tools:['get_text','delete_file']};
const summary={id:sid,name:config.name,transport:'stdio',revision,status:'configured',tools_count:2,blocked_count:1,reason:null,credential_configured:false};
const connectPreview={server_id:sid,revision,config,identity:{executable_hash:'b'.repeat(64),cwd:null,args_files:[{path:'C:\\synthetic\\synthetic.py',sha256:'c'.repeat(64),bytes:24}]},credential_configured:false,purpose:'连接并发现 MCP 工具'};
const metadata={name:'get_text',inputSchema:{type:'object',properties:{query:{type:'string'}},required:['query'],additionalProperties:false},annotations:{readOnlyHint:true}};
const toolReview={server_id:sid,revision,server_revision:revision,session_id:session,server_info:{name:'合成程序',version:'1'},capabilities:{tools:{}},tools:[{name:'get_text',metadata,allowed:true,blocked_reason:null},{name:'delete_file',metadata:{inputSchema:{type:'object'}},allowed:false,blocked_reason:'危险工具名称'}]};
const request={id:cid,server_id:sid,tool:'get_text',arguments:{query:'合成问题'}};
const callPreview={...request,revision,server_revision:revision,session_id:session,server_name:config.name,metadata,purpose:'调用已审查的只读 MCP 工具'};
const execution={id:cid,server_id:sid,revision,server_name:config.name,tool:'get_text',status:'completed',result:{content:[{type:'resource_link',uri:'file:///synthetic/private.txt',name:'纯文本资源定位'}]},error:null};
let userData:string,adapter:SafeStorageAdapter;
beforeEach(async()=>{
  vi.clearAllMocks();native.message.mockResolvedValue({response:1});native.open.mockResolvedValue({canceled:false,filePaths:['C:\\synthetic\\mcp.json']});
  const root=path.resolve('artifacts/test-results/V4-007');await fs.mkdir(root,{recursive:true});userData=await fs.mkdtemp(path.join(root,'credential-'));
  // 仅模拟safeStorage算法；真实临时加密文件/原子替换，不证明本机DPAPI可用。
  adapter={isEncryptionAvailable:vi.fn(()=>true),encryptString:vi.fn(value=>Buffer.from('synthetic:'+value)),decryptString:vi.fn(value=>{if(!value.toString().startsWith('synthetic:'))throw Error('synthetic-secret-raw-error');return value.toString().slice(10);})};
});
afterEach(()=>vi.restoreAllMocks());
function vault(){return new McpCredentialVault({userData,safeStorage:adapter});}
function context(result:(method:string,params:Record<string,unknown>)=>unknown=(method)=>({list:{servers:[summary]},preview_config:{review_id:randomUUID(),revision,config},configure:summary,connect_preview:connectPreview,connect:toolReview,approve_tools:{...summary,status:'ready'},call_preview:callPreview,call:execution,history:{executions:[execution]},disconnect:{server_id:sid,closed:true,children_reaped:true},remove:{server_id:sid,removed:true},credential_replace:summary}[method])){
  const handlers=new Map<string,(...args:unknown[])=>Promise<unknown>>(),store=vault();
  const mcp=vi.fn(async(method:string,params:Record<string,unknown>)=>result(method,params));
  const authorization=registerMcp({handle:(channel,_count,fn)=>handlers.set(channel,fn),serial:async fn=>fn(),window:()=>({} as BrowserWindow),backend:()=>({mcp} as unknown as BackendClient),vault:()=>store});
  return{mcp,store,authorization,invoke:(method:string,params?:unknown)=>handlers.get(`orvia:mcp-${method}`)!(...(params===undefined?[]:[params]))};
}

describe('V4-007原生配置、工具审查与一次调用许可',()=>{
  it('renderer只准固定服务/会话/工具/参数字段，拒绝路径、URL、任意method、schema与批准',()=>{
    for(const [schema,input] of [[mcpServerInput,{server_id:sid}],[mcpApprovalInput,{server_id:sid,revision}],[mcpHistoryInput,{id:cid}],[mcpCallInput,request],[mcpCallApprovalInput,{id:cid,server_id:sid,revision}],[mcpCredentialInput,{server_id:sid,key:'synthetic-bearer'}]] as const){
      expect(schema.safeParse(input).success).toBe(true);
      for(const extra of [{path:'C:/private'},{url:'https://other.invalid'},{executable:'other.exe'},{method:'tools/write'},{schema:{}},{approved:true},{grant:'network'}])expect(schema.safeParse({...input,...extra}).success).toBe(false);
    }
  });
  it('配置禁止env/Key/userinfo/query/fragment，参数限制UTF8并拒绝非JSON及非有限数字',()=>{
    expect(mcpConfig.safeParse(config).success).toBe(true);
    expect(mcpConfig.safeParse({...config,env:{DEEPSEEK_API_KEY:'synthetic'}}).success).toBe(false);
    for(const url of ['http://example.invalid/mcp','https://name:token@example.invalid/mcp','https://example.invalid/mcp?key=token','https://example.invalid/mcp#secret'])expect(mcpConfig.safeParse({name:'合成',transport:'https',url,allowed_tools:['get_text']}).success).toBe(false);
    for(const argumentsValue of [{value:NaN},{value:Infinity},{value:()=>1},{value:undefined},{value:'汉'.repeat(3000)}])expect(mcpCallInput.safeParse({...request,arguments:argumentsValue}).success).toBe(false);
    expect(mcpCallInput.safeParse({...request,arguments:{value:'汉'.repeat(2000)}}).success).toBe(true);
  });
  it('完整工具与结果结构总预算受限，URI是纯数据字段，不转成权限',()=>{
    expect(mcpExecution.safeParse(execution).success).toBe(true);
    expect(mcpExecution.safeParse({...execution,grant:'file'}).success).toBe(false);
    expect(mcpToolReview.safeParse({...toolReview,tools:Array.from({length:32},()=>({...toolReview.tools[0],metadata:{body:'汉'.repeat(500)}}))}).success).toBe(false);
    expect(mcpHistory.safeParse({executions:Array.from({length:17},()=>execution)}).success).toBe(false);
  });
  it('原生配置或连接取消不登记、启动或请求服务',async()=>{
    const c=context();native.message.mockResolvedValue({response:0});expect(await c.invoke('import')).toEqual({cancelled:true});expect(c.mcp.mock.calls.map(call=>call[0])).toEqual(['preview_config']);
    c.mcp.mockClear();expect(await c.invoke('connect',{server_id:sid})).toEqual({cancelled:true});expect(c.mcp.mock.calls.map(call=>call[0])).toEqual(['connect_preview']);
    const detail=native.message.mock.calls.at(-1)![1].detail;expect(detail).toContain(JSON.stringify(config.executable));expect(detail).toContain(connectPreview.identity.args_files[0]!.sha256);expect(detail).toContain('当前用户权限');
  });
  it('准确工具清单独立审批，取消不allowlist批准，旧清单不重用',async()=>{
    const c=context();await expect(c.invoke('approve-tools',{server_id:sid,revision})).rejects.toThrow();await c.invoke('connect',{server_id:sid});native.message.mockResolvedValue({response:0});
    expect(await c.invoke('approve-tools',{server_id:sid,revision})).toEqual({cancelled:true});await expect(c.invoke('approve-tools',{server_id:sid,revision})).rejects.toThrow();
    expect(c.mcp.mock.calls.map(call=>call[0])).toEqual(['connect_preview','connect']);const detail=native.message.mock.calls.at(-1)![1].detail;expect(detail).toContain('delete_file');expect(detail).toContain('危险工具名称');expect(detail).toContain('不能证明');
  });
  it('调用取消零tools/call，完整preview变化即使revision相同也拒绝',async()=>{
    const c=context();await c.invoke('call-preview',request);native.message.mockResolvedValue({response:0});expect(await c.invoke('call',{id:cid,server_id:sid,revision})).toEqual({cancelled:true});expect(c.mcp.mock.calls.map(call=>call[0])).toEqual(['call_preview','call_preview']);
    let changed=false;const d=context(method=>method==='call_preview'&&changed?{...callPreview,session_id:randomUUID()}:callPreview);await d.invoke('call-preview',request);changed=true;
    await expect(d.invoke('call',{id:cid,server_id:sid,revision})).rejects.toThrow();expect(d.mcp.mock.calls.map(call=>call[0])).toEqual(['call_preview','call_preview']);
  });
  it('批准仅调用一次，未知结果或原生窗口异常不会重用旧许可',async()=>{
    const c=context(method=>{if(method==='call')throw Error('synthetic unknown');return callPreview;});await c.invoke('call-preview',request);await expect(c.invoke('call',{id:cid,server_id:sid,revision})).rejects.toThrow('synthetic unknown');await expect(c.invoke('call',{id:cid,server_id:sid,revision})).rejects.toThrow();expect(c.mcp.mock.calls.map(call=>call[0])).toEqual(['call_preview','call_preview','call']);
    const d=context();await d.invoke('call-preview',request);native.message.mockRejectedValueOnce(Error('synthetic native unknown'));await expect(d.invoke('call',{id:cid,server_id:sid,revision})).rejects.toThrow();await expect(d.invoke('call',{id:cid,server_id:sid,revision})).rejects.toThrow();expect(d.mcp.mock.calls.map(call=>call[0])).toEqual(['call_preview','call_preview']);
  });
  it('断开和重连清除调用许可；对象参数键顺序不影响准确内容校验',async()=>{
    const c=context(method=>method==='call_preview'?{...callPreview,arguments:{a:1,b:2}}:{server_id:sid,closed:true,children_reaped:true});await c.invoke('call-preview',{...request,arguments:{b:2,a:1}});await c.invoke('disconnect',{server_id:sid});await expect(c.invoke('call',{id:cid,server_id:sid,revision})).rejects.toThrow();
    const d=context();await d.invoke('call-preview',request);d.authorization.clear();await expect(d.invoke('call',{id:cid,server_id:sid,revision})).rejects.toThrow();
  });
  it('程序丢失或远端不可用仍能原生移除本机配置，不尝试连接',async()=>{
    const c=context(method=>{if(method==='connect_preview'||method==='connect')throw Error('synthetic missing executable');return method==='list'?{servers:[summary]}:method==='disconnect'?{server_id:sid,closed:true,children_reaped:true}:{server_id:sid,removed:true};});await c.store.load();
    expect(await c.invoke('remove',{server_id:sid})).toEqual({cancelled:false,result:{server_id:sid,removed:true}});expect(c.mcp.mock.calls.map(call=>call[0])).toEqual(['list','disconnect','remove']);
  });
  it('保存专用凭据显示准确接收方且不显示令牌，更新先断开再私有替换，撤回旧调用批准',async()=>{
    const https={...connectPreview,config:{name:'合成HTTPS',transport:'https',url:'https://example.invalid/mcp',allowed_tools:['get_text']}};
    const c=context(method=>method==='connect_preview'?https:method==='call_preview'?callPreview:summary);await c.store.load();await c.invoke('call-preview',request);await c.invoke('credential-save',{server_id:sid,key:'synthetic-private-bearer'});
    expect(c.mcp.mock.calls.map(call=>call[0])).toEqual(['call_preview','connect_preview','disconnect','credential_replace']);expect(c.mcp).toHaveBeenLastCalledWith('credential_replace',{server_id:sid,credential:'synthetic-private-bearer'});
    const detail=native.message.mock.calls.at(-1)![1].detail;expect(detail).toContain('https://example.invalid/mcp');expect(detail).not.toContain('synthetic-private-bearer');await expect(c.invoke('call',{id:cid,server_id:sid,revision})).rejects.toThrow();
    native.message.mockResolvedValue({response:0});const before=c.mcp.mock.calls.length;expect(await c.invoke('credential-save',{server_id:sid,key:'synthetic-cancelled'})).toEqual({cancelled:true});expect(c.mcp.mock.calls.length).toBe(before+1);expect(c.store.get(sid)).toBe('synthetic-private-bearer');
  });
  it('远端离线仍能原生移除本机令牌，准确服务身份可见且令牌不出现',async()=>{
    const c=context(method=>{if(method==='connect_preview'||method==='connect')throw Error('synthetic offline');return method==='list'?{servers:[{...summary,transport:'https',credential_configured:true}]}:summary;});await c.store.load();await c.store.save(sid,'synthetic-removable');
    expect(await c.invoke('credential-remove',{server_id:sid})).toMatchObject({cancelled:false});expect(c.store.get(sid)).toBeUndefined();expect(c.mcp.mock.calls.map(call=>call[0])).toEqual(['list','disconnect','credential_replace']);expect(c.mcp).toHaveBeenLastCalledWith('credential_replace',{server_id:sid,credential:null});
    const detail=native.message.mock.calls.at(-1)![1].detail;expect(detail).toContain(sid);expect(detail).toContain(config.name);expect(detail).not.toContain('synthetic-removable');
  });
  it('调用预览拒绝错会话或篡改参数，八个许可有界且淘汰旧预览',async()=>{
    const wrong=context(()=>({...callPreview,id:randomUUID()}));await expect(wrong.invoke('call-preview',request)).rejects.toThrow();await expect(wrong.invoke('call',{id:cid,server_id:sid,revision})).rejects.toThrow();
    const changed=context(()=>({...callPreview,arguments:{query:'其它参数'}}));await expect(changed.invoke('call-preview',request)).rejects.toThrow();
    const c=context((_method,params)=>({...callPreview,id:params.id,server_id:params.server_id}));await c.invoke('call-preview',request);for(let index=0;index<8;index++)await c.invoke('call-preview',{...request,id:randomUUID()});await expect(c.invoke('call',{id:cid,server_id:sid,revision})).rejects.toThrow();expect(native.message).not.toHaveBeenCalled();
  });
  it('未知深层、循环、非安全数值和无效Unicode参数在backend调用前拒绝',async()=>{
    let deep:unknown='x';for(let i=0;i<30;i++)deep={child:deep};const cyclic:Record<string,unknown>={};cyclic.self=cyclic;
    const c=context();for(const value of [deep,cyclic,Number.MAX_SAFE_INTEGER+1,'\ud800'])await expect(c.invoke('call-preview',{...request,arguments:{value}})).rejects.toThrow();await expect(c.invoke('call-preview',{...request,arguments:Object.fromEntries(Array.from({length:129},(_,i)=>['key'+i,0]))})).rejects.toThrow();expect(c.mcp).not.toHaveBeenCalled();
    expect(mcpConfig.safeParse({...config,executable:'C:/synthetic/reader.exe'}).success).toBe(true);
  });
});

describe('V4-007专用safeStorage仓库（模拟算法，真实文件）',()=>{
  it('加密保存/重载/删除，只公开服务身份，副本修改不能改变内存',async()=>{
    const store=vault();await store.load();await store.save(sid,'synthetic-private-bearer');const body=await fs.readFile(path.join(userData,'mcp-credentials.enc.json'),'utf8');expect(body).not.toContain('synthetic-private-bearer');expect(JSON.stringify(store.getStatus())).not.toContain('synthetic-private-bearer');
    const copy=store.getSecrets();copy[sid]='modified';expect(store.get(sid)).toBe('synthetic-private-bearer');const next=vault();await next.load();expect(next.get(sid)).toBe('synthetic-private-bearer');await next.remove(sid);const final=vault();await final.load();expect(final.getSecrets()).toEqual({});
  });
  it('safeStorage不可用时无文件仍允许匿名，保存严格拒绝且不创建明文回退',async()=>{
    vi.mocked(adapter.isEncryptionAvailable).mockReturnValue(false);const store=vault();await store.load();expect(store.getStatus()).toEqual({encryption_available:false,configured:[],loaded:true});await expect(store.save(sid,'synthetic')).rejects.toThrow('ENCRYPTION_UNAVAILABLE');expect(await fs.readdir(userData)).toEqual([]);
  });
  it('损坏文件锁定不覆盖，解密底层错误与原令牌不会出现在错误里',async()=>{
    const file=path.join(userData,'mcp-credentials.enc.json'),body=JSON.stringify({[sid]:'YQ=='});await fs.writeFile(file,body);const store=vault();await expect(store.load()).rejects.toThrow('MCP_CREDENTIAL_CORRUPT');await expect(store.save(sid,'replacement')).rejects.toThrow('NOT_LOADED');await expect(store.remove(sid)).rejects.toThrow('NOT_LOADED');expect(await fs.readFile(file,'utf8')).toBe(body);expect(store.getStatus().loaded).toBe(false);
  });
  it('原子替换失败保留磁盘/内存并清理加密临时文件，不泄露底层错误',async()=>{
    const store=vault();await store.load();await store.save(sid,'synthetic-old');const body=await fs.readFile(path.join(userData,'mcp-credentials.enc.json'),'utf8');vi.spyOn(fs,'rename').mockRejectedValueOnce(Error('synthetic-new-secret-raw-error'));
    await expect(store.save(sid,'synthetic-new')).rejects.toThrow('MCP_CREDENTIAL_WRITE_FAILED: 服务凭据保存失败，原状态保留');expect(store.get(sid)).toBe('synthetic-old');expect(await fs.readFile(path.join(userData,'mcp-credentials.enc.json'),'utf8')).toBe(body);expect(await fs.readdir(userData)).toEqual(['mcp-credentials.enc.json']);
  });
  it('最多五个独立服务；并发保存不丢更新；拒绝空白/Unicode/control令牌',async()=>{
    const store=vault();await store.load();const ids=Array.from({length:5},()=>randomUUID());await Promise.all(ids.map((id,index)=>store.save(id,'synthetic-'+index)));expect(Object.keys(store.getSecrets())).toHaveLength(5);await expect(store.save(randomUUID(),'synthetic-extra')).rejects.toThrow('MCP_CREDENTIAL_LIMIT');
    for(const key of ['', 'a b', '汉', 'a\nb', 'a\x00b', 'x'.repeat(4097)]){expect(mcpCredentialInput.safeParse({server_id:sid,key}).success).toBe(false);await expect(store.save(ids[0]!,key)).rejects.toThrow('MCP_CREDENTIAL_INVALID');}
  });
});
