"""显式合成资料的真实本地Qwen基准；不读凭据、不下载模型、不访问真实资料。"""
import asyncio
import json
import math
import os
import platform
import importlib.metadata
from pathlib import Path
import sys
import time
import psutil

from orvia_backend.context import ContextService
from orvia_backend.retrieval import RetrievalService
from orvia_backend.retrieval.runtime import LocalEmbedder
from orvia_backend.retrieval.service import _decode
from orvia_backend.retrieval.model import SIGNATURE
from orvia_backend.storage import Store


# 固定合成主题，不使用用户正文；查询刻意包含同义词与中英文混合。
DOCUMENTS = [
    ('transport','城市公共交通方案提出增加公交车班次，降低居民开车通勤的成本。'),
    ('energy','太阳能电池将光能转换为电能，阴天会降低光伏发电效率。'),
    ('storage','SQLite数据库保留任务事实，Redis缓存失效不改变审批结果。'),
    ('privacy','文件正文只在本机建立索引，向云端发送前需预览并确认。'),
    ('backup','每天复制研究数据到另一块硬盘，防止设备损坏造成资料丢失。'),
    ('plants','植物根系吸收水分，叶片通过光合作用合成有机物。'),
    ('coffee','咖啡店提供烘焙豆和热饮，营业时间从上午九点到下午六点。'),
    ('travel','旅馆提供双床客房，预订取消规则应在付款前阅读。'),
    ('memory','对话记忆保存来源定位，删除会话后清除对应派生索引。'),
    ('approval','执行文件移动计划之前，用户逐项核对目录与目标文件名。'),
    ('network','服务端使用HTTPS传输请求，客户端校验目标站点并处理超时。'),
    ('signal','低通滤波器抑制高频噪声，保留传感器信号的慢速变化。'),
    ('training','机器学习模型通过训练集拟合参数，并使用独立测试集评估。'),
    ('health','合成设备说明建议定时维护风扇，保证空气流通和散热。'),
    ('meeting','小组会议讨论项目日程，每周三下午在会议室汇报进展。'),
    ('budget','项目支出包括设备采购和软件许可，预算需要逐笔记录。'),
]
QUERIES = [
    ('怎样减少汽车上班的花费？','transport'),
    ('为什么 cloudy weather 会影响 photovoltaic power？','energy'),
    ('缓存断开会丢失真实任务状态吗？','storage'),
    ('资料内容在上传之前有什么步骤？','privacy'),
    ('硬盘坏了怎样避免研究文件消失？','backup'),
    ('什么 filter 可以去掉快速噪声？','signal'),
    ('删除聊天后还留着派生记忆吗？','memory'),
    ('评价 machine learning 需要什么独立数据？','training'),
]


async def main():
    path=os.environ.get('ORVIA_EMBEDDING_MODEL_PATH')
    if not path:
        raise SystemExit('须显式提供已批准且核验的 ORVIA_EMBEDDING_MODEL_PATH；本脚本不下载模型。')
    root=Path('artifacts/test-results/V4-004').resolve()
    work=root/('real-'+str(time.time_ns()));work.mkdir(parents=True)
    store=Store(work/'facts.sqlite');await store.open()
    runtime=LocalEmbedder(work/'profile');service=RetrievalService(store,runtime);await service.open()
    started=time.monotonic()
    report={'mock':False,'cloud_model_calls':0,'dataset':'orvia-v4-004-synthetic-v1',
            'documents':len(DOCUMENTS),'queries':len(QUERIES),'rows':[],
            'environment':{'os':platform.platform(),'cpu':platform.processor(),'python':platform.python_version(),
                           'ram_bytes':psutil.virtual_memory().total,
                           'libraries':{name:importlib.metadata.version(name) for name in ('torch','transformers','safetensors')}},
            'measurement':'单次固定8查询；同一FTS5 OR基线；vector含独立query嵌入/SQLite/余弦，hybrid含FTS/RRF；RSS为工作器抽样观测；无统计置信或通用收益声明'}
    try:
        ready=await runtime.prepare(path)
        assert ready['ready'],ready
        report['prepare_seconds']=time.monotonic()-started
        context=ContextService(store)
        for source,text in DOCUMENTS:await context.index_text('synthetic-benchmark',source,text)
        await context.index_text('synthetic-benchmark','duplicate-transport',DOCUMENTS[0][1])
        async with store._lock:await store._db().execute('PRAGMA wal_checkpoint(TRUNCATE)')
        report['sqlite_before_vectors_bytes']=store.path.stat().st_size
        start=time.monotonic();built=await service.rebuild('synthetic-benchmark')
        assert built['status']=='completed',built
        assert built['indexed_chunks']==17 and built['unique_texts']==16
        report['index_seconds']=time.monotonic()-start
        for query,expected in QUERIES:
            class KeywordOnly:
                signature=SIGNATURE
                def status(self):return {'ready':False,'reason':'BENCHMARK_KEYWORD_ONLY','signature':SIGNATURE}
            # 使用同一FTS5 OR通道作基线，避免把AND→OR差异冒充向量收益。
            service.embedder=KeywordOnly()
            start=time.monotonic();keyword=await service.search('synthetic-benchmark',query,5);kt=time.monotonic()-start
            service.embedder=runtime
            start=time.monotonic();hybrid=await service.search('synthetic-benchmark',query,5);ht=time.monotonic()-start
            assert hybrid['status']=='hybrid',hybrid['reason']
            start=time.monotonic();q=(await runtime.embed([query],query=True))[0]
            async with store._lock:
                async with store._db().execute('SELECT d.source,v.vector FROM retrieval_vectors v JOIN context_documents d ON d.id=v.document_id WHERE v.mission_id=?',['synthetic-benchmark']) as cursor:
                    rows=await cursor.fetchall()
            ranked=sorted(((source,math.fsum(a*b for a,b in zip(q,_decode(blob),strict=True))) for source,blob in rows),key=lambda x:-x[1])
            seen=set();vector=[]
            for source,_ in ranked:
                canonical='transport' if source=='duplicate-transport' else source
                if canonical not in seen:vector.append(canonical);seen.add(canonical)
            def sources(hits):
                return ['transport' if h['source']=='duplicate-transport' else h['source'] for h in hits]
            report['rows'].append({'query':query,'expected':expected,'keyword':sources(keyword['evidence']),
                'vector':vector[:5],'hybrid':sources(hybrid['evidence']),
                'seconds':{'keyword':kt,'vector':time.monotonic()-start,'hybrid':ht}})
        metrics={}
        for channel in ('keyword','vector','hybrid'):
            ranks=[row[channel].index(row['expected'])+1 if row['expected'] in row[channel] else None for row in report['rows']]
            metrics[channel]={'Recall@5':sum(r is not None for r in ranks)/len(ranks),
                              'MRR@5':sum(1/r if r else 0 for r in ranks)/len(ranks),
                              'mean_seconds':sum(row['seconds'][channel] for row in report['rows'])/len(ranks)}
        report['metrics']=metrics
        report['semantic_checks']={row['expected']:row['expected'] in row['vector']
                                   for row in report['rows'] if row['expected'] in ('transport','energy','signal')}
        # 在运行前固定中文同义transport和中英混合energy/signal三个条件，禁止事后挑选成功项。
        assert len(report['semantic_checks'])==3 and all(report['semantic_checks'].values()),'预登记中文同义/混合语言召回条件未满足'
        assert not (await service.search('other-mission',QUERIES[0][0]))['evidence']
        await context.clear('synthetic-benchmark','transport')
        after=await service.search('synthetic-benchmark',QUERIES[0][0])
        assert all(h['source']!='transport' for h in after['evidence'])
        await runtime.close();await store.close();await store.open();await service.open()
        assert (await service.status('synthetic-benchmark'))['indexed_chunks']==16
        assert (await runtime.restore())['ready']
        restarted=await service.search('synthetic-benchmark',QUERIES[0][0]);assert restarted['status']=='hybrid'
        report['runtime']=runtime.status()
        report['checks']={'dedup':True,'delete':True,'scope':True,'restart':True,'finite_normalized_1024':True}
        async with store._lock:await store._db().execute('PRAGMA wal_checkpoint(TRUNCATE)')
        report['sqlite_bytes']=store.path.stat().st_size
        async with store._lock:
            async with store._db().execute('SELECT sum(length(vector)) FROM retrieval_vectors') as cursor:
                report['vector_payload_bytes']=(await cursor.fetchone())[0] or 0
        report['passed']=True
    finally:
        report['total_seconds']=time.monotonic()-started
        report['runtime']=runtime.status()
        await runtime.close();await store.close()
        (work/'benchmark.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'report':str(work/'benchmark.json'),'passed':report.get('passed',False)},ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())
