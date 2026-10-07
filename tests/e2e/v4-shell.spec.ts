import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,readFile,writeFile,access} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import type {} from '../../apps/desktop/src/shared/api';

/** 实际PowerShell/GitBash/Windows Job，只有明确原生选择与确认模拟。 */
test('V4-008 实际Shell准确审批、输入副本核验、独立回传、Bash和及时取消后代',async()=>{
  test.setTimeout(180000);
  const root=path.resolve('artifacts/test-results/V4-008');await mkdir(root,{recursive:true});const work=await mkdtemp(path.join(root,'electron-'));
  const cwd=path.join(work,'合成 工作目录');await mkdir(cwd);const input=path.join(work,'合成输入.txt'),saved=path.join(work,'合成 导出.txt');await writeFile(input,'合成输入内容','utf8');
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_SHELL_CWD:cwd,ORVIA_SHELL_INPUT:input,ORVIA_SHELL_SAVE:saved,ORVIA_SHELL_CONFIRM:'1'};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','REDIS_PASSWORD'])delete env[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/v4-shell-launch.cjs')],env});let app=await launch();
  try{
    let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    const made=await page.evaluate(()=>window.orvia.chatCreate({client_request_id:crypto.randomUUID(),title:'合成Shell验收'}));if(!made.ok)throw Error(made.message);const cid=made.result.id;
    await page.getByRole('button',{name:'设置',exact:true}).click();const panel=page.getByLabel('普通账户 Shell 执行',{exact:true});
    await expect(panel.getByLabel('本次 Shell 解释器',{exact:true})).toHaveValue('powershell',{timeout:20000});
    await panel.getByLabel('Shell 所属会话',{exact:true}).selectOption(cid);
    const script="$text=[IO.File]::ReadAllText((Join-Path $env:ORVIA_INPUT_DIR '合成输入.txt')); [IO.File]::WriteAllText((Join-Path $env:ORVIA_OUTPUT_DIR '合成结果.txt'),$text,[Text.UTF8Encoding]::new($false)); Write-Output '合成 Shell 返回证据'";
    await panel.getByLabel('完整 Shell 脚本',{exact:true}).fill(script);await panel.getByLabel('明确核验 stdout 包含文本（可留空）',{exact:true}).fill('合成 Shell 返回证据');await panel.getByLabel('明确产物文件名（每行一个，最多十个）',{exact:true}).fill('合成结果.txt');
    await panel.getByLabel('原生选择本次工作目录',{exact:true}).check();await panel.getByLabel('原生选择显式输入文件',{exact:true}).check();
    await panel.getByRole('button',{name:'准备 Shell 完整预览',exact:true}).click();await expect(panel.getByLabel('Shell 完整批准正文',{exact:true})).toHaveValue(/合成输入.txt/);
    await app.evaluate(()=>{process.env.ORVIA_SHELL_CONFIRM='0';});await panel.getByRole('button',{name:'原生批准此完整 Shell 脚本',exact:true}).click();await expect(panel).toContainText('已取消原生批准，脚本未执行。');const empty=await page.evaluate(id=>window.orvia.shellHistory({id}),cid);expect(empty.ok&&empty.result.executions.length===0).toBe(true);
    await app.evaluate(()=>{process.env.ORVIA_SHELL_CONFIRM='1';});await panel.getByRole('button',{name:'准备 Shell 完整预览',exact:true}).click();await panel.getByRole('button',{name:'原生批准此完整 Shell 脚本',exact:true}).click();await expect(panel.getByLabel('Shell 进程与核验事实',{exact:true})).toContainText('明确列出的核验通过',{timeout:20000});
    await expect(panel.getByLabel('Shell stdout',{exact:true})).toHaveValue(/合成 Shell 返回证据/);await panel.getByLabel('Shell 进程与核验事实',{exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(work,'shell-verified-output.png')});
    await app.evaluate(()=>{process.env.ORVIA_SHELL_CONFIRM='0';});await panel.getByRole('button',{name:'逐文件批准回传 合成结果.txt',exact:true}).click();await expect(panel).toContainText('已取消产物回传。');await expect(access(saved)).rejects.toThrow();
    await app.evaluate(()=>{process.env.ORVIA_SHELL_CONFIRM='1';});await panel.getByRole('button',{name:'逐文件批准回传 合成结果.txt',exact:true}).click();await expect(panel).toContainText('新文件已保存并核验');expect(await readFile(saved,'utf8')).toBe('合成输入内容');
    await panel.getByLabel('本次 Shell 解释器',{exact:true}).selectOption('git_bash');await panel.getByLabel('原生选择显式输入文件',{exact:true}).uncheck();await panel.getByLabel('明确产物文件名（每行一个，最多十个）',{exact:true}).fill('');await panel.getByLabel('完整 Shell 脚本',{exact:true}).fill("printf '%s\\n' '合成 Bash 返回证据'");await panel.getByLabel('明确核验 stdout 包含文本（可留空）',{exact:true}).fill('合成 Bash 返回证据');
    await panel.getByRole('button',{name:'准备 Shell 完整预览',exact:true}).click();await panel.getByRole('button',{name:'原生批准此完整 Shell 脚本',exact:true}).click();await expect(panel.getByLabel('Shell stdout',{exact:true})).toHaveValue(/合成 Bash 返回证据/,{timeout:20000});
    const detected=await page.evaluate(()=>window.orvia.shellDetect());if(!detected.ok)throw Error(detected.message);const executable=detected.result.interpreters.find(i=>i.id==='windows_powershell')!.executable.replace(/'/g,"''");
    await panel.getByLabel('本次 Shell 解释器',{exact:true}).selectOption('powershell');await panel.getByLabel('明确核验 stdout 包含文本（可留空）',{exact:true}).fill('');await panel.getByLabel('完整 Shell 脚本',{exact:true}).fill(`$c=Start-Process -FilePath '${executable}' -ArgumentList @('-NoProfile','-NonInteractive','-Command','Start-Sleep -Seconds 60') -WindowStyle Hidden -PassThru; [IO.File]::WriteAllText((Join-Path (Get-Location) 'child-pid.txt'),[string]$c.Id); Start-Sleep -Seconds 60`);
    await panel.getByRole('button',{name:'准备 Shell 完整预览',exact:true}).click();await panel.getByRole('button',{name:'原生批准此完整 Shell 脚本',exact:true}).click();const marker=path.join(cwd,'child-pid.txt');await expect.poll(async()=>readFile(marker,'utf8').then(Number).catch(()=>0),{timeout:15000}).toBeGreaterThan(0);const child=Number(await readFile(marker,'utf8'));
    const alive=(pid:number)=>JSON.parse(execFileSync(path.resolve('backend/.venv/Scripts/python.exe'),['-c','import json,psutil,sys;print(json.dumps(psutil.pid_exists(int(sys.argv[1]))))',String(pid)],{windowsHide:true,encoding:'utf8',timeout:10000}));expect(alive(child)).toBe(true);
    await expect(panel.getByRole('button',{name:'取消当前 Shell 进程',exact:true})).toBeEnabled();await panel.getByRole('button',{name:'取消当前 Shell 进程',exact:true}).click();await expect(panel.getByLabel('Shell 进程与核验事实',{exact:true})).toContainText('执行已取消',{timeout:15000});await expect(panel.getByLabel('Shell 进程与核验事实',{exact:true})).toContainText('自有后代回收：已核验');expect(alive(child)).toBe(false);
    const history=await page.evaluate(id=>window.orvia.shellHistory({id}),cid);expect(history.ok&&history.result.executions.length===3).toBe(true);
    await app.close();app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();const recovered=await page.evaluate(id=>window.orvia.shellHistory({id}),cid);expect(recovered.ok&&recovered.result.executions.length===3).toBe(true);
    await writeFile(path.join(work,'acceptance.json'),JSON.stringify({module:'V4-008',actual:['Electron/preload/main/Python','SQLite','PowerShell7 and GitBash','native-selected synthetic cwd/input copies','output check and SHA256','new file readback','Windows child alive then gone after cancel','restart facts'],mock:['native dialogs'],cloudCalls:0,executions:3,childReaped:true,exportVerified:true,unverified:['real ordinary WSL distribution','manual native dialogs']},null,2));
  }finally{await app.close();}
});
