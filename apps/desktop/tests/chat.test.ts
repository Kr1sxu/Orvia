import {describe,expect,it} from 'vitest';
import {chatApprovalSchema,chatSendSchema,chatIdSchema,parseInspect} from '../src/main/chat-contracts';
import {chatErrorMessage} from '../src/main/chat-errors';
import {mayInvoke} from '../src/main/ipc-policy';
import {readFileSync} from 'node:fs';

const id='6f1b7524-1eac-4567-a6b5-c3c9f563052c';
describe('M10 固定会话边界（无模型）',()=>{
 it('拒绝绝对根、模型覆盖和原始命令字段',()=>{
  expect(chatIdSchema.safeParse({id,root:'C:/Users'}).success).toBe(false);
  expect(chatSendSchema.safeParse({id,request_id:id,text:'合成',model:'other'}).success).toBe(false);
  expect(()=>parseInspect({id,tool:'run_readonly_template',arguments:{}})).toThrow();
  expect(()=>parseInspect({id,tool:'list_directory',arguments:{path:'.',command:'anything'}})).toThrow();
 });
 it('审批必须绑定会话、操作、版本，额外字段拒绝',()=>{
  const valid={id,operation_id:id,revision:'a'.repeat(64)};
  expect(chatApprovalSchema.parse(valid)).toEqual(valid);
  expect(chatApprovalSchema.safeParse({...valid,revision:'old'}).success).toBe(false);
  expect(chatApprovalSchema.safeParse({...valid,actions:[]}).success).toBe(false);
 });
 it('参数个数和顶层窗口来源仍强制校验',()=>{
  const url='file:///orvia/index.html';
  expect(mayInvoke(true,true,url,url,[{id}],1)).toBe(true);
  expect(mayInvoke(true,false,url,url,[{id}],1)).toBe(false);
  expect(mayInvoke(true,true,'https://other.test',url,[{id}],1)).toBe(false);
  expect(mayInvoke(true,true,url,url,[{id},'extra'],1)).toBe(false);
 });
 it('错误映射不回显输入，区分权限和越界',()=>{
  expect(chatErrorMessage('PERMISSION_DENIED')).toContain('授权');
  expect(chatErrorMessage('path_denied')).toContain('范围');
  expect(chatErrorMessage('synthetic-private-input')).not.toContain('synthetic');
 });
 it('preload 没有通用chat方法和后端grant入口',()=>{
  const source=readFileSync('apps/desktop/src/main/preload.ts','utf8');
  expect(source).not.toMatch(/chatGrant:|chat:\s|executeCommand:|invoke:\s/);
  expect(source).toContain("chatApprove: (input: unknown) => ipcRenderer.invoke('orvia:chat-approve', input)");
 });
});
