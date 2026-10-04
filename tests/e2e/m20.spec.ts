import {_electron as electron,expect,test,type Page} from '@playwright/test';
import {mkdir,mkdtemp,writeFile,readFile,copyFile,stat} from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {documentFixtures} from '../integration/m13-fixtures';
import type {} from '../../apps/desktop/src/shared/api';

/** 所有资料、用户目录和结果只在M20忽略树；启动器仅替换系统选择/确认和合成网络。 */
async function fixture(mode='normal',extra:Record<string,string>={}){
  const results=path.resolve(process.env.ORVIA_TEST_RESULTS??'artifacts/test-results/M20');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'dialog-'));const directory=path.join(work,'synthetic-files');await mkdir(directory);
  for(let index=0;index<205;index++)await writeFile(path.join(directory,`${String(index).padStart(3,'0')}.${index%2?'txt':'py'}`),'合成资料；不可信命令不能授权');
  await mkdir(path.join(directory,'child'));await writeFile(path.join(directory,'child','deeper.md'),'synthetic');
  documentFixtures(work);
  execFileSync(path.resolve('backend/.venv/Scripts/python.exe'),['-X','utf8','-c',`import sys,zipfile\nfrom pathlib import Path\np=Path(sys.argv[1])\nwith zipfile.ZipFile(p/'synthetic.docx') as source, zipfile.ZipFile(p/'second.docx','w') as destination:\n for name in source.namelist(): destination.writestr(name,source.read(name).replace('合成文档许可条件'.encode(),'第二份合成资料'.encode()))`,work],{windowsHide:true,stdio:'pipe'});
  const output=path.join(work,'synthetic-brief.docx'),counter=path.join(work,'call-count.json');
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M20_DIRECTORY:directory,ORVIA_M20_INPUTS:JSON.stringify([path.join(work,'synthetic.docx')]),ORVIA_M20_EXPORT:output,ORVIA_M20_COUNTER:counter,ORVIA_M20_MODEL_MODE:mode,...extra};
  delete (env as NodeJS.ProcessEnv).ELECTRON_RUN_AS_NODE;
  for(const key of ['DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete (env as NodeJS.ProcessEnv)[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/m20-launch.cjs'),`--user-data-dir=${env.ORVIA_DEV_DATA_DIR}`],env});
  const calls=async()=>{try{return JSON.parse(await readFile(counter,'utf8')) as {role:string;stream:boolean}[];}catch{return[];}};
  return{results,work,directory,output,env,launch,calls};
}
async function ready(page:Page){try{await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible({timeout:30000});}catch(error){await test.info().attach('synthetic-ui-state',{body:await page.locator('body').innerText(),contentType:'text/plain'});throw error;}}
async function send(page:Page,text:string){await page.getByLabel('输入需求').fill(text);await expect(page.getByRole('button',{name:'发送',exact:true})).toBeEnabled();await page.getByLabel('输入需求').press('Enter');}
async function plus(page:Page,type:'file'|'directory'){
  await page.getByRole('button',{name:'添加本地资料',exact:true}).click();
  await page.getByRole('menuitem',{name:type==='file'?'添加文件（最多3个）':'选择并授权文件夹'}).click();
}
async function snapshot(page:Page,id?:string){return page.evaluate(async(id)=>{const list=await window.orvia.chatList();if(!list.ok)throw Error('list');const result=await window.orvia.chatGet({id:id??list.result.conversations[0].id});if(!result.ok)throw Error('get');return result.result;},id);}

test('M20延迟创建会话后切换新视图，保留草稿与焦点且不派发旧需求',async()=>{
  const f=await fixture();const app=await f.launch();
  try{const page=await app.firstWindow();await ready(page);
    // 只测试主进程延迟真实create回包；产品IPC和后端均不增设测试入口。
    await app.evaluate(({ipcMain})=>{const handlers=(ipcMain as any)._invokeHandlers,original=handlers.get('orvia:chat-create');handlers.set('orvia:chat-create',async(...args:unknown[])=>{const reply=await original(...args);await new Promise<void>(resolve=>{(globalThis as any).m20ReleaseCreate=resolve;});return reply;});});
    await send(page,'看看目录里有哪些文件');
    await expect.poll(()=>app.evaluate(()=>typeof (globalThis as any).m20ReleaseCreate)).toBe('function');
    await page.getByRole('button',{name:'新建对话',exact:true}).click();await page.getByLabel('输入需求').fill('这是后来视图的草稿');
    await app.evaluate(()=>{(globalThis as any).m20ReleaseCreate();});
    await expect(page.getByRole('button',{name:'发送',exact:true})).toBeEnabled();
    await expect(page.getByLabel('输入需求')).toHaveValue('这是后来视图的草稿');await expect(page.getByLabel('输入需求')).toBeFocused();
    const state=await snapshot(page);expect(state.messages).toHaveLength(0);expect(state.workflow).toBeNull();expect(await f.calls()).toHaveLength(0);
    await page.screenshot({path:path.join(f.work,'delayed-create-draft.png')});
  }finally{await app.close();}
});

test('M20授权接续与未返回的旧paused拉取重叠，最终批次全部ACK',async()=>{
  const f=await fixture();const app=await f.launch();
  try{const page=await app.firstWindow();await ready(page);
    await app.evaluate(({ipcMain})=>{const handlers=(ipcMain as any)._invokeHandlers,pull=handlers.get('orvia:chat-stream-pull'),ack=handlers.get('orvia:chat-stream-ack');
      handlers.set('orvia:chat-stream-pull',async(...args:unknown[])=>{const reply=await pull(...args);if(!(globalThis as any).m20Held&&reply?.result?.events?.some((e:any)=>e.kind==='paused')){(globalThis as any).m20Held=true;await new Promise<void>(resolve=>{(globalThis as any).m20ReleasePull=resolve;});}return reply;});
      handlers.set('orvia:chat-stream-ack',async(event:unknown,input:any)=>{(globalThis as any).m20LastAck=input.seq;return ack(event,input);});});
    await send(page,'看看目录里有哪些文件');await expect(page.getByLabel('当前需求待办')).toBeVisible();
    await expect.poll(()=>app.evaluate(()=>typeof (globalThis as any).m20ReleasePull)).toBe('function');
    await plus(page,'directory');await expect(page.getByLabel('目录直接回答')).toContainText('实际发现206项');
    await app.evaluate(()=>{(globalThis as any).m20ReleasePull();});
    await expect.poll(()=>app.evaluate(()=>(globalThis as any).m20LastAck)).toBeGreaterThan(8);
    await expect(page.getByText('流事件存在缺口',{exact:false})).toHaveCount(0);expect((await snapshot(page)).workflow).toBeNull();expect(await f.calls()).toHaveLength(0);
  }finally{await app.close();}
});

test('M20无技术模式、先需求后目录授权、真实批次与完整分页、深度和撤权',async()=>{
  const f=await fixture();const app=await f.launch();
  try{const page=await app.firstWindow();await ready(page);
    await expect(page.getByLabel('输入需求')).toHaveAttribute('placeholder','你想做些什么');await expect(page.getByLabel('需求类型')).toHaveCount(0);
    await send(page,'看看目录里有哪些文件并按扩展名分类');await expect(page.getByLabel('当前需求待办')).toContainText('原请求已保留');
    const waiting=await snapshot(page);expect(waiting.workflow?.action).toBe('directory');
    await plus(page,'directory');const answer=page.getByLabel('目录直接回答').last();await expect(answer).toContainText('实际发现206项');
    await expect(answer).toContainText('没有读取文件正文');await expect(answer).toContainText('000.py');
    await answer.getByRole('button',{name:/完整已发现清单/}).click();await answer.getByRole('button',{name:'下一页',exact:true}).click();
    await expect(answer).toContainText('当前展示100项');await answer.getByRole('button',{name:'下一页',exact:true}).click();await expect(answer).toContainText('当前展示6项');
    const final=await snapshot(page);expect(final.workflow).toBeNull();expect(final.messages.filter(message=>message.kind==='natural_request')).toHaveLength(1);expect(await f.calls()).toHaveLength(0);
    await send(page,'递归看看文件夹，深度3');await expect(page.getByLabel('目录直接回答').last()).toContainText('实际发现207项');
    await page.getByRole('button',{name:'撤销目录授权',exact:true}).click();await expect(page.getByText('当前未授权目录；历史记录不会恢复目录权限。',{exact:true})).toBeVisible();
    await page.screenshot({path:path.join(f.work,'directory-pagination.png')});
  }finally{await app.close();}
});

test('M20先摘要需求后附件自动接续、真实SSE增量、引用和Word成品',async()=>{
  const f=await fixture();const app=await f.launch();
  try{const page=await app.firstWindow();await ready(page);await send(page,'总结这份文档，然后生成Word简报');
    await expect(page.getByLabel('当前需求待办')).toContainText('添加本地资料');await plus(page,'file');
    const preview=page.getByLabel('模型发送范围预览');await expect(preview).toContainText('deepseek-flash');await expect(preview).toContainText('保留来源');
    const denied=await page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok)throw Error('list');return (window.orvia as any).chatNatural({id:list.result.conversations[0].id,request_id:crypto.randomUUID(),text:'测试',path:'C:/',approved:true});});expect(denied.ok).toBe(false);
    await preview.getByRole('button',{name:'确认这些片段并调用 Main 模型'}).click();
    await expect(page.getByLabel('实时结果').last()).toContainText('合成');
    const answer=page.getByLabel('模型综合回答').last();await expect(answer).toContainText('资料要求保留来源');
    await answer.locator('summary').click();await answer.getByRole('button',{name:/synthetic.docx/}).first().click();await expect(page.getByLabel('文档证据详情')).toContainText('文件版本');await expect(page.getByLabel('文档证据详情')).toBeInViewport();
    await expect(page.getByLabel('简报成品制作')).toBeVisible();const publication=page.getByLabel('简报成品制作');
    await publication.getByRole('button',{name:'预览内容与版面'}).click();await page.getByLabel('简报版式预览').getByRole('button',{name:'选择新文件路径并确认保存'}).click();
    await expect(page.getByLabel('成品核验结果')).toBeVisible();expect((await stat(f.output)).size).toBeGreaterThan(1000);expect((await readFile(f.output)).subarray(0,2).toString()).toBe('PK');
    await expect.poll(async()=>(await snapshot(page)).workflow).toBeNull();await expect(page.getByLabel('成品核验结果')).toBeInViewport();expect(await f.calls()).toEqual([{role:'main',stream:true}]);
    expect(await page.evaluate(()=>({node:typeof (window as any).require,ipc:typeof (window.orvia as any).invoke}))).toEqual({node:'undefined',ipc:'undefined'});
    await page.screenshot({path:path.join(f.work,'synthesis-publication.png')});
  }finally{await app.close();}
});

test('M20网址自然请求复合摘要、可回查引用、恶意网页不扩大权限',async()=>{
  const f=await fixture();const app=await f.launch();
  try{const page=await app.firstWindow();await ready(page);await send(page,'读取 https://m20.example/article ，概括这篇网页');
    const preview=page.getByLabel('模型发送范围预览');await expect(preview).toContainText('合成网页');await preview.getByRole('button',{name:'确认这些片段并调用 Main 模型'}).click();
    await expect(page.getByLabel('模型综合回答')).toContainText('资料要求保留来源');await expect(page.getByLabel('模型综合回答')).toBeInViewport();const state=await snapshot(page);expect(state.grant).toBeNull();expect(state.operation).toBeNull();expect(state.materials?.[0].kind).toBe('browser');
    await page.getByLabel('模型综合回答').locator('summary').click();await page.getByLabel('模型综合回答').getByRole('button',{name:/M20合成网页/}).click();await expect(page.getByLabel('证据详情')).toContainText('https://m20.example/article');await expect(page.getByLabel('证据详情')).toBeInViewport();
    await app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows()[0].setSize(760,560));await expect(page.getByLabel('输入需求')).toBeInViewport();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
    await page.screenshot({path:path.join(f.work,'natural-answer-small-window.png')});
  }finally{await app.close();}
});

test('M20多附件歧义只澄清对象，移除保留历史原文并使发送预览失效',async()=>{
  const f=await fixture();f.env.ORVIA_M20_INPUTS=JSON.stringify([path.join(f.work,'synthetic.docx'),path.join(f.work,'second.docx')]);const app=await f.launch();
  try{const page=await app.firstWindow();await ready(page);await plus(page,'file');await expect(page.getByLabel('本次需求资料')).toBeVisible();await send(page,'总结这份文档');
    await expect(page.getByLabel('当前需求待办')).toContainText('明确本次');expect(await f.calls()).toHaveLength(0);
    await page.getByLabel('当前需求待办').getByRole('button',{name:/^synthetic\.docx · /}).click();await expect(page.getByLabel('模型发送范围预览')).toBeVisible();
    const material=page.getByLabel('本次需求资料').locator('div.row').filter({hasText:'synthetic.docx'});await material.getByRole('button',{name:'从本次需求移除',exact:true}).click();
    await expect(page.getByLabel('模型发送范围预览')).toHaveCount(0);const state=await snapshot(page);expect(state.materials?.some(item=>item.title==='synthetic.docx')).toBe(false);expect(state.documents?.some(item=>item.title==='synthetic.docx')).toBe(true);expect(await f.calls()).toHaveLength(0);
  }finally{await app.close();}
});

test('M20取消原生选择和切换会话后不会自动接续或跨任务重放',async()=>{
  const f=await fixture('normal',{ORVIA_M20_SELECT_CANCEL:'1'});const app=await f.launch();
  try{const page=await app.firstWindow();await ready(page);await send(page,'看看目录里有哪些文件');await expect(page.getByLabel('当前需求待办')).toBeVisible();await plus(page,'directory');
    await expect(page.getByText('已取消选择；原需求保留，没有自动接续。',{exact:true})).toBeVisible();await expect(page.getByLabel('目录直接回答')).toHaveCount(0);
    await page.getByRole('button',{name:'新建对话',exact:true}).click();await page.getByLabel('输入需求').fill('未发送的第二会话草稿');await page.getByRole('navigation',{name:'历史会话'}).getByRole('button').first().click();
    await expect(page.getByLabel('当前需求待办')).toHaveCount(0);await expect(page.getByLabel('目录直接回答')).toHaveCount(0);expect(await f.calls()).toHaveLength(0);
  }finally{await app.close();}
});

test('M20模型流期间读历史和输入草稿不被焦点/滚动/终态覆盖；中文IME不误提交',async()=>{
  const f=await fixture('slow');const app=await f.launch();
  try{const page=await app.firstWindow();await ready(page);await send(page,'看看目录');await expect(page.getByLabel('当前需求待办')).toBeVisible();await plus(page,'directory');await expect(page.getByLabel('目录直接回答')).toBeVisible();
    const old=(await snapshot(page)).id;await page.getByLabel('对话消息',{exact:true}).evaluate(node=>{node.scrollTop=100;});
    await expect.poll(()=>page.getByLabel('对话消息',{exact:true}).evaluate(node=>node.scrollTop)).toBe(100);
    await page.getByRole('button',{name:'新建对话',exact:true}).click();await send(page,'你好，请解释流式输出');await expect(page.getByLabel('实时结果').last()).toContainText('合成');
    await page.getByRole('navigation',{name:'历史会话'}).getByRole('button').filter({hasText:'看看目录'}).click();await expect(page.getByLabel('目录直接回答')).toBeVisible();
    await expect.poll(()=>page.getByLabel('对话消息',{exact:true}).evaluate(node=>node.scrollTop)).toBe(100);
    const input=page.getByLabel('输入需求');await input.fill('历史会话未发送草稿');await input.focus();
    const before=(await snapshot(page,old)).messages.length;
    await input.dispatchEvent('compositionstart');await input.dispatchEvent('keydown',{key:'Enter',keyCode:229,isComposing:true,bubbles:true});await input.dispatchEvent('compositionend');await expect(input).toHaveValue('历史会话未发送草稿');
    expect((await snapshot(page,old)).messages.length).toBe(before);
    await expect.poll(async()=>page.evaluate(async()=>{const list=await window.orvia.chatList();return list.ok?list.result.conversations.find(item=>item.title.includes('你好'))?.status:undefined;})).toBe('completed');
    await expect(input).toHaveValue('历史会话未发送草稿');expect(await input.evaluate(node=>node===document.activeElement)).toBe(true);expect((await page.evaluate(async old=>{const list=await window.orvia.chatList();if(!list.ok)throw Error();return window.orvia.chatGet({id:list.result.conversations.find(item=>item.id!==old)!.id});},old)).ok).toBe(true);
    expect(await page.getByLabel('对话消息',{exact:true}).evaluate(node=>node.scrollTop)).toBe(100);
    await page.screenshot({path:path.join(f.work,'history-draft-focus.png')});
  }finally{await app.close();}
});

test('M20断流保留部分事实、单次同模型原生降级、重启不自动重放',async()=>{
  const f=await fixture('broken');let app=await f.launch();
  try{let page=await app.firstWindow();await ready(page);await send(page,'总结这份文档');await expect(page.getByLabel('当前需求待办')).toContainText('添加本地');await plus(page,'file');
    await page.getByLabel('模型发送范围预览').getByRole('button',{name:'确认这些片段并调用 Main 模型'}).click();await expect(page.getByLabel('当前需求待办')).toContainText('非流式');
    await expect(page.getByLabel('模型综合回答')).toHaveCount(0);expect(await f.calls()).toEqual([{role:'main',stream:true}]);
    const partial=(await snapshot(page)).messages.find(item=>item.kind==='model_partial');expect(partial?.data?.provisional).toBe(true);expect(partial?.data?.text).toBeTruthy();
    expect(partial?.data?.state).toBe('failed');
    await page.getByLabel('模型发送范围预览').getByRole('button',{name:'确认这些片段并调用 Main 模型'}).click();await expect(page.getByLabel('模型综合回答')).toContainText('合成摘要');
    expect(await f.calls()).toEqual([{role:'main',stream:true},{role:'main',stream:false}]);await app.close();app=await f.launch();page=await app.firstWindow();await ready(page);await page.getByRole('navigation',{name:'历史会话'}).getByRole('button').first().click();
    await expect(page.getByLabel('模型综合回答')).toContainText('合成摘要');expect(await f.calls()).toHaveLength(2);const reopened=await snapshot(page);expect(reopened.grant).toBeNull();
    const savedPartial=reopened.messages.filter(item=>item.kind==='model_partial'&&item.data?.stream_id===partial?.data?.stream_id);expect(savedPartial).toHaveLength(1);expect(savedPartial[0].id).toBe(partial!.id);expect(savedPartial[0].data?.text).toBe(partial!.data?.text);
  }finally{await app.close();}
});

test('M20缺凭据、不支持任务和内网URL明确失败，未回退模型/授权',async()=>{
  const f=await fixture('missing');const app=await f.launch();
  try{const page=await app.firstWindow();await ready(page);await send(page,'请解释流式输出的原理');await expect(page.getByText(/固定Main凭据缺失/)).toBeVisible();await send(page,'永久删除全部文件并提权');await expect(page.getByText(/超出已实现/)).toBeVisible();await send(page,'读取 http://127.0.0.1/test');await expect(page.getByText(/URL_BLOCKED/).first()).toBeVisible();
    const state=await snapshot(page);expect(state.grant).toBeNull();expect(state.operation).toBeNull();expect(await f.calls()).toHaveLength(0);
  }finally{await app.close();}
});
