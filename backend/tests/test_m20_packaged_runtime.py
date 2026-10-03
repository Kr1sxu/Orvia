"""M20安装资源分支：合成字节验证固定来源/完整hash与拒绝边界，不启动解释器。"""
import json
import os

import pytest

from orvia_backend.automation import windows_isolation as isolation


pytestmark = pytest.mark.skipif(os.name != 'nt', reason='固定Windows资源路径验收')


def packaged(monkeypatch, tmp_path):
    resources = tmp_path / 'candidate/resources'
    host = resources / 'backend/orvia-backend.exe'
    host.parent.mkdir(parents=True)
    host.write_bytes(b'synthetic frozen service, not an interpreter')
    source = resources / 'script-runtime/python312'
    (source / 'Lib/encodings').mkdir(parents=True)
    for name, data in {'python.exe':b'synthetic interpreter', 'python312.dll':b'synthetic DLL',
                       'python312._pth':b'.\nLib\nDLLs\n', 'Lib/encodings/__init__.py':b'# synthetic',
                       'LICENSE.txt':b'synthetic license'}.items():
        (source / name).write_bytes(data)
    record = {'version':'3.12','transform':'manifestless-console','files':isolation._runtime_manifest(source)}
    (source / 'orvia-runtime.json').write_text(json.dumps(record,sort_keys=True),encoding='utf-8')
    monkeypatch.setattr(isolation.sys,'frozen',True,raising=False)
    monkeypatch.setattr(isolation.sys,'executable',str(host))
    return source, tmp_path / 'application-private/runtime'


def test_frozen_copy_uses_fixed_prepared_runtime_without_environment_override(monkeypatch,tmp_path):
    source, private = packaged(monkeypatch,tmp_path)
    monkeypatch.setenv('PYTHONHOME',str(tmp_path/'untrusted'))
    monkeypatch.setenv('PATH',str(tmp_path/'untrusted'))
    copied = isolation.prepare_runtime(private)
    assert copied == private/'python312/python.exe'
    assert copied.read_bytes() == (source/'python.exe').read_bytes()
    assert isolation._runtime_manifest(copied.parent) == isolation._runtime_manifest(source)
    assert isolation.prepare_runtime(private) == copied
    assert not (source/'Lib/site-packages').exists()


def test_frozen_refuses_caller_interpreter_and_arbitrary_host_location(monkeypatch,tmp_path):
    source, private = packaged(monkeypatch,tmp_path)
    with pytest.raises(isolation.IsolationError,match='不接受解释器覆盖'):
        isolation.prepare_runtime(private,source/'python.exe')
    monkeypatch.setattr(isolation.sys,'executable',str(source/'python.exe'))
    with pytest.raises(isolation.IsolationError,match='固定安装资源'):
        isolation.prepare_runtime(private)
    assert not private.exists()


@pytest.mark.parametrize('change',['bytes','extra','manifest'])
def test_frozen_refuses_changed_prepared_resource(monkeypatch,tmp_path,change):
    source, private = packaged(monkeypatch,tmp_path)
    if change == 'bytes':
        (source/'python312.dll').write_bytes(b'changed')
    elif change == 'extra':
        (source/'unexpected.py').write_text('malicious synthetic',encoding='utf-8')
    else:
        (source/'orvia-runtime.json').write_bytes(b'x'*(2*1024*1024+1))
    with pytest.raises(isolation.IsolationError):
        isolation.prepare_runtime(private)
    assert not private.exists()


def test_frozen_does_not_repair_changed_private_copy(monkeypatch,tmp_path):
    _, private = packaged(monkeypatch,tmp_path)
    copied = isolation.prepare_runtime(private)
    copied.write_bytes(b'user-modified synthetic')
    with pytest.raises(isolation.IsolationError):
        isolation.prepare_runtime(private)
    assert copied.read_bytes() == b'user-modified synthetic'


def test_frozen_refuses_private_runtime_from_another_release(monkeypatch,tmp_path):
    source, private = packaged(monkeypatch,tmp_path)
    isolation.prepare_runtime(private)
    (source/'python.exe').write_bytes(b'new synthetic interpreter')
    record={'version':'3.12','transform':'manifestless-console','files':isolation._runtime_manifest(source)}
    (source/'orvia-runtime.json').write_text(json.dumps(record,sort_keys=True),encoding='utf-8')
    with pytest.raises(isolation.IsolationError,match='当前安装资源版本'):
        isolation.prepare_runtime(private)
    assert (private/'python312/python.exe').read_bytes() == b'synthetic interpreter'


def test_runtime_manifest_refuses_hard_links(monkeypatch,tmp_path):
    source, private = packaged(monkeypatch,tmp_path)
    os.link(source/'python.exe',source/'second.exe')
    with pytest.raises(isolation.IsolationError):
        isolation.prepare_runtime(private)
    assert not private.exists()


def test_frozen_refuses_search_path_that_enables_site(monkeypatch,tmp_path):
    source, private = packaged(monkeypatch,tmp_path)
    (source/'python312._pth').write_text('.\nLib\nDLLs\nimport site\n',encoding='utf-8')
    record={'version':'3.12','transform':'manifestless-console','files':isolation._runtime_manifest(source)}
    (source/'orvia-runtime.json').write_text(json.dumps(record,sort_keys=True),encoding='utf-8')
    with pytest.raises(isolation.IsolationError):
        isolation.prepare_runtime(private)
    assert not private.exists()
