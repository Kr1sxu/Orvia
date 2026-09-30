"""Windows配套Chromium的私有原样副本；不修改SDK、系统程序集或二进制manifest。"""

import hashlib
import ctypes
from ctypes import wintypes as w
import json
import os
import re
import stat
import threading
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree
from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException

from ..computer.paths import ToolError, _reparse

_LOCK = threading.Lock()
_RECORD = "orvia-chromium-runtime.json"
_MAX_FILES = 1024
_MAX_BYTES = 1024 * 1024 * 1024


def _error():
    return ToolError("BROWSER_RUNTIME_UNAVAILABLE", "配套Chromium私有运行时无法核验；未修改原安装或退回其他浏览器")


def _plain(path):
    for item in [path, *path.parents]:
        if item.exists() and _reparse(item):
            raise _error()


def _tree(root):
    """运行时来自固定SDK路径，仍有界检查链接、文件身份和完整字节，拒绝额外文件。"""
    _plain(root)
    pending, files, visited, total = [root], {}, 0, 0
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                visited += 1
                if visited > 2048:
                    raise _error()
                path = Path(entry.path)
                _plain(path)
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                    continue
                relative = path.relative_to(root).as_posix()
                if relative == _RECORD:
                    continue
                with path.open("rb") as stream:
                    before = os.fstat(stream.fileno())
                    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > _MAX_BYTES:
                        raise _error()
                    checksum = hashlib.sha256()
                    read = 0
                    while chunk := stream.read(1024 * 1024):
                        read += len(chunk)
                        if read > before.st_size:
                            raise _error()
                        checksum.update(chunk)
                    after = os.fstat(stream.fileno())
                    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or read != before.st_size:
                        raise _error()
                total += read
                files[relative] = checksum.hexdigest()
                if len(files) > _MAX_FILES or total > _MAX_BYTES:
                    raise _error()
    return files


def _copy(source, target, expected):
    _plain(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    checksum = hashlib.sha256()
    with source.open("rb") as reader, target.open("xb") as writer:
        before = os.fstat(reader.fileno())
        if before.st_nlink != 1 or not stat.S_ISREG(before.st_mode):
            raise _error()
        read = 0
        while chunk := reader.read(1024 * 1024):
            read += len(chunk)
            if read > min(before.st_size, _MAX_BYTES):
                raise _error()
            checksum.update(chunk)
            writer.write(chunk)
        writer.flush()
        os.fsync(writer.fileno())
        after = os.fstat(reader.fileno())
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or read != before.st_size or checksum.hexdigest() != expected:
            raise _error()


def _sandbox_read_access(root):
    """仅自有公开程序副本给AppContainer/LPAC只读执行，不给profile/任务或原cache授权。

    Chromium的受限子进程必须能读程序资源；普通用户目录的默认DACL未必满足。
    当前用户仍为owner，所有组只获得GRGX，既不提权也不禁用Chromium sandbox。
    """
    if os.name != "nt":
        return
    from .windows_isolation import _Native
    native = _Native()
    user = native.user_sid()
    _plain(root)
    if "-owner-1-" not in native.acl_diagnostics(root,user):
        raise _error()
    descriptor = w.LPVOID()
    sddl = f"D:P(A;OICI;FA;;;{user})(A;OICI;FA;;;SY)(A;OICI;GRGX;;;S-1-15-2-1)(A;OICI;GRGX;;;S-1-15-2-2)"
    if not native.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,ctypes.byref(descriptor),None):
        raise _error()
    try:
        paths = [root]
        for path in root.rglob("*"):
            if len(paths) >= 2049:
                raise _error()
            paths.append(path)
        for path in paths:
            _plain(path)
            if not native.a.SetFileSecurityW(str(path),0x80000004,descriptor):
                raise _error()
    finally:
        native.k.LocalFree(descriptor)


def prepare_chromium(executable, runtime_root):
    """保留所有原字节/签名，补齐Windows私有版本程序集目录，再核验完整副本。

    本机SDK的flat CfT目录使Windows找不到版本程序集并返回14001；在应用私有副本
    保留根chrome.exe，其余原样放入同名版本目录，满足SxS与沙箱模块路径规则。
    不禁用SxS/Chromium sandbox、不修改原cache、不联网，也不接收用户解释器路径。
    """
    with _LOCK:
        try:
            source = Path(executable)
            if source.name.casefold() != "chrome.exe" or runtime_root is None:
                raise _error()
            _plain(source)
            original = _tree(source.parent)
            names = [name for name in original if re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\.manifest", name)]
            if len(names) != 1 or "chrome.exe" not in original or "chrome_elf.dll" not in original:
                raise _error()
            manifest_name, = names
            manifest_path = source.parent / manifest_name
            if manifest_path.stat().st_size > 16 * 1024:
                raise _error()
            assembly = fromstring(manifest_path.read_bytes())
            identity = assembly.find("{urn:schemas-microsoft-com:asm.v1}assemblyIdentity")
            version = Path(manifest_name).stem
            members = assembly.findall("{urn:schemas-microsoft-com:asm.v1}file")
            if identity is None or identity.get("name") != version or identity.get("version") != version or identity.get("type") != "win32" or [member.get("name") for member in members] != ["chrome_elf.dll"]:
                raise _error()
            runtime_root = Path(runtime_root)
            _plain(runtime_root)
            target = runtime_root / ("chromium-" + version)
            # chrome.dll与静态绑定的chrome_elf必须同属一个版本目录；保留两份ELF
            # 会使sandbox加载不同模块路径。只改变安装布局，不改任何文件字节。
            mapping = {relative: relative if relative == "chrome.exe" else f"{version}/{relative}" for relative in original}
            expected = {mapping[relative]: checksum for relative, checksum in original.items()}
            record = {"version": version, "layout": "private-version-directory", "files": expected}
            if target.exists():
                _plain(target / _RECORD)
                record_stat = (target / _RECORD).stat()
                if not stat.S_ISREG(record_stat.st_mode) or record_stat.st_nlink != 1 or record_stat.st_size > 256 * 1024 or json.loads((target / _RECORD).read_text(encoding="utf-8")) != record or _tree(target) != expected:
                    raise _error()
                _sandbox_read_access(target)
                return target / source.name
            runtime_root.mkdir(parents=True, exist_ok=True)
            temporary = runtime_root / ("prepare-" + uuid4().hex)
            temporary.mkdir()
            for relative, checksum in original.items():
                _copy(source.parent / relative, temporary / mapping[relative], checksum)
            if _tree(temporary) != expected:
                raise _error()
            (temporary / _RECORD).write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
            _sandbox_read_access(temporary)
            temporary.rename(target)
            return target / source.name
        except (OSError, ValueError, ElementTree.ParseError, DefusedXmlException):
            raise _error() from None
