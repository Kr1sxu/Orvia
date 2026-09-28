"""显式真实 Main 合成规划验证：最多3请求，无审批，不修改合成源文件。"""
import argparse
import asyncio
import json
from pathlib import Path
from tempfile import mkdtemp
from uuid import uuid4

from live_model_preflight import credentials
from orvia_backend.application import Application
from orvia_backend.domain import get_profiles


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-live', action='store_true', required=True)
    parser.parse_args()
    values = credentials()
    result_dir = Path(__file__).resolve().parents[2] / 'artifacts/test-results/M10'
    result_dir.mkdir(parents=True, exist_ok=True)
    work = Path(mkdtemp(prefix='live-synthetic-',dir=result_dir))
    root = work / 'files'
    root.mkdir()
    (root / 'sample.txt').write_text('synthetic content',encoding='utf-8')
    app = Application()
    async def call(method, params=None):
        return await app.handle(json.dumps({'v':1,'id':str(uuid4()),'method':method,'params':params or {}}).encode())
    report = {'real_model':True,'mock':False,'max_requests':3,'max_output_tokens_per_request':1024,'retries':0,'approved':False}
    try:
        await call('hello')
        initialized = await call('initialize',{'data_directory':str(work/'db'),'credentials':{p.role:values.get(p.credential_ref) for p in get_profiles()}})
        if not initialized['ok']:
            report.update(status='failed',reason='INITIALIZATION_FAILED')
        else:
            cid = (await call('chat.create',{'client_request_id':str(uuid4()),'title':'M10 合成规划验证'}))['result']['id']
            await call('chat.grant',{'id':cid,'root':str(root)})
            await call('chat.inspect',{'id':cid,'tool':'list_directory','arguments':{'path':'.','limit':100}})
            response = await call('chat.send',{'id':cid,'request_id':str(uuid4()),'text':'这是合成测试目录。请只提出将 sample.txt 重命名为 renamed.txt 的单步计划，不执行。已有观察里可见该文件，请直接通过 propose 提交 kind=plan，actions=[{kind:rename,source:sample.txt,destination:renamed.txt}]。'})
            operation = response.get('result',{}).get('operation')
            expected = [{'kind':'rename','source':'sample.txt','destination':'renamed.txt'}]
            report.update(status='passed' if operation and operation['status']=='planned' and operation['actions']==expected else 'failed',
                          plan_valid=bool(operation and operation['actions']==expected),
                          source_unchanged=(root/'sample.txt').read_text(encoding='utf-8')=='synthetic content',
                          destination_absent=not (root/'renamed.txt').exists())
            if not operation:
                report['error_codes']=[m.get('data',{}).get('code') for m in response.get('result',{}).get('messages',[]) if m['kind']=='error' and m.get('data')]
    finally:
        await app.close()
    (result_dir/'live-plan.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(asyncio.run(main()))
