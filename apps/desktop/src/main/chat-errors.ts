/** 错误码映射为固定中文，不展示供应商正文、路径或异常输入。 */
export function chatErrorMessage(code: string): string {
  const messages: Record<string, string> = {
    PERMISSION_DENIED: '目录授权已失效，请重新选择目录。', permission_denied: '目录身份发生变化，请重新授权。',
    PATH_DENIED: '路径超出授权范围或包含不允许的链接。', path_denied: '路径超出授权范围或包含不允许的链接。',
    invalid_root: '请选择可访问的普通本地目录，不支持网络目录或链接。',
    path_unavailable: '路径不存在或无法访问，请刷新文件信息。',
    CONFLICT: '内容或目标发生冲突，请重新查看结果并生成计划。',
    INVALID_STATE: '任务状态已变化，当前操作不可用，请刷新会话。',
    STALE_PLAN: '计划已过期，请查看最新计划后再审批。',
    STALE_APPROVAL: '计划已变化或不属于当前会话，请查看最新版本。',
    ROOT_CHANGED: '目录身份已变化，请重新选择目录并生成计划。',
    SOURCE_CHANGED: '源文件在计划生成后发生变化，请重新生成计划。',
    RECOVERY_CONFLICT: '中断步骤无法安全核验，恢复已停止，不会重放不确定动作。',
    REQUEST_INTERRUPTED: '上次消息处理已中断，请检查现有结果后用新消息继续。',
    NOT_FOUND: '会话或任务不存在，请刷新会话列表。',
    MISSING_CREDENTIAL: '缺少固定模型凭据，请在设置中检查配置。',
    MODEL_UNAVAILABLE: '固定模型暂不可用，本轮未执行文件动作。',
    BUDGET_EXCEEDED: '已达到本次任务预算，请停止并检查任务结果。',
    INVALID_PARAMS: '请求参数不符合当前业务接口。',
    UNDO_CONFLICT: '文件已变化，撤销停止；请查看最新账本状态。',
  };
  return messages[code] ?? '操作未完成，请刷新会话查看事实状态；不会自动重放文件动作。';
}
