import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {expect,it} from 'vitest';
import {workspaceVisibility} from '../src/renderer/workspace-state';
import {workspaceHistorySchema} from '../src/main/chat-contracts';
import {M17Workspace} from '../src/renderer/M17Cards';
import {M18Workspace} from '../src/renderer/M18Cards';

const cid='6f1b7524-1eac-4567-a6b5-c3c9f563052c';
const empty={development:false,cleanup:false,script:false,desktop:false,browser:false};
const history={development:null,cleanup:null,automation:[]} as const;
it('无会话、普通消息及正文中的能力名称都不打开工作区',()=>{
  expect(workspaceVisibility()).toEqual(empty);
  for(const kind of ['text','natural_request','natural_answer','source','document'] as const){
    expect(workspaceVisibility({messages:[{id:cid,role:'assistant',kind,text:'生成 React 清理 Temp 运行 Python 桌面 浏览器',data:{action:'script'},created_at:''}]})).toEqual(empty);
  }
});
it.each(['development','cleanup','script','desktop','browser'] as const)('%s只显示自身，工作流状态不改变可见性',action=>{
  for(const state of ['waiting_input','waiting_approval','running'] as const){
    const visible=workspaceVisibility({messages:[],workflow:{action,state,request_id:cid,continuation_id:cid,reason:'',question:''}});
    expect(visible).toEqual({...empty,[action]:true});
    const common={cid,visible,authorized:false,disabled:true,notice:()=>{},refresh:async()=>{}};
    const html=renderToStaticMarkup(action==='development'||action==='cleanup'?<M17Workspace {...common} messages={[]} availableSources={[]}/>:<M18Workspace {...common}/>);
    const labels={development:'代码生成与网页原型',cleanup:'系统清理：旧临时文件隔离',script:'任意脚本：Python隔离执行',desktop:'桌面点击：准确应用与控件',browser:'浏览器写操作：专用会话与实际外发'};
    for(const [kind,label] of Object.entries(labels))expect(html.includes(label)).toBe(kind===action);
  }
});
it('历史投影在消息裁剪后保留入口；切换普通会话不继承能力',()=>{
  const workspace_history={development:{draft_id:cid,kind:'code' as const},cleanup:{plan_id:cid},automation:['script','desktop','browser'] as const};
  const saved={messages:[],workspace_history:{...workspace_history,automation:[...workspace_history.automation]}};
  expect(workspaceVisibility(saved)).toEqual({development:true,cleanup:true,script:true,desktop:true,browser:true});
  expect(workspaceVisibility({messages:[]})).toEqual(empty);
  const html=renderToStaticMarkup(<M17Workspace cid={cid} visible={workspaceVisibility(saved)} history={saved.workspace_history} messages={[]} availableSources={[]} authorized={false} disabled={true} notice={()=>{}} refresh={async()=>{}}/>);
  expect(html).toContain('读取最近已保存代码草稿');expect(html).toContain('读取最近已保存清理计划');
});
it('历史投影契约拒绝未知能力、绝对路径和超出预算的条目',()=>{
  expect(workspaceHistorySchema.safeParse({...history,automation:[]}).success).toBe(true);
  for(const value of [{...history,automation:['shell']},{...history,path:'C:/'},{...history,automation:Array(4).fill('script')}])expect(workspaceHistorySchema.safeParse(value).success).toBe(false);
});
