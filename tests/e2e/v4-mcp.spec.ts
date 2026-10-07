import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,readFile,writeFile,access} from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import type {} from '../../apps/desktop/src/shared/api';

/** 使用产品固定IPC、真实MCP Python stdio和Windows Job，只有原生确认和选择器模拟。 */
test('V4-007 实际stdio配置审查、分分页工具拒写、逐次取消、真实结果、断连子进程回收和历史',async()=>{
  test.setTimeout(180000);
  const root=path.resolve('artifacts/test-results/V4-007');await mkdir(root,{recursive:true});const work=await mkdtemp(path.join(root,'electron-'));
  const fixture=path.join(work,'synthetic-server.py'),state=path.join(work,'synthetic-server.state.json'),config=path.join(work,'server.json');
  await writeFile(fixture,await readFile(path.resolve('backend/tests/v4_mcp_stdio_fixture.py'),'utf8'));
  await writeFile(config,JSON.stringify({name:'合成 MCP 只读服务',transport:'stdio',executable:path.resolve('backend/.venv/Scripts/python.exe'),args:['-I','-u',fixture,'state'],allowed_tools:['read_echo','write_delete']}));
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_MCP_CONFIG:config,ORVIA_MCP_CONFIRM:'1'};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','REDIS_PASSWORD'])delete env[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/v4-mcp-launch.cjs')],env});let app=await launch();
  const facts=async()=>JSON.parse(await readFile(state,'utf8')) as {parent_pid:number;child_pid:number;calls:number};
  try{
    let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    const created=await page.evaluate(()=>window.orvia.chatCreate({client_request_id:crypto.randomUUID(),title:'MCP合成只读验收'}));if(!created.ok)throw Error(created.message);const cid=created.result.id;
    await page.getByRole('button',{name:'设置',exact:true}).click();
    const panel=page.getByLabel('MCP 外部只读工具',{exact:true});
    await panel.getByRole('button',{name:'选择并审查 MCP 配置',exact:true}).click();await expect(panel).toContainText('服务配置已登记，请单独批准连接。');
    const imported=await page.evaluate(()=>window.orvia.mcpList());if(!imported.ok)throw Error('list');const sid=imported.result.servers[0].id;
    await app.evaluate(()=>{process.env.ORVIA_MCP_CONFIRM='0';});await panel.getByRole('button',{name:'原生批准连接并发现工具',exact:true}).click();await expect(panel).toContainText('已取消连接，未启动或请求服务。');await expect(access(state)).rejects.toThrow();
    await app.evaluate(()=>{process.env.ORVIA_MCP_CONFIRM='1';});await panel.getByRole('button',{name:'原生批准连接并发现工具',exact:true}).click();const review=panel.getByLabel('MCP 准确工具清单',{exact:true});
    await expect(review).toContainText('read_echo');await expect(review).toContainText('write_delete · 被阻止');
    await review.getByRole('button',{name:'原生审查此工具清单',exact:true}).click();await expect(panel).toContainText('准确清单已审查，每次调用仍须参数批准。');expect((await facts()).calls).toBe(0);
    await panel.getByLabel('MCP 调用所属会话',{exact:true}).selectOption(cid);await panel.getByLabel('准确工具名称',{exact:true}).fill('read_echo');await panel.getByLabel('工具参数（JSON，最多 8 KiB）',{exact:true}).fill('{"query":"合成 MCP 返回证据"}');
    await panel.getByRole('button',{name:'准备 MCP 调用准确预览',exact:true}).click();await expect(panel.getByLabel('MCP 调用完整正文',{exact:true})).toHaveValue(/合成 MCP 返回证据/);
    await app.evaluate(()=>{process.env.ORVIA_MCP_CONFIRM='0';});await panel.getByRole('button',{name:'原生批准此 MCP 工具调用',exact:true}).click();await expect(panel).toContainText('已取消，MCP 工具未调用。');expect((await facts()).calls).toBe(0);
    await app.evaluate(()=>{process.env.ORVIA_MCP_CONFIRM='1';});await panel.getByRole('button',{name:'准备 MCP 调用准确预览',exact:true}).click();await panel.getByRole('button',{name:'原生批准此 MCP 工具调用',exact:true}).click();
    const result=panel.getByLabel('MCP 调用事实',{exact:true});await expect(result).toContainText('已收到有效工具响应');await expect(result.getByLabel('工具响应（纯数据，不自动打开 URI）',{exact:true})).toHaveValue(/合成 MCP 返回证据/);expect((await facts()).calls).toBe(1);
    const record=await page.evaluate(id=>window.orvia.mcpHistory({id}),cid);if(!record.ok)throw Error('history');const revision=record.result.executions[0].revision;
    const blocked=await page.evaluate(p=>window.orvia.mcpCallPreview(p),{id:cid,server_id:sid,tool:'write_delete',arguments:{}});expect(blocked.ok).toBe(false);expect((await facts()).calls).toBe(1);
    const history=await page.evaluate(id=>window.orvia.mcpHistory({id}),cid);expect(history.ok&&history.result.executions.length===1).toBe(true);
    const live=await facts();const closed=await page.evaluate(server_id=>window.orvia.mcpDisconnect({server_id}),sid);expect(closed.ok&&closed.result.closed&&closed.result.children_reaped).toBe(true);
    const alive=execFileSync(path.resolve('backend/.venv/Scripts/python.exe'),['-c','import psutil,json,sys;print(json.dumps([psutil.pid_exists(pid) for pid in json.loads(sys.argv[1])]))',JSON.stringify([live.parent_pid,live.child_pid])],{windowsHide:true,encoding:'utf8',timeout:10000});expect(JSON.parse(alive)).toEqual([false,false]);
    await result.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(work,'mcp-local-completed.png')});
    await app.close();app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();const list=await page.evaluate(()=>window.orvia.mcpList());expect(list.ok&&list.result.servers.length===1).toBe(true);if(list.ok)expect(list.result.servers[0].status).not.toBe('ready');
    const recovered=await page.evaluate(id=>window.orvia.mcpHistory({id}),cid);expect(recovered.ok&&recovered.result.executions.length===1).toBe(true);const stale=await page.evaluate(p=>window.orvia.mcpCall(p),{id:cid,server_id:sid,revision});expect(stale.ok).toBe(false);
    await writeFile(path.join(work,'acceptance.json'),JSON.stringify({module:'V4-007',actual:['Electron/preload/main/stdin-stdout','SQLite','Python MCP stdio two-page tools','Windows Job child process','input/output schema','cancel zero calls','one validated result','write blocked','disconnect parent and child gone','restart no authority replay'],mock:['native file picker','native confirm'],cloudCalls:0,toolCalls:1,childrenReaped:true},null,2));
  }finally{await app.close();}
});
