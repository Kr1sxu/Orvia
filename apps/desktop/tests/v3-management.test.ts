import {expect,it} from 'vitest';
import {chatRenameSchema,chatPinSchema,chatIdSchema} from '../src/main/chat-contracts';
const id='6f1b7524-1eac-4567-a6b5-c3c9f563052c';
it('会话管理契约拒绝空标题、控制字符、额外删除权限和非布尔置顶',()=>{
  expect(chatRenameSchema.parse({id,title:'  合成标题  '}).title).toBe('合成标题');
  for(const title of [' ','a\nb','a'.repeat(101)])expect(chatRenameSchema.safeParse({id,title}).success).toBe(false);
  expect(chatPinSchema.safeParse({id,pinned:1}).success).toBe(false);
  expect(chatIdSchema.safeParse({id,force:true}).success).toBe(false);
});
