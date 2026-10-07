import {_electron as electron,expect,test,type Page} from '@playwright/test';
import {mkdir,mkdtemp,readFile} from 'node:fs/promises';
import path from 'node:path';
import type {} from '../../apps/desktop/src/shared/api';

const synthetic='解释，合成人甲负责项目合成航线。文件合成方案.md属于项目合成航线。项目合成航线依赖项目合成导航。';
/** 等待真实请求终态及消息持久化，不以页面出现模型文字判断流程完成。 */
async function send(page:Page){
  await page.getByLabel('输入需求').fill(synthetic);await page.getByLabel('输入需求').press('Enter');
  await expect.poll(()=>page.evaluate(async()=>{const r=await window.orvia.chatList();if(!r.ok||!r.result.conversations.length)return false;const c=await window.orvia.chatGet({id:r.result.conversations[0].id});return c.ok&&!c.result.workflow&&c.result.messages.some(m=>m.role==='assistant');})).toBe(true);
}

test('V4-005 原生取消零外发、批准抽取、三类实体有向两跳、跨会话歧义、重启与删除',async()=>{
  test.setTimeout(180000);
  const root=path.resolve('artifacts/test-results/V4-005');await mkdir(root,{recursive:true});const work=await mkdtemp(path.join(root,'electron-'));
  const counter=path.join(work,'calls.json');const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M20_COUNTER:counter,ORVIA_M20_CONFIRM:'0'};
  for(const name of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','REDIS_PASSWORD'])delete env[name];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/v4-graph-launch.cjs')],env});
  const calls=async()=>{try{return JSON.parse(await readFile(counter,'utf8')) as {role:string;stream:boolean}[];}catch{return [];}};
  let app=await launch();
  try{
    let page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();await send(page);
    const first=await page.evaluate(async()=>{const r=await window.orvia.chatList();if(!r.ok)throw Error('list');return r.result.conversations[0].id;});const before=(await calls()).length;
    await page.getByRole('button',{name:'设置',exact:true}).click();let panel=page.getByLabel('实体关系与知识图谱',{exact:true});
    await panel.getByRole('button',{name:'准备实体关系抽取预览'}).click();await expect(panel.getByLabel('图谱本批输入（完整字段与原文）')).toHaveValue(/合成人甲负责项目合成航线/);
    await panel.getByRole('button',{name:'原生确认此批图谱发送'}).click();await expect(panel).toContainText('已取消，模型未调用');expect((await calls()).length).toBe(before);
    await app.close();env.ORVIA_M20_CONFIRM='1';app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'设置',exact:true}).click();panel=page.getByLabel('实体关系与知识图谱',{exact:true});
    await panel.getByRole('button',{name:'准备实体关系抽取预览'}).click();await panel.getByRole('button',{name:'原生确认此批图谱发送'}).click();
    await expect(panel).toContainText('当前展示 4 个实体、3 条关系');await expect(panel).toContainText('本批抽取已按原文校验');expect((await calls()).length).toBe(before+1);
    await panel.getByLabel('实体名称或本地问题').fill('合成人甲');await panel.getByRole('button',{name:'在本机查询关系'}).click();
    let result=panel.getByLabel('本地关系查询结果');await expect(result).toContainText('返回 1 个实体身份、2 条路径');await expect(result).toContainText('合成导航');
    await result.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(work,'two-hop.png')});
    await app.close();app=await launch();page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'新建对话',exact:true}).click();await send(page);const secondBefore=(await calls()).length;
    await page.getByRole('button',{name:'设置',exact:true}).click();panel=page.getByLabel('实体关系与知识图谱',{exact:true});
    await panel.getByRole('button',{name:'准备实体关系抽取预览'}).click();await panel.getByRole('button',{name:'原生确认此批图谱发送'}).click();await expect(panel).toContainText('当前展示 4 个实体、3 条关系');expect((await calls()).length).toBe(secondBefore+1);
    await panel.getByLabel('实体名称或本地问题').fill('合成人甲');await panel.getByRole('button',{name:'在本机查询关系'}).click();result=panel.getByLabel('本地关系查询结果');
    await expect(result).toContainText('返回 2 个实体身份、0 条路径');await expect(result.getByRole('button',{name:/选择实体：合成人甲/})).toHaveCount(2);
    await result.getByRole('button',{name:/选择实体：合成人甲/}).first().click();await expect(result).toContainText('返回 1 个实体身份、2 条路径');expect((await calls()).length).toBe(secondBefore+1);
    const deleted=await page.evaluate(id=>window.orvia.chatDelete({id}),first);expect(deleted.ok).toBe(true);
    await panel.getByRole('button',{name:'在本机查询关系'}).click();await expect(result).toContainText('返回 1 个实体身份、2 条路径');
    expect((await calls()).length).toBe(secondBefore+1);await result.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(work,'after-delete.png')});
  }finally{await app.close();}
});
