import {describe,it,expect} from 'vitest';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {developmentContextRequestSchema,developmentGenerateRequestSchema,developmentApplyRequestSchema,cleanupExecuteRequestSchema,cleanupRestoreRequestSchema,developmentDraftSchema,cleanupPlanSchema} from '../src/main/chat-contracts';
import {M17Workspace} from '../src/renderer/M17Cards';

const id='6f1b7524-1eac-4567-a6b5-c3c9f563052c',hash='a'.repeat(64);

describe('M17 固定桌面契约',()=>{
  it('上下文、逐文件写入和清理仅接受身份与选择，不接受绝对路径或模型覆盖',()=>{
    expect(developmentContextRequestSchema.safeParse({id,requirement:'合成更改',paths:['src/App.tsx'],sources:[],result_message_id:null}).success).toBe(true);
    const generate={id,paths:['src/App.tsx'],sources:[],result_message_id:null,kind:'code',stack:'react-vite',requirement:'合成更改',context_revision:hash,request_id:id};
    expect(developmentGenerateRequestSchema.safeParse(generate).success).toBe(true);
    for(const extra of [{root:'C:/any'},{model:'other'},{base_url:'https://other'},{file_content:'hidden'},{approved:true}])
      expect(developmentGenerateRequestSchema.safeParse({...generate,...extra}).success).toBe(false);
    expect(developmentApplyRequestSchema.safeParse({id,draft_id:id,revision:hash,index:0}).success).toBe(true);
    expect(developmentApplyRequestSchema.safeParse({id,draft_id:id,revision:hash,index:0,path:'C:/any'}).success).toBe(false);
    expect(cleanupExecuteRequestSchema.safeParse({id,plan_id:id,revision:hash,indices:[0]}).success).toBe(true);
    expect(cleanupExecuteRequestSchema.safeParse({id,plan_id:id,revision:hash,indices:[0],permanent:true}).success).toBe(false);
    expect(cleanupRestoreRequestSchema.safeParse({id,plan_id:id,index:0}).success).toBe(true);
  });
  it('草稿与清理计划含审查和恢复事实，模型文字按纯文本展示',()=>{
    expect(developmentDraftSchema.safeParse({draft_id:id,kind:'code',stack:'web-native',revision:hash,files:[{index:0,path:'index.html',content:'<script>bad</script>',diff:'+<script>bad</script>',status:'pending',operation:'create'}],prototype:null}).success).toBe(true);
    expect(cleanupPlanSchema.safeParse({plan_id:id,revision:hash,status:'planned',entries:[{index:0,name:'old.tmp',size:12,mtime:'2026-08-01',risk:'low',status:'pending',error:null}],truncated:false,logical_bytes:12,quarantined_bytes:0,released_bytes:0,restore_until:'2026-10-30'}).success).toBe(true);
    const html=renderToStaticMarkup(React.createElement(M17Workspace,{cid:id,visible:{development:true,cleanup:true},authorized:true,disabled:false,messages:[{id,role:'assistant',kind:'development',text:'<script>越权</script>',created_at:'2026-09-29',data:{draft_id:id,kind:'code'}}],availableSources:[],notice:()=>{},refresh:async()=>{}}));
    expect(html).not.toContain('<script>');
    expect(html).toContain('代码生成与网页原型');
    expect(html).toContain('系统清理');
  });
});
