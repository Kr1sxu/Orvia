import {retryId,retryHistory} from './retry-contracts';
import type {BackendClient} from './backend';

/** 只读SQLite重试事实，不弹权限窗口、不授予分类，也不能通过状态查询重放业务请求。 */
export function registerRetry({handle,backend}:{
  handle:(channel:string,count:number,action:(...args:unknown[])=>Promise<unknown>)=>void;
  backend:()=>BackendClient;
}){
  handle('orvia:retry-history',1,async input=>{
    const request=retryId.parse(input);
    const result=retryHistory.parse(await backend().retryHistory(request));
    if(result.id!==request.id)throw new Error('重试事实与明确选择的会话不对应。');
    return result;
  });
}
