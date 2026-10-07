"""显式固定本地模型的最大文本批次/Token预算实测；只用合成文本。"""
import asyncio
import json
import math
import os
from pathlib import Path
import time
import sys

from orvia_backend.retrieval.runtime import LocalEmbedder, EmbeddingError


async def main():
    model = os.environ.get('ORVIA_EMBEDDING_MODEL_PATH')
    if not model:
        raise SystemExit('须显式提供已批准模型目录；不下载模型。')
    root = Path('artifacts/test-results/V4-004').resolve()
    work = root / ('resource-' + str(time.time_ns()))
    work.mkdir(parents=True)
    runtime = LocalEmbedder(work / 'profile')
    token_only = sys.argv[1:] == ['--token-only']
    if sys.argv[1:] and not token_only:
        raise SystemExit('仅支持--token-only最小复验选项')
    report = {'mock': False, 'cloud_model_calls': 0, 'batch': 8, 'chars_per_text': 600,
              'mode': 'token-only' if token_only else 'full'}
    try:
        assert (await runtime.prepare(model))['ready']
        if not token_only:
            texts = [(f'合成测试资料编号{i}，公共交通与低通滤波。' * 40)[:600] for i in range(8)]
            start = time.monotonic()
            vectors = await runtime.embed(texts)
            report['full_batch_seconds'] = time.monotonic() - start
            assert len(vectors) == 8 and all(len(v) == 1024 for v in vectors)
            assert all(all(math.isfinite(x) for x in v) and abs(math.hypot(*v)-1)<1e-4 for v in vectors)
            report['full_batch_completed'] = True
            try:
                await runtime.embed(['a' * 601])
            except EmbeddingError as error:
                assert error.code == 'MODEL_INPUT_LIMIT'
                report['char_limit_rejected'] = True
            else:
                raise AssertionError('601字符应拒绝')
        start = time.monotonic()
        try:
            # 固定Qwen分词器实测600个𒀀为1201 tokens，emoji600仅601，不能假设字节=token。
            await runtime.embed(['𒀀' * 600])
        except EmbeddingError as error:
            assert error.code == 'MODEL_TOKEN_LIMIT',error.code
            report['token_limit_rejected'] = True
            report['token_fixture_tokens'] = 1201
            report['token_check_seconds'] = time.monotonic() - start
            assert not runtime.status()['ready'], '超限工作器不得继续提供晚到结果'
        else:
            raise AssertionError('超过1024 tokens的合成文本应拒绝静默截断')
        report['passed'] = True
    finally:
        report['runtime'] = runtime.status()
        await runtime.close()
        output = work / 'resources.json'
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'passed': report.get('passed', False), 'report': str(output)}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
