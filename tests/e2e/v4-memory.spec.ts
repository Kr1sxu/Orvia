import {_electron as electron,expect,test,type Page} from '@playwright/test';
import {mkdir,mkdtemp,readFile} from 'node:fs/promises';
import path from 'node:path';
import type {} from '../../apps/desktop/src/shared/api';

/** 产品消息入口创建真实轮次；只读IPC轮询等待已持久化结果，不假设文字出现即完成。 */
async function send(page:Page,text:string){
  const previous=await page.evaluate(async()=>{const list=await window.orvia.chatList();if(!list.ok||!list.result.conversations.length)return 0;const r=await window.orvia.chatGet({id:list.result.conversations[0].id});return r.ok?r.result.messages.length:0;});
  await page.getByLabel('输入需求').fill(text);await page.getByLabel('输入需求').press('Enter');
  await expect.poll(()=>page.evaluate(async(previous)=>{const list=await window.orvia.chatList();if(!list.ok||!list.result.conversations.length)return false;const r=await window.orvia.chatGet({id:list.result.conversations[0].id});return r.ok&&r.result.messages.length>=previous+2&&!r.result.workflow;},previous)).toBe(true);
}

test('V4-003 五轮/候选、原生取消零外发、批准整理、跨会话本地检索、重启、纠正与忘记',async()=>{
  test.setTimeout(180000);
  const root=path.resolve('artifacts/test-results/V4-003');await mkdir(root,{recursive:true});
  const work=await mkdtemp(path.join(root,'electron-'));const counter=path.join(work,'calls.json');
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M20_COUNTER:counter,ORVIA_M20_CONFIRM:'0'};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','REDIS_PASSWORD'])delete env[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/v4-memory-launch.cjs')],env});
  const calls=async()=>{try{return JSON.parse(await readFile(counter,'utf8')) as {role:string;stream:boolean}[];}catch{return [];}};
  let app=await launch();
  try{
    let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    for(let index=0;index<6;index++)await send(page,'你好');expect(await calls()).toEqual([]);
    await send(page,'解释，我喜欢简洁回答');const before=(await calls()).length;expect(before).toBeGreaterThan(0);
    await page.getByRole('button',{name:'设置',exact:true}).click();let panel=page.getByLabel('会话上下文与长期记忆',{exact:true});
    await expect(panel).toContainText('当前保留 5 轮');await expect(panel).toContainText('表达偏好：简洁回答');
    await panel.getByRole('button',{name:'准备待处理摘要与记忆'}).click();await expect(panel.getByLabel('本批输入（完整字段与原文）')).toHaveValue(/简洁回答/);
    await panel.getByRole('button',{name:'原生确认此批发送'}).click();await expect(panel).toContainText('已取消，模型未调用');expect((await calls()).length).toBe(before);
    await app.close();env.ORVIA_M20_CONFIRM='1';app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'设置',exact:true}).click();panel=page.getByLabel('会话上下文与长期记忆',{exact:true});
    await panel.getByRole('button',{name:'准备待处理摘要与记忆'}).click();await panel.getByRole('button',{name:'原生确认此批发送'}).click();
    await expect(panel).toContainText('本批整理结束');await expect(panel).toContainText('有原文支持');expect((await calls()).length).toBe(before+1);
    await panel.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(work,'approved.png')});
    await page.getByRole('button',{name:'关闭设置'}).click();await page.getByRole('button',{name:'新建对话',exact:true}).click();
    await page.getByRole('button',{name:'设置',exact:true}).click();panel=page.getByLabel('会话上下文与长期记忆',{exact:true});
    await panel.getByLabel('本地记忆问题').fill('简洁');await panel.getByRole('button',{name:'在本机检索记忆'}).click();await expect(panel).toContainText('返回 1 条有界结果');expect((await calls()).length).toBe(before+1);
    await panel.getByRole('button',{name:'查看来源会话的记忆'}).click();await expect(panel.getByRole('button',{name:'保存此条修正'})).toHaveCount(1);
    await panel.getByLabel('修正 表达偏好').fill('详细回答');await panel.getByRole('button',{name:'保存此条修正'}).click();await expect(panel).toContainText('修正已保存为明确用户原文');
    await app.close();app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'设置',exact:true}).click();panel=page.getByLabel('会话上下文与长期记忆',{exact:true});
    await panel.getByLabel('本地记忆问题').fill('详细');await panel.getByRole('button',{name:'在本机检索记忆'}).click();await expect(panel).toContainText('返回 1 条有界结果');
    await panel.getByRole('button',{name:'查看来源会话的记忆'}).click();
    const corrected=panel.locator('article').filter({has:page.getByRole('button',{name:'忘记此条记忆'})}).filter({hasText:'详细回答'});
    await corrected.getByRole('button',{name:'忘记此条记忆'}).click();await expect(panel).toContainText('此条派生记忆已忘记，原文保留');
    await panel.getByLabel('本地记忆问题').fill('详细');await panel.getByRole('button',{name:'在本机检索记忆'}).click();await expect(panel).toContainText('返回 0 条有界结果');
    expect((await calls()).length).toBe(before+1);await page.screenshot({path:path.join(work,'forgotten.png')});
  }finally{await app.close();}
});
