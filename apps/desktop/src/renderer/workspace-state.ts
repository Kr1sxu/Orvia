import type {Conversation} from '../main/chat-contracts';

export type WorkspaceVisibility=Record<'development'|'cleanup'|'script'|'desktop'|'browser',boolean>;

/** 只按当前会话的工作流/历史身份显示入口；用户、模型或网页文字不能直接启动能力。 */
export function workspaceVisibility(conversation?:Pick<Conversation,'workflow'|'messages'|'workspace_history'>):WorkspaceVisibility{
  const visible:WorkspaceVisibility={development:false,cleanup:false,script:false,desktop:false,browser:false};
  if(!conversation)return visible;
  const action=conversation.workflow?.action;
  if(action&&action in visible)visible[action as keyof WorkspaceVisibility]=true;
  const history=conversation.workspace_history;
  visible.development ||= !!history?.development;
  visible.cleanup ||= !!history?.cleanup;
  for(const kind of history?.automation??[])visible[kind]=true;
  // 兼容缺少新投影的旧快照；仅认程序消息种类和身份，不按正文关键词猜意图。
  for(const message of conversation.messages){
    const data=message.data;
    if(message.kind==='development'&&typeof data?.draft_id==='string')visible.development=true;
    if(message.kind==='cleanup'&&typeof data?.plan_id==='string')visible.cleanup=true;
    if(message.kind==='automation'){
      const kind=data?.kind;
      if(kind==='script'||kind==='script-export')visible.script=true;
      if(kind==='desktop')visible.desktop=true;
      if(kind==='browser'||kind==='browser-request')visible.browser=true;
    }
  }
  return visible;
}
