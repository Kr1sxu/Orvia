import { spawn } from 'node:child_process';
import { once } from 'node:events';
import path from 'node:path';
import { describe, it, expect } from 'vitest';
import { BackendClient } from '../../apps/desktop/src/main/backend';
import { responseSchema } from '../../apps/desktop/src/main/protocol';

describe('真实 Python 3.12 进程', () => {
  it('真实客户端握手、并发响应关联与退出', async () => {
    const backend = new BackendClient(process.cwd());
    let pid: number | undefined;
    try {
      const results = await Promise.all(Array.from({ length: 8 }, () => backend.health()));
      expect(results).toHaveLength(8);
      // 仅测试读取私有子进程 PID，用 OS 存活检查核验退出，不增加产品 API。
      pid = (backend as unknown as { child: { pid: number } }).child.pid;
      for (const result of results) expect(result).toEqual({ status: 'ok', service: 'orvia-backend' });
    } finally { await backend.stop(); }
    expect(pid).toBeTypeOf('number');
    expect(() => process.kill(pid!, 0)).toThrow();
    await expect(backend.health()).rejects.toThrow();
  });

  it('缺失可执行文件明确失败，不回退到 PATH', async () => {
    const backend = new BackendClient(path.join(process.cwd(), 'artifacts/test-results/M01/missing'));
    try { await expect(backend.health()).rejects.toThrow('无法启动'); }
    finally { await backend.stop(); }
  });

  it('直接跨进程验证中文分片、合并、错误恢复和 EOF', async () => {
    const child = spawn(path.resolve('backend/.venv/Scripts/python.exe'), ['-I', '-u', '-X', 'utf8', '-m', 'orvia_backend'], { windowsHide: true, shell: false, stdio: 'pipe' });
    let stdout = ''; let stderr = '';
    child.stdout.setEncoding('utf8'); child.stdout.on('data', (data) => { stdout += data; });
    child.stderr.setEncoding('utf8'); child.stderr.on('data', (data) => { stderr += data; });
    const closed = once(child, 'close');
    const killTimer = setTimeout(() => child.kill(), 5000);
    try {
      const frame = (id: string, method: string, v = 1) => JSON.stringify({ v, id, method, params: {} }) + '\n';
      const hello = Buffer.from(frame('中文握手', 'hello'));
      child.stdin.write(frame('before', 'health') + '{\n' + frame('old', 'hello', 2));
      const split = hello.indexOf(Buffer.from('中')) + 1;
      child.stdin.write(hello.subarray(0, split));
      await new Promise((resolve) => setTimeout(resolve, 20));
      child.stdin.end(Buffer.concat([hello.subarray(split), Buffer.from(frame('中文检查', 'health') + frame('unknown', 'delete'))]));
      const [code] = await closed;
      expect(code).toBe(0);
      // 允许已知依赖弃用提示；协议错误/其它诊断仍使测试失败。
      const diagnostics = stderr.replace(/^.*LangChainPendingDeprecationWarning: The default value of `allowed_objects`.*\r?\n\s+from langgraph\.checkpoint\.serde\.jsonplus import JsonPlusSerializer\r?\n/gm, '');
      expect(diagnostics).toBe('');
      const responses = stdout.trim().split('\n').map((line) => responseSchema.parse(JSON.parse(line)));
      expect(responses).toHaveLength(6);
      expect(responses[0]).toMatchObject({ ok: false, error: { code: 'NOT_READY' } });
      expect(responses[1]).toMatchObject({ ok: false, error: { code: 'INVALID_REQUEST' } });
      expect(responses[2]).toMatchObject({ ok: false, error: { code: 'UNSUPPORTED_VERSION' } });
      expect(responses[3]).toMatchObject({ id: '中文握手', ok: true });
      expect(responses[4]).toMatchObject({ id: '中文检查', result: { status: 'ok' } });
      expect(responses[5]).toMatchObject({ ok: false, error: { code: 'METHOD_NOT_FOUND' } });
    } finally { clearTimeout(killTimer); child.kill(); }
  });
});
