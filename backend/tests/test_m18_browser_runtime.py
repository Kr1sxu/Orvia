"""私有Chromium资源搬运的合成单测；不把假PE文件称为浏览器执行能力。"""
import hashlib
import os

import pytest

from orvia_backend.automation.browser_runtime import prepare_chromium
from orvia_backend.computer.paths import ToolError


def source(tmp_path):
    directory = tmp_path / "synthetic-sdk"
    directory.mkdir()
    (directory/"chrome.exe").write_bytes(b"synthetic executable bytes - never executed")
    (directory/"chrome_elf.dll").write_bytes(b"synthetic assembly bytes")
    (directory/"resources.pak").write_bytes(b"synthetic resources")
    (directory/"153.0.8010.12.manifest").write_text("<assembly xmlns='urn:schemas-microsoft-com:asm.v1' manifestVersion='1.0'><assemblyIdentity name='153.0.8010.12' version='153.0.8010.12' type='win32'/><file name='chrome_elf.dll'/></assembly>",encoding="utf-8")
    return directory/"chrome.exe"


def test_private_runtime_keeps_original_bytes_and_verifies_reuse(tmp_path):
    executable = source(tmp_path)
    original = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in executable.parent.iterdir()}
    private = prepare_chromium(executable,tmp_path/"private")
    for name, checksum in original.items():
        target = private if name == "chrome.exe" else private.parent/"153.0.8010.12"/name
        assert hashlib.sha256(target.read_bytes()).hexdigest() == checksum
        assert hashlib.sha256((executable.parent/name).read_bytes()).hexdigest() == checksum
    assert not (private.parent/"chrome_elf.dll").exists()  # 不混合根/版本DLL路径。
    assert (private.parent/"153.0.8010.12/chrome_elf.dll").read_bytes() == (executable.parent/"chrome_elf.dll").read_bytes()
    assert prepare_chromium(executable,tmp_path/"private") == private
    resource = private.parent/"153.0.8010.12/resources.pak"
    resource.write_bytes(b"synthetic tamper")
    with pytest.raises(ToolError,match="无法核验"):
        prepare_chromium(executable,tmp_path/"private")
    assert resource.read_bytes() == b"synthetic tamper"  # 不自动覆盖修复。


def test_runtime_rejects_manifest_path_and_link_or_extra_file(tmp_path):
    executable = source(tmp_path)
    manifest = executable.parent/"153.0.8010.12.manifest"
    valid = manifest.read_text()
    manifest.write_text(valid.replace("chrome_elf.dll","../unapproved.dll"))
    with pytest.raises(ToolError): prepare_chromium(executable,tmp_path/"private")
    assert not (tmp_path/"private").exists()
    manifest.write_text(valid)
    os.link(executable.parent/"resources.pak",executable.parent/"hardlink.pak")
    with pytest.raises(ToolError): prepare_chromium(executable,tmp_path/"private")


def test_source_change_rejects_cached_private_runtime(tmp_path):
    executable = source(tmp_path)
    prepare_chromium(executable,tmp_path/"private")
    (executable.parent/"resources.pak").write_bytes(b"synthetic source replacement")
    with pytest.raises(ToolError): prepare_chromium(executable,tmp_path/"private")


def test_runtime_rejects_xml_entities_and_linked_metadata(tmp_path):
    executable = source(tmp_path)
    manifest = executable.parent/"153.0.8010.12.manifest"
    valid = manifest.read_bytes()
    manifest.write_bytes(b'<!DOCTYPE assembly [<!ENTITY x "synthetic">]>' + valid)
    with pytest.raises(ToolError): prepare_chromium(executable,tmp_path/"private")
    assert not (tmp_path/"private").exists()
    manifest.write_bytes(valid)
    private = prepare_chromium(executable,tmp_path/"private")
    record = private.parent/"orvia-chromium-runtime.json"
    os.link(record,tmp_path/"linked-record.json")
    with pytest.raises(ToolError): prepare_chromium(executable,tmp_path/"private")
