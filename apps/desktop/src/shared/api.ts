import type { Configuration, Mission, MissionCreate } from '../main/contracts';
/** 渲染端只能请求有限业务接口，没有通用 IPC、后端初始化或凭据读取入口。 */
export interface HealthResult { status: 'ok'; service: 'orvia-backend' }
export type Reply<T> = { ok: true; result: T } | { ok: false; message: string };
export type HealthReply = Reply<HealthResult>;
export type Role = 'main' | 'computer' | 'browser';
export type Settings = Configuration & { mode: 'development' | 'secure_storage'; encryption_available: boolean; credential_error: string | null;
  credentials: { role: Role; configured: boolean; source: 'development_env' | 'safe_storage' | 'missing' }[] };
declare global { interface Window { orvia: {
  health: () => Promise<HealthReply>;
  settings: () => Promise<Reply<Settings>>;
  missions: () => Promise<Reply<{ missions: Mission[] }>>;
  createMission: (input: MissionCreate) => Promise<Reply<Mission>>;
  saveCredential: (input: { role: Role; key: string }) => Promise<Reply<{ updated: true }>>;
  removeCredential: (role: Role) => Promise<Reply<{ updated: true }>>;
} } }
