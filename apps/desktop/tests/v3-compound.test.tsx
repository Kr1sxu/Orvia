import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {expect,it} from 'vitest';
import {TaskProgress} from '../src/renderer/TaskProgress';
import {taskProgressSchema,workflowSchema} from '../src/main/m20-contracts';

it('目标进度区分实际完成、接受未执行、剩余目标且重启不授予权限',()=>{
 const progress=taskProgressSchema.parse({request_id:'6f1b7524-1eac-4567-a6b5-c3c9f563052c',state:'interrupted',instruction:'完整原需求',steps:[
  {index:0,title:'扫描',kind:'list',status:'completed',detail:'仅一级'},
  {index:1,title:'闲置应用',kind:'unsupported',status:'accepted',detail:'未实现'},
  {index:2,title:'文档',kind:'publication',status:'not_started',detail:''}]});
 const html=renderToStaticMarkup(<TaskProgress progress={progress}/>);
 for(const text of ['已完成','已接受未执行','未开始','没有自动重放','完整原需求'])expect(html).toContain(text);
 expect(html).not.toContain('<button');
 expect(workflowSchema.safeParse({request_id:progress.request_id,continuation_id:progress.request_id,state:'waiting_input',reason:'task_decision',action:'task_decision',question:'接受或取消'}).success).toBe(true);
 expect(taskProgressSchema.safeParse({...progress,approved:true}).success).toBe(false);
});
