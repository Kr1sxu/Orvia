import { describe, expect, it } from 'vitest';
import { mkdtemp, mkdir, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { BackendClient } from '../../apps/desktop/src/main/backend';

describe('M09 Computer 只读界面适配（合成目录）', () => {
  it('授权后可列表、搜索、读取属性和统计大文件，且结果带预算证据', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'orvia-m09-root-'));
    const data = await mkdtemp(path.join(os.tmpdir(), 'orvia-m09-data-'));
    await mkdir(path.join(root, '资料'));
    await writeFile(path.join(root, '资料', '项目说明.txt'), 'synthetic', 'utf8');
    await writeFile(path.join(root, 'large.bin'), Buffer.alloc(1024 * 1024 + 10));
    const backend = new BackendClient(process.cwd(), 5000, { dataDirectory: data, credentials: () => ({}) });
    try {
      const mission = await backend.createMission({ client_request_id: randomUUID(), title: 'M09 合成扫描' });
      const grant = await backend.grantComputer({ mission_id: mission.id, root });
      expect(grant.root_label).toBe(path.basename(root));
      expect(grant.grant_id).toBeTypeOf('string');
      const list = await backend.executeComputer({ mission_id: mission.id, grant_id: grant.grant_id!, call: { tool: 'list_directory', arguments: { path: '.', limit: 100 } } });
      expect(list.data.entries).toHaveLength(2);
      const search = await backend.executeComputer({ mission_id: mission.id, grant_id: grant.grant_id!, call: { tool: 'search_files', arguments: { path: '.', query: '说明', recursive: true, limit: 100 } } });
      expect(search.data.entries).toHaveLength(1);
      const metadata = await backend.executeComputer({ mission_id: mission.id, grant_id: grant.grant_id!, call: { tool: 'get_file_metadata', arguments: { path: 'large.bin' } } });
      expect(metadata.data.path).toBe('large.bin');
      const space = await backend.executeComputer({ mission_id: mission.id, grant_id: grant.grant_id!, call: { tool: 'analyze_directory_space', arguments: { path: '.', top_n: 10, min_size: 1024 * 1024 } } });
      expect(space.data.large_files).toHaveLength(1);
      expect(space.calls_remaining).toBe(196);
    } finally { await backend.stop(); }
  });

  it('越界相对路径由既有 Computer 契约拒绝，不由 UI 绕过', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'orvia-m09-boundary-'));
    const data = await mkdtemp(path.join(os.tmpdir(), 'orvia-m09-boundary-data-'));
    const backend = new BackendClient(process.cwd(), 5000, { dataDirectory: data, credentials: () => ({}) });
    try {
      const mission = await backend.createMission({ client_request_id: randomUUID(), title: 'M09 越界测试' });
      const grant = await backend.grantComputer({ mission_id: mission.id, root });
      await expect(backend.executeComputer({ mission_id: mission.id, grant_id: grant.grant_id!, call: { tool: 'get_file_metadata', arguments: { path: '../outside.txt' } } })).rejects.toThrow('后端拒绝请求');
    } finally { await backend.stop(); }
  });
});
