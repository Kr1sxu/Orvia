"""显式首次批准后固定工件准备；仅元数据输出，不读Key或用户资料。"""
import asyncio
import json
from pathlib import Path
import time

from orvia_backend.retrieval.model import manifest
from orvia_backend.retrieval.runtime import LocalEmbedder, verify


async def main():
    root = Path(__file__).resolve().parents[2]
    runtime = LocalEmbedder(root / '.orvia')
    report = {'source': manifest(), 'approval': '2026-10-07 user explicitly approved download',
              'model_directory': str(runtime.directory), 'mock': False, 'cloud_model_calls': 0}
    started = time.monotonic()
    try:
        state = await runtime.download()
        report['runtime'] = state
        if state['ready']:
            await asyncio.to_thread(verify, runtime.directory)
            report['verified_files'] = 6
            report['passed'] = True
        else:
            report['passed'] = False
    finally:
        report['elapsed_seconds'] = time.monotonic() - started
        await runtime.close()
        output = root / 'artifacts/test-results/V4-004/download-live.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'passed': report.get('passed', False), 'reason': report.get('runtime', {}).get('reason'),
                          'report': str(output)}, ensure_ascii=False))
    if not report.get('passed'):
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
