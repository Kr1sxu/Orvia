/** 仅只读真实自有UI线程输入法前提；这项通过不能称为物理IME组合输入通过。 */
import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,writeFile} from 'node:fs/promises';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';
import type {} from '../../apps/desktop/src/shared/api';

const run=promisify(execFile);
test('M20只读自有窗口UI线程HKL与焦点前提（未发送物理IME按键）',async()=>{
  test.setTimeout(90000);
  const results=path.resolve('artifacts/test-results/M20');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'ime-inspect-')),profile=path.join(work,'profile');await mkdir(profile);
  const env:Record<string,string>={...Object.fromEntries(Object.entries(process.env).filter((pair):pair is [string,string]=>typeof pair[1]==='string')),ORVIA_DEV_DATA_DIR:profile};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete env[key];
  const app=await electron.launch({args:[path.resolve('tests/e2e/m20-runtime-parity-launch.cjs'),`--user-data-dir=${profile}`],env});
  try{
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible({timeout:30000});
    const input=page.getByLabel('输入需求'),draft='M20 synthetic unsent IME prerequisite';await input.fill(draft);await input.focus();
    const identity=await app.evaluate(({BrowserWindow})=>{
      const ownWindow=BrowserWindow.getAllWindows()[0];ownWindow.focus();
      const bytes=ownWindow.getNativeWindowHandle();
      return {pid:process.pid,executable:process.execPath,hwnd:(bytes.length===8?bytes.readBigUInt64LE():BigInt(bytes.readUInt32LE())).toString()};
    });
    expect(path.resolve(identity.executable).toLowerCase()).toBe(path.resolve('node_modules/electron/dist/electron.exe').toLowerCase());
    const {stdout}=await run(path.join(process.env.SystemRoot!,'System32/WindowsPowerShell/v1.0/powershell.exe'),['-NoProfile','-NonInteractive','-File',path.resolve('tests/e2e/m20-ime-input.ps1'),'-OwnerProcess',String(identity.pid),'-WindowHandle',identity.hwnd,'-ProfileDirectory',profile],{windowsHide:true,timeout:20000,maxBuffer:4000});
    const fact=JSON.parse(stdout.trim());expect(fact.ownerMatched).toBe(true);expect(fact.profileMatched).toBe(true);
    await expect(input).toHaveValue(draft);await input.fill('');
    await writeFile(path.join(work,'ime-prerequisite.json'),JSON.stringify({module:'M20',phase:'read-only prerequisite',...identity,...fact,rendererInputFocused:await input.evaluate(node=>document.activeElement===node),keysSent:0,layoutChanged:false,physicalCompositionVerified:false,modelCalls:0,scope:'only this isolated Electron PID, top HWND and its UI thread; no other candidate/window/config inspection'},null,2));
  }finally{await app.close();}
});

test('M20真实Windows中文IME固定NIHAO及Space组合不发送待办需求',async()=>{
  test.setTimeout(90000);
  const results=path.resolve('artifacts/test-results/M20');await mkdir(results,{recursive:true});
  const work=await mkdtemp(path.join(results,'ime-physical-')),profile=path.join(work,'profile');await mkdir(profile);
  const env:Record<string,string>={...Object.fromEntries(Object.entries(process.env).filter((pair):pair is [string,string]=>typeof pair[1]==='string')),ORVIA_DEV_DATA_DIR:profile};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'])delete env[key];
  const app=await electron.launch({args:[path.resolve('tests/e2e/m20-runtime-parity-launch.cjs'),`--user-data-dir=${profile}`],env});
  try{
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible({timeout:30000});
    const input=page.getByLabel('输入需求');await input.fill('看看目录里有哪些文件');await expect(page.getByRole('button',{name:'发送',exact:true})).toBeEnabled();await input.press('Enter');await expect(page.getByLabel('当前需求待办')).toBeVisible();
    const requestsBefore=await naturalRequests(page);
    await input.fill('');await input.focus();await input.evaluate(node=>{
      (globalThis as any).__m20ImeEvents=[];
      // 只监听本输入OS实际事件；没有dispatch/Unicode插入/读取候选窗口。
      for(const type of ['compositionstart','compositionupdate','compositionend'])node.addEventListener(type,event=>(globalThis as any).__m20ImeEvents.push({type:event.type,trusted:event.isTrusted,data:(event as CompositionEvent).data.slice(0,32)}));
    });
    const identity=await app.evaluate(({BrowserWindow})=>{const own=BrowserWindow.getAllWindows()[0];own.focus();const bytes=own.getNativeWindowHandle();return{pid:process.pid,executable:process.execPath,hwnd:(bytes.length===8?bytes.readBigUInt64LE():BigInt(bytes.readUInt32LE())).toString(),versions:{electron:process.versions.electron,chrome:process.versions.chrome,node:process.versions.node}};});
    const step=async(action:'Inspect'|'TypePinyin'|'CommitSpace')=>{const {stdout}=await run(path.join(process.env.SystemRoot!,'System32/WindowsPowerShell/v1.0/powershell.exe'),['-NoProfile','-NonInteractive','-File',path.resolve('tests/e2e/m20-ime-input.ps1'),'-OwnerProcess',String(identity.pid),'-WindowHandle',identity.hwnd,'-ProfileDirectory',profile,'-Action',action],{windowsHide:true,timeout:20000,maxBuffer:4000});return JSON.parse(stdout.trim());};
    const facts:unknown[]=[];let keysSent=0,verified=false;
    try{
      expect(identity.versions.electron).toBe('44.4.5');expect(identity.versions.chrome).toBe('152.0.7977.130');
      const prerequisite=await step('Inspect');facts.push(prerequisite);expect(prerequisite.foregroundOwn&&prerequisite.focusOwnerMatched&&prerequisite.focusRootIsOwn&&prerequisite.simplifiedChineseLayout).toBe(true);await expect(input).toBeFocused();
      const typed=await step('TypePinyin');facts.push(typed);keysSent+=typed.keysSent;
      await expect.poll(async()=>page.evaluate(()=>(globalThis as any).__m20ImeEvents.some((event:any)=>event.type==='compositionstart'&&event.trusted)&&(globalThis as any).__m20ImeEvents.some((event:any)=>event.type==='compositionupdate'&&event.trusted)),{timeout:2000}).toBe(true);
      // 只有真实start/update已经到达，才另一步发送固定Space，永远不发送Enter。
      const committed=await step('CommitSpace');facts.push(committed);keysSent+=committed.keysSent;
      // 该锁定Chromium版本end走ScopedEventQueue，保持默认trusted=false；真实来源由OS守卫及trusted start/update证明。
      // primary链见M20/ime-source-investigation.md。记录end实际trusted，核对结束顺序/内容，不伪造为true。
      await expect.poll(async()=>page.evaluate(()=>(globalThis as any).__m20ImeEvents.some((event:any)=>event.type==='compositionend')),{timeout:2000}).toBe(true);
      const composed=await page.evaluate(()=>(globalThis as any).__m20ImeEvents as {type:string;trusted:boolean;data:string}[]);
      expect(composed[0]).toMatchObject({type:'compositionstart',trusted:true});expect(composed.at(-1)).toMatchObject({type:'compositionend',data:'你好'});
      expect(composed.filter(event=>event.type==='compositionend')).toHaveLength(1);expect(composed.slice(1,-1).every(event=>event.type==='compositionupdate'&&event.trusted)).toBe(true);
      await expect(input).toHaveValue(/你好/);expect(await naturalRequests(page)).toBe(requestsBefore);verified=true;await page.screenshot({path:path.join(work,'ime-product.png')});
    }finally{
      const events=await page.evaluate(()=>(globalThis as any).__m20ImeEvents),text=await input.inputValue(),requestsAfter=await naturalRequests(page);
      await writeFile(path.join(work,'ime-physical.json'),JSON.stringify({module:'M20',...identity,facts,keysSent,events,text,requestsBefore,requestsAfter,physicalCompositionVerified:verified,layoutChanged:false,unicodeInjection:false,enterSent:false,candidateWindowsInspected:false,modelCalls:0,sourceInvestigation:'ime-source-investigation.md; Chromium152.0.7977.130 native compositionend uses ScopedEventQueue without EventTarget trusted setter; actual end.trusted recorded unchanged',scope:'own HWND/UI thread, ASCII virtual keys NIHAO followed by separately gated Space'},null,2));
      await input.fill('');
    }
  }finally{await app.close();}
});
async function naturalRequests(page:import('@playwright/test').Page){return page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok||!list.result.conversations.length)throw Error('IME own conversation missing');const reply=await window.orvia.chatGet({id:list.result.conversations[0].id});if(!reply.ok)throw Error(reply.message);return reply.result.messages.filter(message=>message.kind==='natural_request').length;});}
