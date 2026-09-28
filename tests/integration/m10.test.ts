import {expect,it} from 'vitest';
import {mkdir,mkdtemp,writeFile,readFile} from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {BackendClient,BackendRequestError} from '../../apps/desktop/src/main/backend';

it('M10 真实Python/SQLite快照与TypeScript契约匹配（无模型调用）',async()=>{
  const results=path.resolve('artifacts/test-results/M10');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'stdio-'));
  const root=path.join(work,'files');await mkdir(root);await writeFile(path.join(root,'合成.txt'),'synthetic');
  const backend=new BackendClient(process.cwd(),5000,{dataDirectory:path.join(work,'db'),credentials:()=>({})});
  let id='';
  try {
    const create={client_request_id:randomUUID(),title:'M10 stdio synthetic'};
    const conversation=await backend.chat('chat.create',create);id=conversation.id;
    expect(await backend.chat('chat.create',create)).toEqual(conversation);
    expect((await backend.chatList()).conversations).toContainEqual({id,title:create.title});
    expect((await backend.chat('chat.grant',{id,root})).grant?.root_label).toBe('files');
    const scan=await backend.chat('chat.inspect',{id,tool:'list_directory',arguments:{path:'.',limit:100}});
    expect(scan.messages.at(-1)?.kind).toBe('scan');
    expect(JSON.stringify(scan)).not.toContain(root);
    const missing=await backend.chat('chat.send',{id,request_id:randomUUID(),text:'合成只读查询'});
    expect(missing.messages.at(-1)?.data?.code).toBe('MISSING_CREDENTIAL');
    await expect(backend.chat('chat.inspect',{id,tool:'get_file_metadata',arguments:{path:'../outside'}})).rejects.toBeInstanceOf(BackendRequestError);
    await expect(backend.chat('chat.inspect',{id,tool:'run_readonly_template',arguments:{}})).rejects.toThrow();
    expect(await readFile(path.join(root,'合成.txt'),'utf8')).toBe('synthetic');
  }finally{await backend.stop();}
  const reopened=new BackendClient(process.cwd(),5000,{dataDirectory:path.join(work,'db'),credentials:()=>({})});
  try {const result=await reopened.chat('chat.get',{id});expect(result.grant).toBeNull();expect(result.messages.length).toBeGreaterThan(0);}
  finally{await reopened.stop();}
},15000);
