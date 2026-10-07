import {_electron as electron,expect,test,type Page} from '@playwright/test';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import type {} from '../../apps/desktop/src/shared/api';

/** 等待真实请求终态和已持久化消息；不能凭页面出现模型文字宣称完成。 */
async function send(page:Page,text:string){
  await page.getByLabel('输入需求').fill(text);await page.getByLabel('输入需求').press('Enter');
  await expect.poll(()=>page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok||!list.result.conversations.length)return false;const r=await window.orvia.chatGet({id:list.result.conversations[0].id});return r.ok&&!r.result.workflow&&r.result.messages.some(message=>message.role==='assistant');})).toBe(true);
}

test('V4-006 明确选记忆、准确改写取消/批准、原问题接续、重启来源撤回和只读Skills',async()=>{
  test.setTimeout(180000);
  const root=path.resolve('artifacts/test-results/V4-006');await mkdir(root,{recursive:true});const work=await mkdtemp(path.join(root,'electron-'));
  const docx=path.join(work,'synthetic-rewrite.docx'),counter=path.join(work,'calls.json');
  execFileSync(path.resolve('backend/.venv/Scripts/python.exe'),['-X','utf8','-c',"from docx import Document\nimport sys\nd=Document()\nd.add_paragraph('合成航线经费为120万元。该项目成本以此合成资料为准。')\nd.save(sys.argv[1])",docx],{windowsHide:true,stdio:'pipe',timeout:10000});
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M20_COUNTER:counter,ORVIA_M20_CONFIRM:'1',ORVIA_M20_INPUTS:JSON.stringify([docx])};
  for(const name of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','REDIS_PASSWORD'])delete env[name];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/v4-rewrite-launch.cjs')],env});
  const calls=async()=>{try{return JSON.parse(await readFile(counter,'utf8')) as {role:string;stream:boolean}[];}catch{return [];}};
  let app=await launch();
  try{
    let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();await send(page,'解释，我的项目是合成航线');
    const cid=await page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok)throw Error('list');return list.result.conversations[0]!.id;});
    await page.getByRole('button',{name:'添加本地资料',exact:true}).click();await page.getByRole('menuitem',{name:'添加文件（最多3个）',exact:true}).click();
    await expect.poll(()=>page.evaluate(async id=>{const r=await window.orvia.chatGet({id});return r.ok&&r.result.materials?.some(item=>item.status==='ready'&&item.title==='synthetic-rewrite.docx');},cid)).toBe(true);
    const attached=await page.evaluate(async id=>{const r=await window.orvia.chatGet({id});if(!r.ok)throw Error('get');return r.result.materials!.find(item=>item.title==='synthetic-rewrite.docx')!;},cid);
    await page.getByRole('button',{name:'设置',exact:true}).click();let memory=page.getByLabel('会话上下文与长期记忆',{exact:true});
    await expect(memory).toContainText('当前项目：合成航线');await memory.getByRole('button',{name:'准备待处理摘要与记忆'}).click();await memory.getByRole('button',{name:'原生确认此批发送'}).click();await expect(memory).toContainText('本批整理结束');
    // 重新打开面板读取已保存的记忆，不绕过产品生成或原文支持验证。
    await page.getByRole('button',{name:'关闭设置'}).click();await page.getByRole('button',{name:'设置',exact:true}).click();let panel=page.getByLabel('查询改写与本地检索',{exact:true});
    await panel.getByLabel('原问题',{exact:true}).fill('它的费用');await panel.getByRole('checkbox',{name:'当前项目：合成航线'}).check();
    const before=(await calls()).length;await panel.getByRole('button',{name:'准备查询改写预览'}).click();
    const accurate=panel.getByLabel('改写输入（原问题、明确记忆、资料片段和准确范围）');await expect(accurate).toHaveValue(/"original": "它的费用"/);await expect(accurate).toHaveValue(/合成航线/);await expect(accurate).toHaveValue(/scope_revision/);await expect(accurate).toHaveValue(/allowed_candidates/);
    await app.evaluate(()=>{process.env.ORVIA_M20_CONFIRM='0';});await panel.getByRole('button',{name:'原生确认此批查询改写'}).click();await expect(panel).toContainText('已取消发送，模型未调用');expect((await calls()).length).toBe(before);
    await app.evaluate(()=>{process.env.ORVIA_M20_CONFIRM='1';});await panel.getByRole('button',{name:'准备查询改写预览'}).click();await panel.getByRole('button',{name:'原生确认此批查询改写'}).click();
    await expect(panel.getByLabel('查询改写结果')).toContainText('合成航线的费用');expect((await calls()).length).toBe(before+1);
    await panel.getByRole('button',{name:'在本机检索原问题和有效候选'}).click();const found=panel.getByLabel('查询改写检索结果');await expect(found).toContainText('保留原问题：它的费用');await expect(found).toContainText('120万元');await expect(found).toContainText('关键词');expect((await calls()).length).toBe(before+1);
    await found.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(work,'approved-search.png')});
    const saved=await page.evaluate(async id=>{const r=await window.orvia.rewriteHistory({id});if(!r.ok)throw Error('history');return r.result.records.find(record=>record.status==='rewritten')!;},cid);expect(saved.original).toBe('它的费用');expect(saved.revision).toMatch(/^[a-f0-9]{64}$/);
    await app.close();app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'设置',exact:true}).click();panel=page.getByLabel('查询改写与本地检索',{exact:true});await panel.getByText('本会话改写记录（最多显示二十条）',{exact:true}).click();await expect(panel).toContainText('原问题：它的费用');await expect(panel).toContainText('候选：合成航线的费用');
    const removed=await page.evaluate(q=>window.orvia.chatMaterialRemove(q),{id:cid,kind:attached.kind,evidence_id:attached.evidence_id});expect(removed.ok).toBe(true);
    const fallback=await page.evaluate(q=>window.orvia.rewriteSearch(q),{id:cid,query:saved.original,revision:saved.revision!});if(!fallback.ok)throw Error(fallback.message);
    expect(fallback.result.queries).toEqual(['它的费用']);expect(fallback.result.rewrite.status).toBe('original');expect(fallback.result.rewrite.reason).toBe('SOURCE_CHANGED');expect(fallback.result.evidence).toEqual([]);expect((await calls()).length).toBe(before+1);
    await panel.getByLabel('原问题',{exact:true}).fill('它的费用');await panel.getByRole('button',{name:'直接在本机检索原问题'}).click();await expect(panel.getByLabel('查询改写检索结果')).toContainText('0 个原文片段');
    const skills=page.getByLabel('Skills 工作流',{exact:true});await skills.getByLabel('运行工作流',{exact:true}).selectOption('query-rewrite');await skills.getByLabel('本地工作流所属会话',{exact:true}).selectOption(cid);
    await skills.getByLabel('只读本机会话与资料',{exact:true}).check();await skills.getByLabel('工作流输入（JSON）',{exact:true}).fill('{"query":"费用","revision":""}');await skills.getByRole('button',{name:'预览本地工作流',exact:true}).click();
    const execution=skills.getByLabel('Skill 执行结果',{exact:true});await expect(execution).toContainText('已完成只读工作流');await execution.getByText('查看工具事实',{exact:true}).click();await expect(execution).toContainText('费用');await expect(execution).toContainText('NO_APPROVED_REWRITE');
    expect((await calls()).length).toBe(before+1);await execution.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(work,'local-skills-after-withdrawal.png')});
    await writeFile(path.join(work,'acceptance.json'),JSON.stringify({module:'V4-006',actual:['Electron renderer/preload/main/stdin-stdout','SQLite facts','native-approved synthetic memory','DOCX local extraction via selected file','local FTS search','rewrite history restart','material withdrawal invalidates approved candidate','readonly query-rewrite Skill without folder/gateway'],mock:['Main HTTP transport','native dialogs'],realCloud:false,cancelCalls:0,approvedRewriteCalls:1,postWithdrawalCalls:0,skillsCalls:0,original:'它的费用',sourceWithdrawn:true},null,2));
  }finally{await app.close();}
});
