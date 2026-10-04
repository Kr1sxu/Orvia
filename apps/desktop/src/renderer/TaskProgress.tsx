import React from 'react';
import type {Conversation} from '../main/chat-contracts';

const labels:Record<string,string>={not_started:'未开始',running:'处理中',waiting_authorization:'等待目录授权',waiting_approval:'等待审批',waiting_input:'等待必要信息',unsupported:'不支持',limited:'仅部分结果',blocked:'前置结果缺失',completed:'已完成',accepted:'已接受未执行或受限范围',failed:'失败',cancelled:'已取消',interrupted:'已中断'};
/** 历史进度只读展示；重开不会获得新的续步token或触发扫描/模型。 */
export function TaskProgress({progress}:{progress:NonNullable<Conversation['task_progress']>}){
  return <details className="source-detail task-progress" aria-label="完整目标进度" open={!['completed','cancelled'].includes(progress.state)}><summary>本次目标进度</summary>
    <details><summary>查看完整原始需求</summary><p className="message-text">{progress.instruction}</p></details>
    {progress.state==='interrupted'&&<p>请求已中断，以下进度已保留。没有自动重放扫描、模型或文件操作；请核对后发起新的明确需求。</p>}
    <ol>{progress.steps.map(step=><li key={step.index}><strong>{labels[step.status]}：</strong>{step.title}{step.detail&&<details><summary>原因与范围</summary><p>{step.detail}</p></details>}</li>)}</ol>
    {progress.steps.some(step=>step.status==='accepted')&&<p>接受限制不等于该目标已经完成；未执行项不会产生虚构结果。</p>}
  </details>;
}
