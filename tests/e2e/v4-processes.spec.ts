import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,readFile,writeFile,access} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import type {} from '../../apps/desktop/src/shared/api';

/** 仅准确dialogs模拟，实际普通Token/CreateProcess/WM_CLOSE/TerminateProcess和SQLite。 */
test('V4-009准确启动、等待、温和关闭不升级、另批终止与重启事实',async()=>{
  test.setTimeout(180000);
  const root=path.resolve('artifacts/test-results/V4-009');await mkdir(root,{recursive:true});const work=await mkdtemp(path.join(root,'electron-'));
  const cwd=path.join(work,'合成 工作目录');await mkdir(cwd);const marker=path.join(cwd,'合成启动.txt');
  const tester=path.resolve('backend/.venv/Scripts/python.exe');
  // venv的exe可仅是redirector；准确目标使用已安装的baseexe，避免把launcher退出当子程序退出。
  const exe=execFileSync(tester,['-I','-c','import sys;print(sys._base_executable)'],{encoding:'utf8'}).trim();
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_PROCESS_EXE:exe,ORVIA_PROCESS_CWD:cwd,ORVIA_PROCESS_CONFIRM:'0'};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','REDIS_PASSWORD'])delete env[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/v4-processes-launch.cjs')],env});let app=await launch();let pid=0,created=0;
  const exists=()=>execFileSync(tester,['-I','-c',`import psutil;print(int(psutil.pid_exists(${pid})))`],{encoding:'utf8'}).trim()==='1';
  try{
    let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    const made=await page.evaluate(()=>window.orvia.chatCreate({client_request_id:crypto.randomUUID(),title:'合成进程验收'}));if(!made.ok)throw Error(made.message);const cid=made.result.id;
    await page.getByRole('button',{name:'设置',exact:true}).click();let panel=page.getByLabel('普通用户进程管理',{exact:true});await panel.getByLabel('进程操作所属会话',{exact:true}).selectOption(cid);
    await panel.getByLabel('进程观察等待（秒，1～15）',{exact:true}).fill('1');await panel.getByLabel('原生选择此次程序工作目录',{exact:true}).check();
    const args=['-I','-c',"import pathlib,time;pathlib.Path('合成启动.txt').write_text('合成普通进程',encoding='utf-8');time.sleep(120)"];
    await panel.getByLabel('启动参数（JSON字符串数组）',{exact:true}).fill(JSON.stringify(args));
    await panel.getByRole('button',{name:'原生选择程序并准备启动预览',exact:true}).click();await expect(panel.getByLabel('进程完整批准正文',{exact:true})).toHaveValue(/"action": "launch"/);
    await panel.getByRole('button',{name:'原生批准此准确进程动作',exact:true}).click();await expect(panel.getByText('已取消原生批准，进程动作未执行。',{exact:true})).toBeVisible();
    await expect(access(marker)).rejects.toThrow();let history=await page.evaluate(id=>window.orvia.processHistory({id}),cid);expect(history.ok&&history.result.executions.length).toBe(0);
    await app.evaluate(()=>{process.env.ORVIA_PROCESS_CONFIRM='1';});
    await panel.getByRole('button',{name:'原生选择程序并准备启动预览',exact:true}).click();await panel.getByRole('button',{name:'原生批准此准确进程动作',exact:true}).click();
    await expect(panel.getByLabel('进程操作事实',{exact:true})).toContainText('等待结束，准确进程仍运行');
    history=await page.evaluate(id=>window.orvia.processHistory({id}),cid);if(!history.ok)throw Error(history.message);const launched=history.result.executions[0];pid=launched.target!.pid;created=launched.target!.create_time;
    expect(launched.verified).toBe(true);expect(exists()).toBe(true);expect(await readFile(marker,'utf8')).toBe('合成普通进程');
    // 应用关闭只收尾事实，已释放普通程序应保持运行；重启不自动再启动或取得动作许可。
    await app.close();expect(exists()).toBe(true);env.ORVIA_PROCESS_CONFIRM='1';app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'设置',exact:true}).click();panel=page.getByLabel('普通用户进程管理',{exact:true});await panel.getByLabel('进程操作所属会话',{exact:true}).selectOption(cid);
    await panel.getByLabel('进程观察等待（秒，1～15）',{exact:true}).fill('1');await panel.locator('summary').click();
    await panel.getByRole('button',{name:`启动 · 等待结束，准确进程仍运行 · PID ${pid}`,exact:true}).click();
    const choose=async(action:'wait'|'close'|'terminate')=>{await panel.getByLabel('此次准确进程动作',{exact:true}).selectOption(action);await panel.getByRole('button',{name:'准备此准确进程动作预览',exact:true}).click();await expect(panel.getByLabel('进程完整批准正文',{exact:true})).toBeVisible();};
    await choose('wait');await panel.getByRole('button',{name:'原生批准此准确进程动作',exact:true}).click();await expect(panel.getByLabel('进程操作事实',{exact:true})).toContainText('等待结束，准确进程仍运行');expect(exists()).toBe(true);
    await choose('close');await app.evaluate(()=>{process.env.ORVIA_PROCESS_CONFIRM='0';});await panel.getByRole('button',{name:'原生批准此准确进程动作',exact:true}).click();expect(exists()).toBe(true);
    history=await page.evaluate(id=>window.orvia.processHistory({id}),cid);expect(history.ok&&history.result.executions.length).toBe(2);
    await choose('close');await app.evaluate(()=>{process.env.ORVIA_PROCESS_CONFIRM='1';});await panel.getByRole('button',{name:'原生批准此准确进程动作',exact:true}).click();
    await expect(panel.getByLabel('进程操作事实',{exact:true})).toContainText('等待结束，准确进程仍运行');await expect(panel.getByLabel('进程操作事实',{exact:true})).toContainText('没有实际投递窗口关闭请求');expect(exists()).toBe(true);
    await choose('terminate');await app.evaluate(()=>{process.env.ORVIA_PROCESS_CONFIRM='0';});await panel.getByRole('button',{name:'原生批准此准确进程动作',exact:true}).click();expect(exists()).toBe(true);
    await choose('terminate');await app.evaluate(()=>{process.env.ORVIA_PROCESS_CONFIRM='1';});await panel.getByRole('button',{name:'原生批准此准确进程动作',exact:true}).click();await expect(panel.getByLabel('进程操作事实',{exact:true})).toContainText('准确进程已退出');
    await expect.poll(exists,{timeout:3000}).toBe(false);await page.screenshot({path:path.join(work,'process-terminated.png')});
    history=await page.evaluate(id=>window.orvia.processHistory({id}),cid);if(!history.ok)throw Error(history.message);expect(history.result.executions).toHaveLength(4);const previous=launched;
    await app.close();app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    const restored=await page.evaluate(id=>window.orvia.processHistory({id}),cid);expect(restored.ok&&restored.result.executions.length).toBe(4);expect(exists()).toBe(false);
    const replay=await page.evaluate(p=>window.orvia.processExecute({id:p.id,operation_id:p.operation_id,revision:p.revision}),previous);expect(replay.ok).toBe(false);
    await writeFile(path.join(work,'acceptance.json'),JSON.stringify({module:'V4-009',actual:['Electron/preload/main/Python','SQLite','ordinary Windows launch and exact creation identity','released program survived Orvia close','wait still-running','no-window close did not kill','separately approved terminate and exit','restart no launch/replay'],mock:['native dialogs'],cloudCalls:0,attempts:4,terminated:true,unverified:['manual native dialogs','third-party unsaved window behavior']},null,2));
  }finally{
    if(pid&&exists())execFileSync(tester,['-I','-c',`import psutil;p=psutil.Process(${pid});assert p.create_time()==${created};p.kill();p.wait(3)`]);
    await app.close();
  }
});
