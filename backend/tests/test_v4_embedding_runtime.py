"""V4-004工件校验、离线工作器预算与固定下载取消；不下载真实权重。"""
import asyncio
import hashlib
from pathlib import Path

import pytest

from orvia_backend.retrieval import runtime
from orvia_backend.retrieval.model import manifest


def test_official_manifest_fixed():
    value = manifest()
    assert value['bytes'] == 1207469240
    assert len(value['files']) == 6
    assert value['revision'] == '97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3'
    assert not any(item['name'].endswith('.py') for item in value['files'])


def test_streaming_checksum_and_extra_code_rejected(tmp_path, monkeypatch):
    data=b'fixed-synthetic'
    monkeypatch.setattr(runtime,'FILES',{'sample':(len(data),'sha256',hashlib.sha256(data).hexdigest())})
    (tmp_path/'sample').write_bytes(data)
    runtime.verify(tmp_path)
    (tmp_path/'sample').write_bytes(b'wrong-synthetic')
    with pytest.raises(runtime.EmbeddingError):runtime.verify(tmp_path)
    (tmp_path/'sample').write_bytes(data)
    (tmp_path/'plugin.py').write_text('untrusted')
    with pytest.raises(runtime.EmbeddingError):runtime.verify(tmp_path)


def test_git_blob_checksum(tmp_path,monkeypatch):
    data=b'config'
    digest=hashlib.sha1(b'blob 6\0'+data).hexdigest()
    monkeypatch.setattr(runtime,'FILES',{'config':(6,'git-sha1',digest)})
    (tmp_path/'config').write_bytes(data)
    runtime.verify(tmp_path)


def test_missing_prepare_restore_and_input_no_network(tmp_path,monkeypatch):
    async def run():
        embedder=runtime.LocalEmbedder(tmp_path)
        assert embedder.status()['reason']=='MODEL_MISSING'
        def forbidden(*args,**kwargs):raise AssertionError('must not download')
        monkeypatch.setattr(runtime.httpx,'AsyncClient',forbidden)
        assert not (await embedder.prepare(str(tmp_path/'absent')))['ready']
        assert not (await embedder.restore())['ready']
        with pytest.raises(runtime.EmbeddingError):await embedder.embed(['test'])
        with pytest.raises(runtime.EmbeddingError):await embedder.embed(['a'*601])
        await embedder.close()
    asyncio.run(run())


def test_memory_and_cancel_kill_worker(tmp_path,monkeypatch):
    class Output:
        async def readline(self):await asyncio.sleep(100)
    class Process:
        returncode=None
        pid=123
        stdout=Output()
        stdin=None
        killed=False
        def kill(self):self.killed=True;self.returncode=-1
        async def wait(self):return self.returncode
    class Ps:
        def children(self,recursive=True):return []
        def memory_info(self):return type('Info',(),{'rss':7*1024**3})()
    async def run():
        embedder=runtime.LocalEmbedder(tmp_path);process=Process();embedder.process=process
        monkeypatch.setattr(runtime.psutil,'Process',lambda pid:Ps())
        with pytest.raises(runtime.EmbeddingError,match='MODEL_MEMORY_LIMIT'):await embedder._read(2)
        assert process.killed and embedder.process is None
        process=Process();embedder.process=process
        class Small:
            def children(self,recursive=True):return []
            def memory_info(self):return type('Info',(),{'rss':10})()
        monkeypatch.setattr(runtime.psutil,'Process',lambda pid:Small())
        task=asyncio.create_task(embedder._read(20));await asyncio.sleep(.01);task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert process.killed and embedder.process is None
    asyncio.run(run())


def test_explicit_download_https_hash_and_failure_cleanup(tmp_path,monkeypatch):
    import httpx
    data=b'fixed-test-artifact'
    monkeypatch.setattr(runtime,'FILES',{'sample':(len(data),'sha256',hashlib.sha256(data).hexdigest())})
    urls=[]
    def respond(request):
        urls.append(str(request.url))
        return httpx.Response(200,content=data,request=request)
    original=httpx.AsyncClient
    monkeypatch.setattr(runtime.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    async def run():
        embedder=runtime.LocalEmbedder(tmp_path)
        async def prepared(path=None):
            runtime.verify(embedder.directory)
            return {'ready':True}
        monkeypatch.setattr(embedder,'prepare',prepared)
        assert (await embedder.download())['ready']
        assert (embedder.directory/'sample').read_bytes()==data
        assert len(urls)==1 and urls[0].startswith('https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/resolve/'+runtime.REVISION)
        assert not list(embedder.directory.parent.glob('download-*'))
        await embedder.download();assert len(urls)==1,'有效已有工件不重新下载'
        bad=runtime.LocalEmbedder(tmp_path/'bad')
        class ExistingWorker:
            returncode=None
            killed=False
            pid=99999999
            stdin=None
            def kill(self):self.killed=True;self.returncode=-1
            async def wait(self):return self.returncode
        previous=ExistingWorker();bad.process=previous
        def downgrade(request):
            return httpx.Response(302,headers={'location':'http://unapproved.test/sample'},request=request)
        monkeypatch.setattr(runtime.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(downgrade),**kw))
        assert (await bad.download())['reason']=='MODEL_DOWNLOAD_FAILED'
        assert previous.killed and not bad.status()['ready']
        assert not bad.directory.exists() and not list(bad.directory.parent.glob('download-*'))
    asyncio.run(run())


def test_prepare_has_total_deadline_not_sum_of_phases(tmp_path,monkeypatch):
    async def run():
        embedder=runtime.LocalEmbedder(tmp_path)
        monkeypatch.setattr(runtime,'PREPARE_SECONDS',.01)
        cancelled=[]
        async def pending(path):
            try:await asyncio.sleep(100)
            finally:cancelled.append(True)
        monkeypatch.setattr(embedder,'_prepare',pending)
        result=await embedder.prepare('synthetic-not-opened')
        assert result['ready'] is False and result['reason']=='MODEL_TIMEOUT'
        assert cancelled==[True]
    asyncio.run(run())


def test_memory_budget_includes_launcher_child_and_reaps_it(tmp_path,monkeypatch):
    class Leaf:
        pid=789
        killed=False
        def memory_info(self):return type('Info',(),{'rss':7*1024**3})()
        def kill(self):self.killed=True
    leaf=Leaf()
    class Launcher:
        def children(self,recursive=True):return [leaf]
        def memory_info(self):return type('Info',(),{'rss':4*1024**2})()
    class Output:
        async def readline(self):await asyncio.sleep(100)
    class Process:
        pid=123
        stdout=Output()
        stdin=None
        returncode=None
        def kill(self):self.returncode=-1
        async def wait(self):return self.returncode
    async def run():
        embedder=runtime.LocalEmbedder(tmp_path);embedder.process=Process()
        monkeypatch.setattr(runtime.psutil,'Process',lambda pid:Launcher())
        with pytest.raises(runtime.EmbeddingError,match='MODEL_MEMORY_LIMIT'):await embedder._read(2)
        assert leaf.killed and embedder.process is None
        assert embedder.peak_bytes>7*1024**3
    asyncio.run(run())
