/** 仅靠滚动距离决定是否跟随；读历史时不因后台消息改变阅读位置。 */
export function nearBottom(scrollTop: number, clientHeight: number, scrollHeight: number) {
  return scrollHeight - scrollTop - clientHeight < 64;
}
export const taskLabels: Record<string, string> = {
  draft: '草稿', running: '处理中', planned: '等待审批', awaiting_approval: '等待审批',
  approved: '已批准', completed: '已完成', failed: '失败', interrupted: '已中断',
  cancelled: '已取消', undone: '已撤销', partially_undone: '部分撤销',
};
/** 中文输入法确认候选词时的 Enter 不能成为提交；兼容 Chromium 的 229 标记。 */
export function submitsMessage(key: string, shift: boolean, composing: boolean, keyCode: number) {
  return key === 'Enter' && !shift && !composing && keyCode !== 229;
}
