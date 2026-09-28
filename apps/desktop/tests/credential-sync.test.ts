import { expect, it, vi } from 'vitest';
import { synchronizeCredentials, CredentialSynchronizationError } from '../src/main/credentials/synchronize';

it('凭据已落盘但同步失败时停止旧后端并明确报告部分成功，不重试', async () => {
  const key = 'synthetic-sync-key';
  const backend = { replaceCredentials: vi.fn().mockRejectedValue(new Error(key)), stop: vi.fn().mockResolvedValue(undefined) };
  let error: unknown;
  try { await synchronizeCredentials({ getSecrets: () => ({ main: key }) }, backend); } catch (caught) { error = caught; }
  expect(error).toBeInstanceOf(CredentialSynchronizationError);
  expect(String(error)).toContain('存储已更新');
  expect(String(error)).not.toContain(key);
  expect(backend.stop).toHaveBeenCalledOnce();
  expect(backend.replaceCredentials).toHaveBeenCalledOnce();
});

it('成功同步只传当前凭据快照，不停止后端', async () => {
  const backend = { replaceCredentials: vi.fn().mockResolvedValue({ updated: true }), stop: vi.fn() };
  expect(await synchronizeCredentials({ getSecrets: () => ({}) }, backend)).toEqual({ updated: true });
  expect(backend.replaceCredentials).toHaveBeenCalledWith({});
  expect(backend.stop).not.toHaveBeenCalled();
});
