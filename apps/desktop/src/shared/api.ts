/** 渲染进程仅获得业务健康检查，不获得通用 IPC 或进程入口。 */
export interface HealthResult { status: 'ok'; service: 'orvia-backend' }
export type HealthReply = { ok: true; result: HealthResult } | { ok: false; message: string };
declare global { interface Window { orvia: { health: () => Promise<HealthReply> } } }
