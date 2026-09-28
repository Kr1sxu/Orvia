"""M10 显式模型预检：只发合成内容，零重试，不输出密钥或请求/响应正文。"""

import argparse
import asyncio
import json
from pathlib import Path

from live_model_preflight import credentials
from orvia_backend.configuration import Credentials, ModelRegistry
from orvia_backend.configuration.client import ModelClient, ModelUnavailable
from orvia_backend.domain import get_profiles


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-live', action='store_true', required=True)
    parser.parse_args()
    values = credentials()
    presence = {p.role: bool(values.get(p.credential_ref)) for p in get_profiles()}
    report = {'mock': False, 'real_model': True, 'credential_present': presence,
              'max_requests': 1, 'max_output_tokens': 256, 'retries': 0}
    if not all(presence.values()):
        report.update(status='blocked', reason='MISSING_CREDENTIAL')
    else:
        registry = ModelRegistry(Credentials(**{p.role: values[p.credential_ref] for p in get_profiles()}))
        try:
            # M10 主入口只验证 Main；不因预检自动调用其他角色或读取用户资料。
            result = await asyncio.wait_for(ModelClient(registry).complete(get_profiles()[0], [
                {'role': 'user', 'content': 'Synthetic connectivity test. Reply exactly OK.'}
            ], max_tokens=256), timeout=25)
            report.update(status='passed' if result.text else 'blocked',
                          text_present=bool(result.text), usage=result.usage)
        except ModelUnavailable as error:
            report.update(status='blocked', reason=str(error))
        except TimeoutError:
            report.update(status='blocked', reason='TOTAL_TIMEOUT')
    target = Path(__file__).resolve().parents[2] / 'artifacts/test-results/M10/live-preflight.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
