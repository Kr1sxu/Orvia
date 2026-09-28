import { promises as fs } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { BackendClient } from '../../apps/desktop/src/main/backend';
import { missionSchema, profileSchema, missionCreateSchema, type Mission } from '../../apps/desktop/src/main/contracts';

const synthetic = { main: 'integration-synthetic-main-key', computer: 'integration-synthetic-computer-key', browser: 'integration-synthetic-browser-key' };
const replacement = { main: 'integration-synthetic-replacement-key' };
const input = { client_request_id: randomUUID(), title: '合成任务：仅验证草稿持久化' };
let directory: string;
let backend: BackendClient;
let mission: Mission;
let schemas: Record<string, object>;
// Pydantic 输出使用组合约束，关闭 Ajv 的非标准严格提示，保留 JSON Schema 标准校验。
const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);

describe('M02 真实 Python / SQLite / TypeScript 契约（无模型调用）', () => {
  beforeAll(async () => {
    const results = path.resolve('artifacts/test-results/M02');
    await fs.mkdir(results, { recursive: true });
    directory = await fs.mkdtemp(path.join(results, 'integration-'));
    schemas = JSON.parse(await fs.readFile('contracts/m02.schema.json', 'utf8'));
    backend = new BackendClient(process.cwd(), 5000, { dataDirectory: directory, credentials: () => synthetic });
    mission = await backend.createMission(input);
  });
  afterAll(async () => { if (backend) await backend.stop(); });

  it('创建草稿、幂等重试、冲突检测、凭据替换和重启恢复', async () => {
    expect(mission.status).toBe('draft');
    expect(await backend.createMission(input)).toEqual(mission);
    await expect(backend.createMission({ ...input, title: '同一请求 ID 的不同内容' })).rejects.toThrow('CONFLICT');
    expect((await backend.configuration()).profiles.every(profile => profile.configured)).toBe(true);
    await backend.replaceCredentials(replacement);
    expect((await backend.configuration()).profiles.map(profile => profile.configured)).toEqual([true, false, false]);
    expect(await backend.getMission(mission.id)).toEqual(mission);
    expect((await backend.missions()).missions).toEqual([mission]);
    await backend.stop();
    backend = new BackendClient(process.cwd(), 5000, { dataDirectory: directory, credentials: () => replacement });
    expect(await backend.getMission(mission.id)).toEqual(mission);
    expect((await backend.missions()).missions).toEqual([mission]);
    expect(await backend.createMission(input)).toEqual(mission);
    // 检查真实数据库及 WAL/SHM 原始字节，不依赖仅查询公开列来判断秘密未落盘。
    for (const filename of await fs.readdir(directory)) {
      if (!filename.startsWith('app.sqlite')) continue;
      const bytes = await fs.readFile(path.join(directory, filename));
      for (const secret of [...Object.values(synthetic), ...Object.values(replacement)]) expect(bytes.includes(Buffer.from(secret))).toBe(false);
    }
  });

  it('Pydantic 导出 Schema 和 Zod 接受同一真实后端响应与输入', () => {
    expect(ajv.compile(schemas.Mission)(mission)).toBe(true);
    expect(missionSchema.safeParse(mission).success).toBe(true);
    expect(ajv.compile(schemas.MissionCreate)(input)).toBe(true);
    expect(missionCreateSchema.safeParse(input).success).toBe(true);
    const validateProfile = ajv.compile(schemas.ModelProfile);
    for (const profile of mission.models) {
      expect(validateProfile(profile)).toBe(true);
      expect(profileSchema.safeParse(profile).success).toBe(true);
    }
  });

  it('Unicode 字符预算与默认 revision 的跨语言边界一致', async () => {
    const unicode = { client_request_id: randomUUID(), title: '🚀'.repeat(200) };
    expect(ajv.compile(schemas.MissionCreate)(unicode)).toBe(true);
    expect(missionCreateSchema.safeParse(unicode).success).toBe(true);
    expect((await backend.createMission(unicode)).title).toBe(unicode.title);
    expect(missionCreateSchema.safeParse({ ...unicode, title: unicode.title + 'x' }).success).toBe(false);
    expect(ajv.compile(schemas.MissionCreate)({ ...unicode, title: unicode.title + 'x' })).toBe(false);
    const { revision: _revision, ...withoutRevision } = mission.models[0];
    expect(ajv.compile(schemas.ModelProfile)(withoutRevision)).toBe(true);
    expect(profileSchema.parse(withoutRevision).revision).toBe(1);
  });

  it.each(['model', 'base_url', 'duplicate_role', 'api_key', 'top_level_key'] as const)('双方拒绝篡改：%s', mutation => {
    const candidate = structuredClone(mission) as unknown as Record<string, unknown>;
    const models = candidate.models as Record<string, unknown>[];
    if (mutation === 'model') models[0].model = 'silent-fallback';
    if (mutation === 'base_url') models[0].base_url = 'https://unexpected.invalid/v1';
    if (mutation === 'duplicate_role') models[1] = structuredClone(models[0]);
    if (mutation === 'api_key') models[0].api_key = 'synthetic-unexpected-key';
    if (mutation === 'top_level_key') candidate.api_key = 'synthetic-unexpected-key';
    expect(ajv.compile(schemas.Mission)(candidate)).toBe(false);
    expect(missionSchema.safeParse(candidate).success).toBe(false);
  });
});
