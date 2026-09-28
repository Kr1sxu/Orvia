import type { CredentialVault } from './index';

export class CredentialSynchronizationError extends Error {
  constructor() { super('凭据存储已更新，但后端同步失败；旧后端已停止，请重启应用。'); }
}

/** 落盘与内存更新不能组成事务；失败时停止旧后端，防止删除后仍使用旧凭据。 */
export async function synchronizeCredentials(vault: Pick<CredentialVault, 'getSecrets'>, backend: {
  replaceCredentials: (secrets: ReturnType<CredentialVault['getSecrets']>) => Promise<unknown>;
  stop: () => Promise<void>;
}): Promise<{ updated: true }> {
  try { await backend.replaceCredentials(vault.getSecrets()); }
  catch { await backend.stop(); throw new CredentialSynchronizationError(); }
  return { updated: true };
}
