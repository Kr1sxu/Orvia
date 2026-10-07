import {promises as fs} from 'node:fs';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import type {SafeStorageAdapter} from './credentials';

const identity=/^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
const valid=(value:unknown):value is string=>typeof value==='string'&&/^[\x21-\x7e]{1,4096}$/.test(value);
type Secrets=Record<string,string>;

/** MCP令牌只在主进程内存和系统加密文件中保存；开发模式也不读取.env或角色密钥。 */
export class McpCredentialVault{
  private secrets:Secrets={};
  private loaded=false;
  private pending:Promise<void>=Promise.resolve();
  constructor(private readonly options:{userData:string;safeStorage:SafeStorageAdapter}){}
  private get filename(){return path.join(this.options.userData,'mcp-credentials.enc.json');}
  private serial(action:()=>Promise<void>){const operation=this.pending.then(action);this.pending=operation.catch(()=>undefined);return operation;}
  private requireEncryption(){if(!this.options.safeStorage.isEncryptionAvailable())throw new Error('MCP_CREDENTIAL_ENCRYPTION_UNAVAILABLE: 系统安全存储不可用，无法保存服务令牌');}

  /** 文件损坏或解密失败保持锁定，后续save/remove均不能覆盖原文件；无凭据仍可匿名连接。 */
  load():Promise<void>{return this.serial(async()=>{
    this.loaded=false;this.secrets={};
    let content:string;
    try{const stat=await fs.stat(this.filename);if(!stat.isFile()||stat.size>256*1024)throw new Error('invalid');content=await fs.readFile(this.filename,'utf8');}
    catch(error){if((error as NodeJS.ErrnoException).code==='ENOENT'){this.loaded=true;return;}throw new Error('MCP_CREDENTIAL_READ_FAILED: 无法安全读取服务凭据');}
    this.requireEncryption();
    const next:Secrets={};
    try{
      const parsed:unknown=JSON.parse(content);if(!parsed||typeof parsed!=='object'||Array.isArray(parsed)||Object.keys(parsed).length>5||Buffer.byteLength(content)>256*1024)throw new Error('invalid');
      for(const [id,cipher] of Object.entries(parsed)){
        if(!identity.test(id)||typeof cipher!=='string'||!cipher||cipher.length>44*1024||Buffer.from(cipher,'base64').toString('base64')!==cipher)throw new Error('invalid');
        const value=this.options.safeStorage.decryptString(Buffer.from(cipher,'base64'));if(!valid(value))throw new Error('invalid');next[id]=value;
      }
    }catch{throw new Error('MCP_CREDENTIAL_CORRUPT: 服务凭据损坏或无法解密，保留原文件');}
    this.secrets=next;this.loaded=true;
  });}

  /** 仅供主进程的私有初始化/替换管道；禁止返回renderer或记录令牌片段。 */
  getSecrets():Secrets{return {...this.secrets};}
  get(id:string):string|undefined{return this.secrets[id];}
  getStatus(){return {encryption_available:this.options.safeStorage.isEncryptionAvailable(),configured:Object.keys(this.secrets),loaded:this.loaded};}
  save(id:string,key:string):Promise<void>{return this.change(id,key);}
  remove(id:string):Promise<void>{return this.change(id,undefined);}

  /** 串行原子加密替换成功后才更改内存；失败仅清理本次加密临时文件，不输出底层错误。 */
  private change(id:string,key:string|undefined):Promise<void>{return this.serial(async()=>{
    if(!this.loaded)throw new Error('MCP_CREDENTIAL_NOT_LOADED: 请先成功加载服务凭据');
    if(!identity.test(id)||(key!==undefined&&!valid(key)))throw new Error('MCP_CREDENTIAL_INVALID: 服务身份或单行令牌无效');
    this.requireEncryption();const next={...this.secrets};if(key===undefined)delete next[id];else next[id]=key;
    if(Object.keys(next).length>5)throw new Error('MCP_CREDENTIAL_LIMIT: 最多保存五个服务的令牌');
    const temporary=this.filename+'.'+randomUUID()+'.tmp';
    try{
      const encrypted:Record<string,string>={};
      for(const [sid,value] of Object.entries(next)){const cipher=this.options.safeStorage.encryptString(value);if(!Buffer.isBuffer(cipher)||!cipher.length||cipher.length>32*1024)throw new Error('invalid');encrypted[sid]=cipher.toString('base64');}
      const body=JSON.stringify(encrypted);if(Buffer.byteLength(body)>256*1024)throw new Error('invalid');
      await fs.mkdir(this.options.userData,{recursive:true});await fs.writeFile(temporary,body,{encoding:'utf8',mode:0o600,flag:'wx'});await fs.rename(temporary,this.filename);
    }catch{await fs.unlink(temporary).catch(()=>undefined);throw new Error('MCP_CREDENTIAL_WRITE_FAILED: 服务凭据保存失败，原状态保留');}
    this.secrets=next;
  });}
}
