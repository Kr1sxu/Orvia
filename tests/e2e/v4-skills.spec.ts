import {_electron as electron,expect,test} from '@playwright/test';
import {mkdir,mkdtemp,writeFile,readFile} from 'node:fs/promises';
import path from 'node:path';

test('V4-002 Skills启停、取消与真实只读组合事实',async()=>{
  const root=path.resolve('artifacts/test-results/V4-002');await mkdir(root,{recursive:true});
  const work=await mkdtemp(path.join(root,'electron-')),files=path.join(work,'files');await mkdir(files);await writeFile(path.join(files,'synthetic.txt'),'fixture');
  const pkg=path.join(work,'package');await mkdir(pkg);
  const object={type:'object',additionalProperties:true};
  await writeFile(path.join(pkg,'SKILL.md'),'# 合成属性读取\n此说明没有执行权限。');
  await writeFile(path.join(pkg,'workflow.json'),JSON.stringify({schema_version:1,id:'synthetic-meta',name:'合成属性读取',version:'1.0.0',description:'仅观察显式目录中的属性',
    input_schema:{type:'object',properties:{path:{type:'string',maxLength:1000}},required:['path']},output_schema:object,dependencies:[],
    steps:[{id:'observe',tool:'get_file_metadata',arguments:{path:{from_input:'path'}},output_schema:object}],output:{metadata:{from_step:'observe'}}}));
  const counter=path.join(work,'calls.json');
  const env={...process.env,ORVIA_DEV_DATA_DIR:path.join(work,'profile'),ORVIA_M20_DIRECTORY:files,ORVIA_M20_CONFIRM:'1',ORVIA_M20_COUNTER:counter};
  for(const key of ['ELECTRON_RUN_AS_NODE','DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY','REDIS_PASSWORD'])delete env[key];
  const launch=()=>electron.launch({args:[path.resolve('tests/e2e/m20-launch.cjs')],env});let app=await launch();
  try{
    const page=await app.firstWindow();await expect(page.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await page.getByRole('button',{name:'设置',exact:true}).click();const panel=page.getByLabel('Skills 工作流',{exact:true});
    await expect(panel.getByRole('button',{name:'禁用 File Organize'})).toBeVisible();
    await panel.getByRole('button',{name:'禁用 File Organize'}).click();await expect(panel.getByRole('button',{name:'启用 File Organize'})).toBeVisible();
    await expect(panel.getByRole('button',{name:'选择目录并预览执行'})).toBeDisabled();
    await panel.getByRole('button',{name:'启用 File Organize'}).click();await panel.getByRole('button',{name:'选择目录并预览执行'}).click();
    const result=panel.getByLabel('Skill 执行结果');await expect(result).toContainText('已完成只读工作流');
    await result.getByText('查看工具事实',{exact:true}).click();await expect(result).toContainText('synthetic.txt');
    await panel.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(work,'skills.png')});
    // 测试启动器模拟原生取消；真实产品没有环境批准入口。
    await app.evaluate(()=>{process.env.ORVIA_M20_CONFIRM='0';});
    await panel.getByRole('button',{name:'选择目录并预览执行'}).click();await expect(panel).toContainText('已取消，工具未执行。');
    await app.evaluate((_app,p)=>{process.env.ORVIA_M20_DIRECTORY=p;},pkg);
    await panel.getByRole('button',{name:'选择并审查 Skill 包'}).click();await expect(panel).toContainText('已取消导入。');
    await expect(panel.getByRole('button',{name:'禁用 合成属性读取'})).toHaveCount(0);
    await app.evaluate(()=>{process.env.ORVIA_M20_CONFIRM='1';});await panel.getByRole('button',{name:'选择并审查 Skill 包'}).click();
    await expect(panel.getByRole('button',{name:'禁用 合成属性读取'})).toBeVisible();
    await panel.getByLabel('运行工作流').selectOption('synthetic-meta');await panel.getByLabel('工作流输入（JSON）').fill('{"path":"synthetic.txt"}');
    await app.evaluate((_app,p)=>{process.env.ORVIA_M20_DIRECTORY=p;},files);await panel.getByRole('button',{name:'选择目录并预览执行'}).click();
    await expect(result).toContainText('文件属性：已核验');
    await app.close();app=await launch();const restarted=await app.firstWindow();await expect(restarted.getByText('本地服务已连接',{exact:true})).toBeVisible();
    await restarted.getByRole('button',{name:'设置',exact:true}).click();const saved=restarted.getByLabel('Skills 工作流',{exact:true});
    await expect(saved.getByRole('button',{name:'禁用 合成属性读取'})).toBeVisible();
    await saved.getByText('最近工作流记录',{exact:true}).click();await saved.getByRole('button',{name:'合成属性读取 · 已完成只读工作流'}).click();
    await saved.getByLabel('Skill 执行结果').getByText('查看工具事实',{exact:true}).click();await expect(saved.getByLabel('Skill 执行结果')).toContainText('synthetic.txt');
    await restarted.screenshot({path:path.join(work,'restart.png')});
    let calls=[];try{calls=JSON.parse(await readFile(counter,'utf8'));}catch{}expect(calls).toEqual([]);
  }finally{await app.close();}
});
