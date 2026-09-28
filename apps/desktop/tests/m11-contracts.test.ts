import {describe,it,expect} from 'vitest';
import {chatCancelSchema,chatSnapshotSchema} from '../src/main/chat-contracts';
import {chatErrorMessage} from '../src/main/chat-errors';
const id='6f1b7524-1eac-4567-a6b5-c3c9f563052c';
describe('M11 取消与错误证据边界',()=>{
 it('取消绑定会话和请求，拒绝动作、根或任意方法',()=>{
  expect(chatCancelSchema.parse({id,request_id:id})).toEqual({id,request_id:id});
  for(const field of ['operation_id','root','method','command'])expect(chatCancelSchema.safeParse({id,request_id:id,[field]:'synthetic'}).success).toBe(false);
 });
 it('历史与当前状态是有界契约，拒绝伪造状态',()=>{
  const base={id,title:'synthetic',mission_id:id,messages:[],grant:null,operation:null};
  expect(chatSnapshotSchema.safeParse({...base,status:'running',operations:[]}).success).toBe(true);
  expect(chatSnapshotSchema.safeParse({...base,status:'automatically_approved'}).success).toBe(false);
 });
 it('存储故障固定说明后续动作，不回显异常内容',()=>{
  expect(chatErrorMessage('STORAGE_BUSY')).toContain('数据库');
  expect(chatErrorMessage('STORAGE_FULL')).toContain('磁盘空间');
  expect(chatErrorMessage('synthetic-secret-db-path')).not.toContain('synthetic');
 });
});
