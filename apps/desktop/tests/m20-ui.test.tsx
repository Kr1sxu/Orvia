import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {it,expect} from 'vitest';
import {DirectoryAnswer,LiveResult,PartialModelMessage} from '../src/renderer/M20Results';
import {chatMessageSchema} from '../src/main/chat-contracts';
import {newStream} from '../src/renderer/m20-state';
import {readFileSync} from 'node:fs';

const id='6f1b7524-1eac-4567-a6b5-c3c9f563052c';
it('程序目录回答直接展示、明确分类与全发现入口，不执行恶意路径',()=>{
  const html=renderToStaticMarkup(<DirectoryAnswer cid={id} disabled={false} message={{data:{scan_id:id,summary:{scope:'合成目录',discovered:121,visited:125,depth:3,recursive:true,truncated:true,complete:false,reason:'深度预算'},entries:[{path:'<script>bad()</script>.txt',kind:'file',size:3,category:'文档'}]},kind:'scan'} as any}/>);
  expect(html).toContain('完整已发现清单');expect(html).toContain('121');expect(html).toContain('没有读取文件正文');expect(html).toContain('深度预算');expect(html).not.toContain('<script>');expect(html).toContain('&lt;script&gt;');
});
it('暂态模型文本没有成功引用或成品按钮；主输入无需模式且不禁用草稿',()=>{
  const html=renderToStaticMarkup(<LiveResult stream={{...newStream(id,id),text:'未完成<script>bad()</script>'}}/>);
  expect(html).toContain('引用待完整结果校验');expect(html).not.toContain('制作 Word');expect(html).not.toContain('<script>');
  const source=readFileSync('apps/desktop/src/renderer/main.tsx','utf8');expect(source).toContain('placeholder="你想做些什么"');expect(source).not.toContain('aria-label="需求类型"');expect(source).toContain('value={text} onChange=');expect(source).not.toContain('!busy && !remoteBusy && !showSettings) input.current?.focus');
});
it('长路径使初始结果少于100时仍显示续页，不把截断初页冒充全部',()=>{
  const html=renderToStaticMarkup(<DirectoryAnswer cid={id} disabled={false} message={{data:{scan_id:id,summary:{scope:'合成长路径',discovered:17,visited:17,depth:1,recursive:false,complete:true,truncated:false},entries:[{path:'长'.repeat(400)+'.txt',kind:'file',size:3,category:'文档'}]},kind:'directory_result'} as any}/>);
  expect(html).toContain('下一页');expect(html).toContain('每批至多100项');expect(html).toContain('当前展示1项');expect(html).not.toContain('第1/1页');
});
it('部分模型历史有真实身份与前缀预算，但不能出现成功引用或成品入口',()=>{
  const message={id,role:'assistant' as const,kind:'model_partial' as const,text:'部分模型文字',created_at:'2026-10-03',data:{request_id:id,stream_id:id,last_seq:3,state:'interrupted',text:'真实前缀<script>bad()</script>',provisional:true}};
  expect(chatMessageSchema.safeParse(message).success).toBe(true);
  expect(chatMessageSchema.safeParse({...message,data:{...message.data,provisional:false}}).success).toBe(false);
  expect(chatMessageSchema.safeParse({...message,data:{...message.data,text:'\n'.repeat(16000)}}).success).toBe(false);
  const html=renderToStaticMarkup(<PartialModelMessage message={message}/>);expect(html).toContain('不能作为成功回答或制作成品');expect(html).toContain('真实前缀');expect(html).toContain('&lt;script&gt;');expect(html).not.toContain('<script>');expect(html).not.toContain('<button');
});
