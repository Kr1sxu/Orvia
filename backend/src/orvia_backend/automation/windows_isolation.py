"""M18 Windows LPAC 隔离：操作系统令牌约束权限，Job 负责资源和进程树回收。

此适配器从不退回普通 subprocess。运行时只包含固定 CPython 的私有副本；
环境和继承句柄使用允许清单，后端源码、数据库、凭据都不授给脚本。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
from uuid import uuid4
import xml.etree.ElementTree as ET

from ..computer.paths import ToolError


class IsolationError(ToolError):
    """隔离前提失败必须关闭能力，不能由调用方切换到无隔离执行。"""


_RUN_LOCK = threading.Lock()
_OUTPUT_LIMIT = 16 * 1024
_MEMORY_LIMIT = 512 * 1024 * 1024
_MANIFEST = "orvia-runtime.json"


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", w.DWORD), ("Data2", w.WORD), ("Data3", w.WORD), ("Data4", w.BYTE * 8)]


def _local_appdata() -> str:
    """从当前用户 Known Folder 获取固定系统目录，不要求后端继承用户环境。

    Electron 后端环境有意不带 LOCALAPPDATA；用空字符串创建 LPAC 会导致
    CreateProcess 返回 203。此调用仅查当前用户目录位置，不读取目录资料。
    """
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    ole = ctypes.WinDLL("ole32", use_last_error=True)
    shell.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(_GUID), w.DWORD, w.HANDLE, ctypes.POINTER(w.LPWSTR)]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes, ole.CoTaskMemFree.restype = [w.LPVOID], None
    folder_id = _GUID(0xF1B32785, 0x6FBA, 0x4FCF, (w.BYTE * 8)(0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91))
    pointer = w.LPWSTR()
    if shell.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(pointer)) < 0:
        raise IsolationError("M18_ISOLATION_UNAVAILABLE", "无法定位当前用户 LPAC 私有目录")
    try:
        return str(_ordinary(Path(pointer.value)))
    finally:
        ole.CoTaskMemFree(pointer)


def _ordinary(path: Path, *, exists: bool = True) -> Path:
    raw = Path(path)
    if not raw.is_absolute() or raw.anchor.startswith("\\\\"):
        raise IsolationError("M18_ISOLATION_INVALID", "隔离路径必须是本地绝对路径")
    for part in (*reversed(raw.parents), raw):
        if not part.exists():
            if exists:
                raise IsolationError("M18_ISOLATION_INVALID", "隔离路径不存在")
            continue
        info = part.lstat()
        if part.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise IsolationError("M18_ISOLATION_INVALID", "隔离路径不能包含重解析点")
    return raw


def _digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _runtime_manifest(root: Path) -> dict[str, str]:
    files = {}
    for path in root.rglob("*"):
        _ordinary(path)
        if path.is_file() and path != root / _MANIFEST:
            if path.stat().st_nlink != 1:
                raise IsolationError("M18_RUNTIME_UNAVAILABLE", "运行时不能包含硬链接")
            files[path.relative_to(root).as_posix()] = _digest(path)
        if len(files) > 5000:
            raise IsolationError("M18_RUNTIME_UNAVAILABLE", "运行时副本超过预算")
    return files


def _disable_sxs_manifest(path: Path, resource_id: int) -> None:
    """私有控制台副本移除固定 CPython 的 SxS manifest 资源。

    CPython 的共享 manifest 带有此 GUI 依赖；LPAC 零能力启动时 SxS 初始化
    被系统拒绝。最小删除 Common-Controls 依赖仍会触发 SxS，因此删除整个
    固定 manifest；非提升由启动前 LPAC 令牌复核保证，不接收用户资源/代码；
    不改原安装、不改系统 ACL/注册表。私有副本不再继承原二进制签名，后续
    以完整哈希清单核验变换后的副本，而不声称其签名与原安装相同。
    """
    library = ctypes.WinDLL("kernel32", use_last_error=True)
    definitions = {
        "LoadLibraryExW": ([w.LPCWSTR, w.HANDLE, w.DWORD], w.HANDLE),
        "FreeLibrary": ([w.HANDLE], w.BOOL),
        "FindResourceExW": ([w.HANDLE, w.LPVOID, w.LPVOID, w.WORD], w.HANDLE),
        "SizeofResource": ([w.HANDLE, w.HANDLE], w.DWORD),
        "LoadResource": ([w.HANDLE, w.HANDLE], w.HANDLE),
        "LockResource": ([w.HANDLE], w.LPVOID),
        "BeginUpdateResourceW": ([w.LPCWSTR, w.BOOL], w.HANDLE),
        "UpdateResourceW": ([w.HANDLE, w.LPVOID, w.LPVOID, w.WORD, w.LPVOID, w.DWORD], w.BOOL),
        "EndUpdateResourceW": ([w.HANDLE, w.BOOL], w.BOOL),
    }
    for name, (args, result) in definitions.items():
        fn = getattr(library, name)
        fn.argtypes, fn.restype = args, result
    callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HANDLE, w.LPVOID, w.LPVOID, w.WORD, ctypes.c_ssize_t)
    library.EnumResourceLanguagesW.argtypes = [w.HANDLE, w.LPVOID, w.LPVOID, callback_type, ctypes.c_ssize_t]
    library.EnumResourceLanguagesW.restype = w.BOOL
    module = library.LoadLibraryExW(str(path), None, 0x2 | 0x20)
    if not module:
        raise IsolationError("M18_RUNTIME_UNAVAILABLE", "无法读取私有 CPython 固定资源")
    changed = []
    try:
        languages = []
        callback = callback_type(lambda module, kind, name, language, data: languages.append(language) is None)
        if not library.EnumResourceLanguagesW(module, 24, resource_id, callback, 0):
            if ctypes.get_last_error() in (1812, 1813, 1814, 1815):
                return
            raise IsolationError("M18_RUNTIME_UNAVAILABLE", "无法枚举私有 CPython 固定资源")
        for language in languages:
            resource = library.FindResourceExW(module, 24, resource_id, language)
            length = library.SizeofResource(module, resource)
            pointer = library.LockResource(library.LoadResource(module, resource))
            if not pointer or not 0 < length <= 64 * 1024:
                raise IsolationError("M18_RUNTIME_UNAVAILABLE", "CPython manifest 资源无效")
            root = ET.fromstring(ctypes.string_at(pointer, length))
            if root.tag.rsplit("}", 1)[-1] != "assembly":
                raise IsolationError("M18_RUNTIME_UNAVAILABLE", "CPython 固定 manifest 类型不符")
            changed.append(language)
    finally:
        library.FreeLibrary(module)
    if not changed:
        return
    update = library.BeginUpdateResourceW(str(path), False)
    if not update:
        raise IsolationError("M18_RUNTIME_UNAVAILABLE", "无法准备私有 CPython 资源变换")
    committed = False
    try:
        for language in changed:
            if not library.UpdateResourceW(update, 24, resource_id, language, None, 0):
                raise IsolationError("M18_RUNTIME_UNAVAILABLE", "私有 CPython 资源变换失败")
        if not library.EndUpdateResourceW(update, False):
            raise IsolationError("M18_RUNTIME_UNAVAILABLE", "私有 CPython 资源保存失败")
        committed = True
    finally:
        if not committed:
            library.EndUpdateResourceW(update, True)


def _verify_runtime(executable: Path) -> None:
    root = _ordinary(executable).parent
    try:
        manifest = json.loads((root / _MANIFEST).read_text(encoding="utf-8"))
        if (not isinstance(manifest, dict) or manifest.get("version") != "3.12" or manifest.get("transform") != "manifestless-console"
                or manifest.get("files") != _runtime_manifest(root)):
            raise ValueError("manifest")
        if executable.name != "python.exe" or not (root / "python312.dll").is_file():
            raise ValueError("runtime")
    except (OSError, ValueError, TypeError) as exc:
        raise IsolationError("M18_RUNTIME_UNAVAILABLE", "私有 Python 副本缺失或变化，请重新准备") from exc


def _file_budget(root: Path, *, count: int) -> bool:
    """有界采样磁盘产物；它是预算监测，不宣称操作系统磁盘配额。"""
    entries, total, visited = 0, 0, 0
    try:
        root_info = root.lstat()
        if (not stat.S_ISDIR(root_info.st_mode) or root.is_symlink()
                or getattr(root_info, "st_file_attributes", 0) & 0x400):
            return False
        pending = [root]
        while pending:
            with os.scandir(pending.pop()) as iterator:
                for entry in iterator:
                    visited += 1
                    if visited > 512:
                        return False
                    # Windows DirEntry 缓存的 nlink/ino 可能为0；硬链接核验须用真实 lstat。
                    info = Path(entry.path).lstat()
                    if entry.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                        return False
                    if stat.S_ISREG(info.st_mode):
                        if info.st_nlink != 1:
                            return False
                        entries += 1
                        total += info.st_size
                        if entries > count or info.st_size > 2 * 1024 * 1024 or total > 16 * 1024 * 1024:
                            return False
                    elif stat.S_ISDIR(info.st_mode):
                        pending.append(Path(entry.path))
                    else:
                        return False
    except OSError:
        return False
    return True


def prepare_runtime(private_root: Path, source_executable: Path | None = None) -> Path:
    """仅复制当前固定 CPython，不查询 PATH、不下载、不安装第三方依赖。

    冻结后端不是 Python 解释器，必须另行提供经过发行核验的私有运行时；
    当前冻结模式明确失败，防止静默使用系统 Python。已存在副本只核验，不覆盖。
    """
    if os.name != "nt" or getattr(sys, "frozen", False) or sys.version_info[:2] != (3, 12):
        raise IsolationError("M18_RUNTIME_UNAVAILABLE", "当前环境没有固定 Python 3.12 脚本运行时")
    fixed = Path(getattr(sys, "_base_executable", sys.executable))
    source = Path(source_executable) if source_executable is not None else fixed
    _ordinary(source)
    if source.resolve() != fixed.resolve() or source.name.casefold() != "python.exe":
        raise IsolationError("M18_RUNTIME_UNAVAILABLE", "脚本运行时只能来自当前固定 CPython")
    private_root = _ordinary(Path(private_root), exists=False)
    target = private_root / "python312"
    executable = target / "python.exe"
    if target.exists():
        _verify_runtime(executable)
        return executable
    source_root = source.parent
    if not (source_root / "python312.dll").is_file() or not (source_root / "Lib" / "encodings").is_dir():
        raise IsolationError("M18_RUNTIME_UNAVAILABLE", "固定 CPython 标准库不完整")
    target.mkdir(parents=True, exist_ok=False)
    for name in ("python.exe", "python3.dll", "python312.dll", "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"):
        original = source_root / name
        if original.is_file():
            _ordinary(original)
            shutil.copyfile(original, target / name)
    for directory in ("Lib", "DLLs"):
        original = source_root / directory
        for path in original.rglob("*"):
            relative = path.relative_to(original)
            if any(part.casefold() in {"site-packages", "__pycache__", "test", "tests", "idlelib", "tkinter", "ensurepip", "venv"} for part in relative.parts):
                continue
            if path.name.casefold().startswith(("_test", "_ctypes_test", "_tkinter", "tk86", "tcl86")):
                continue
            _ordinary(path)
            destination = target / directory / relative
            if path.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            elif path.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
    # _pth 在解释器级锁定搜索路径；不包含 import site，因此不加载环境或用户插件。
    (target / "python312._pth").write_text(".\nLib\nDLLs\n", encoding="utf-8")
    _disable_sxs_manifest(target / "python.exe", 1)
    for path in target.rglob("*"):
        if path.suffix.casefold() in {".dll", ".pyd"}:
            _disable_sxs_manifest(path, 2)
    (target / _MANIFEST).write_text(json.dumps({"version": "3.12", "transform": "manifestless-console", "files": _runtime_manifest(target)}, sort_keys=True), encoding="utf-8")
    _verify_runtime(executable)
    return executable


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("nLength", w.DWORD), ("lpSecurityDescriptor", w.LPVOID), ("bInheritHandle", w.BOOL)]


class _STARTUPINFO(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR), ("lpTitle", w.LPWSTR),
                ("dwX", w.DWORD), ("dwY", w.DWORD), ("dwXSize", w.DWORD), ("dwYSize", w.DWORD),
                ("dwXCountChars", w.DWORD), ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD),
                ("dwFlags", w.DWORD), ("wShowWindow", w.WORD), ("cbReserved2", w.WORD),
                ("lpReserved2", w.LPVOID), ("hStdInput", w.HANDLE), ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE)]


class _STARTUPINFOEX(ctypes.Structure):
    _fields_ = [("StartupInfo", _STARTUPINFO), ("lpAttributeList", w.LPVOID)]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE), ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


class _CAPABILITIES(ctypes.Structure):
    _fields_ = [("AppContainerSid", w.LPVOID), ("Capabilities", w.LPVOID), ("CapabilityCount", w.DWORD), ("Reserved", w.DWORD)]


class _BASIC_LIMIT(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", w.DWORD), ("Affinity", ctypes.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _EXTENDED_LIMIT(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _BASIC_LIMIT), ("IoInfo", _IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


class _ACCOUNTING(ctypes.Structure):
    _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                ("TotalPageFaultCount", w.DWORD), ("TotalProcesses", w.DWORD), ("ActiveProcesses", w.DWORD), ("TotalTerminatedProcesses", w.DWORD)]


class _GENERIC_MAPPING(ctypes.Structure):
    _fields_ = [("GenericRead", w.DWORD), ("GenericWrite", w.DWORD), ("GenericExecute", w.DWORD), ("GenericAll", w.DWORD)]


class _Native:
    def __init__(self):
        if os.name != "nt":
            raise IsolationError("M18_ISOLATION_UNAVAILABLE", "LPAC 仅支持 Windows")
        self.k = ctypes.WinDLL("kernel32", use_last_error=True)
        self.a = ctypes.WinDLL("advapi32", use_last_error=True)
        self.u = ctypes.WinDLL("userenv", use_last_error=True)
        self._bind(self.k, "CloseHandle", [w.HANDLE], w.BOOL)
        self._bind(self.k, "LocalFree", [w.LPVOID], w.LPVOID)
        self._bind(self.k, "GetCurrentProcess", [], w.HANDLE)
        self._bind(self.k, "GetCurrentThread", [], w.HANDLE)
        self._bind(self.k, "CreateJobObjectW", [w.LPVOID, w.LPCWSTR], w.HANDLE)
        self._bind(self.k, "SetInformationJobObject", [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD], w.BOOL)
        self._bind(self.k, "QueryInformationJobObject", [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, w.LPVOID], w.BOOL)
        self._bind(self.k, "AssignProcessToJobObject", [w.HANDLE, w.HANDLE], w.BOOL)
        self._bind(self.k, "TerminateJobObject", [w.HANDLE, w.UINT], w.BOOL)
        self._bind(self.k, "TerminateProcess", [w.HANDLE, w.UINT], w.BOOL)
        self._bind(self.k, "WaitForSingleObject", [w.HANDLE, w.DWORD], w.DWORD)
        self._bind(self.k, "ResumeThread", [w.HANDLE], w.DWORD)
        self._bind(self.k, "GetExitCodeProcess", [w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL)
        self._bind(self.k, "GetProcessMitigationPolicy", [w.HANDLE, ctypes.c_int, w.LPVOID, ctypes.c_size_t], w.BOOL)
        self._bind(self.k, "CreatePipe", [ctypes.POINTER(w.HANDLE), ctypes.POINTER(w.HANDLE), ctypes.POINTER(_SECURITY_ATTRIBUTES), w.DWORD], w.BOOL)
        self._bind(self.k, "SetHandleInformation", [w.HANDLE, w.DWORD, w.DWORD], w.BOOL)
        self._bind(self.k, "ReadFile", [w.HANDLE, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD), w.LPVOID], w.BOOL)
        self._bind(self.k, "InitializeProcThreadAttributeList", [w.LPVOID, w.DWORD, w.DWORD, ctypes.POINTER(ctypes.c_size_t)], w.BOOL)
        self._bind(self.k, "UpdateProcThreadAttribute", [w.LPVOID, w.DWORD, ctypes.c_size_t, w.LPVOID, ctypes.c_size_t, w.LPVOID, w.LPVOID], w.BOOL)
        self._bind(self.k, "DeleteProcThreadAttributeList", [w.LPVOID], None)
        self._bind(self.k, "CreateProcessW", [w.LPCWSTR, w.LPWSTR, w.LPVOID, w.LPVOID, w.BOOL, w.DWORD, w.LPVOID, w.LPCWSTR, ctypes.POINTER(_STARTUPINFOEX), ctypes.POINTER(_PROCESS_INFORMATION)], w.BOOL)
        self._bind(self.a, "OpenProcessToken", [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)], w.BOOL)
        self._bind(self.a, "OpenThreadToken", [w.HANDLE, w.DWORD, w.BOOL, ctypes.POINTER(w.HANDLE)], w.BOOL)
        self._bind(self.a, "DuplicateToken", [w.HANDLE, ctypes.c_int, ctypes.POINTER(w.HANDLE)], w.BOOL)
        self._bind(self.a, "AccessCheck", [w.LPVOID, w.HANDLE, w.DWORD, ctypes.POINTER(_GENERIC_MAPPING), w.LPVOID, ctypes.POINTER(w.DWORD), ctypes.POINTER(w.DWORD), ctypes.POINTER(w.BOOL)], w.BOOL)
        self._bind(self.a, "GetTokenInformation", [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD, ctypes.POINTER(w.DWORD)], w.BOOL)
        self._bind(self.a, "ConvertSidToStringSidW", [w.LPVOID, ctypes.POINTER(w.LPWSTR)], w.BOOL)
        self._bind(self.a, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [w.LPCWSTR, w.DWORD, ctypes.POINTER(w.LPVOID), w.LPVOID], w.BOOL)
        self._bind(self.a, "ConvertSecurityDescriptorToStringSecurityDescriptorW", [w.LPVOID, w.DWORD, w.DWORD, ctypes.POINTER(w.LPWSTR), w.LPVOID], w.BOOL)
        self._bind(self.a, "GetNamedSecurityInfoW", [w.LPWSTR, ctypes.c_int, w.DWORD, ctypes.POINTER(w.LPVOID), ctypes.POINTER(w.LPVOID), ctypes.POINTER(w.LPVOID), ctypes.POINTER(w.LPVOID), ctypes.POINTER(w.LPVOID)], w.DWORD)
        self._bind(self.a, "SetFileSecurityW", [w.LPCWSTR, w.DWORD, w.LPVOID], w.BOOL)
        self._bind(self.a, "FreeSid", [w.LPVOID], w.LPVOID)
        self._bind(self.u, "CreateAppContainerProfile", [w.LPCWSTR, w.LPCWSTR, w.LPCWSTR, w.LPVOID, w.DWORD, ctypes.POINTER(w.LPVOID)], ctypes.c_long)
        self._bind(self.u, "DeleteAppContainerProfile", [w.LPCWSTR], ctypes.c_long)

    @staticmethod
    def _bind(library, name, args, result):
        fn = getattr(library, name)
        fn.argtypes, fn.restype = args, result

    @staticmethod
    def check(result, stage):
        if not result:
            raise IsolationError("M18_ISOLATION_UNAVAILABLE", f"Windows 隔离初始化失败（{stage}，{ctypes.get_last_error()}）")

    def token(self, process):
        handle = w.HANDLE()
        self.check(self.a.OpenProcessToken(process, 0xA, ctypes.byref(handle)), "token")
        return handle

    def token_info(self, token, kind):
        needed = w.DWORD()
        self.a.GetTokenInformation(token, kind, None, 0, ctypes.byref(needed))
        buffer = ctypes.create_string_buffer(needed.value)
        self.check(self.a.GetTokenInformation(token, kind, buffer, len(buffer), ctypes.byref(needed)), f"token-info-{kind}")
        return buffer

    def sid_string(self, sid):
        text = w.LPWSTR()
        self.check(self.a.ConvertSidToStringSidW(sid, ctypes.byref(text)), "sid")
        try:
            return text.value
        finally:
            self.k.LocalFree(text)

    def user_sid(self):
        token = self.token(self.k.GetCurrentProcess())
        try:
            info = self.token_info(token, 1)
            return self.sid_string(ctypes.cast(info, ctypes.POINTER(w.LPVOID))[0])
        finally:
            self.k.CloseHandle(token)

    def verify_lpac(self, token, user, package_sid):
        """核验 LPAC 实际访问语义，不忽略部分 Windows 对 class 46 的拒绝。

        TokenIsAppContainer 对普通 AppContainer 也为真；LPAC 还必须拒绝仅
        ALL APPLICATION PACKAGES 允许的资源。第二个允许对照避免失败即成功。
        此处只有内存描述符，不授予实际系统目录权限。
        """
        for kind, expected in ((29, 1), (20, 0), (26, 0), (30, 0)):
            if int.from_bytes(self.token_info(token, kind).raw[:4], "little") != expected:
                return False
        actual = self.token_info(token, 31)
        if self.sid_string(ctypes.cast(actual, ctypes.POINTER(w.LPVOID))[0]) != package_sid:
            return False
        integrity = self.token_info(token, 25)
        if self.sid_string(ctypes.cast(integrity, ctypes.POINTER(w.LPVOID))[0]) != "S-1-16-4096":
            return False
        duplicate = w.HANDLE()
        self.check(self.a.DuplicateToken(token, 2, ctypes.byref(duplicate)), "token-duplicate")
        try:
            outcomes = []
            for package_group in ("S-1-15-2-1", "S-1-15-2-2"):
                descriptor = w.LPVOID()
                text = f"O:{user}G:{user}D:(A;;0x1;;;WD)(A;;0x1;;;{package_group})"
                self.check(self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(text, 1, ctypes.byref(descriptor), None), "token-probe-descriptor")
                try:
                    mapping = _GENERIC_MAPPING(0x120089, 0x120116, 0x1200A0, 0x1F01FF)
                    privileges = ctypes.create_string_buffer(512)
                    size, granted, allowed = w.DWORD(len(privileges)), w.DWORD(), w.BOOL()
                    self.check(self.a.AccessCheck(descriptor, duplicate, 1, ctypes.byref(mapping), privileges, ctypes.byref(size), ctypes.byref(granted), ctypes.byref(allowed)), "token-access-check")
                    outcomes.append(bool(allowed.value))
                finally:
                    self.k.LocalFree(descriptor)
            return outcomes == [False, True]
        finally:
            self.k.CloseHandle(duplicate)

    def acl_diagnostics(self, path, user):
        """仅私有目录失败时的固定诊断；不返回路径、SID 或完整安全描述符。"""
        owner, group, dacl, sacl, descriptor = w.LPVOID(), w.LPVOID(), w.LPVOID(), w.LPVOID(), w.LPVOID()
        token = duplicate = None
        try:
            token = self.token(self.k.GetCurrentProcess())
            info = self.token_info(token, 25)
            integrity = self.sid_string(ctypes.cast(info, ctypes.POINTER(w.LPVOID))[0]).rsplit("-", 1)[-1]
            thread = w.HANDLE()
            impersonating = bool(self.a.OpenThreadToken(self.k.GetCurrentThread(), 0x8, True, ctypes.byref(thread)))
            if impersonating:
                self.k.CloseHandle(thread)
            error = self.a.GetNamedSecurityInfoW(str(path), 1, 0x1 | 0x2 | 0x4 | 0x10, ctypes.byref(owner), ctypes.byref(group),
                                                 ctypes.byref(dacl), ctypes.byref(sacl), ctypes.byref(descriptor))
            if error:
                return f"host-il-{integrity}-thread-{int(impersonating)}-sd-error-{error}"
            same_owner = self.sid_string(owner) == user
            label_text = w.LPWSTR()
            self.check(self.a.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 0x10, ctypes.byref(label_text), None), "acl-diagnostic-label")
            try:
                match = re.search(r"\(ML;[^)]*;;;([^;)]+)\)", label_text.value or "")
                labels = {"LW": "4096", "ME": "8192", "HI": "12288", "SI": "16384"}
                label = labels.get(match.group(1), "other") if match else "absent"
            finally:
                self.k.LocalFree(label_text)
            duplicate = w.HANDLE()
            self.check(self.a.DuplicateToken(token, 2, ctypes.byref(duplicate)), "acl-diagnostic-token")
            access = []
            for desired in (0x40000, 0x80000):
                mapping = _GENERIC_MAPPING(0x120089, 0x120116, 0x1200A0, 0x1F01FF)
                privileges = ctypes.create_string_buffer(512)
                size, granted, allowed = w.DWORD(len(privileges)), w.DWORD(), w.BOOL()
                self.check(self.a.AccessCheck(descriptor, duplicate, desired, ctypes.byref(mapping), privileges, ctypes.byref(size), ctypes.byref(granted), ctypes.byref(allowed)), "acl-diagnostic-access")
                access.append(int(bool(allowed.value)))
            return f"host-il-{integrity}-thread-{int(impersonating)}-owner-{int(same_owner)}-label-{label}-dac-{access[0]}-own-{access[1]}"
        except IsolationError as error:
            match = re.search(r"（([a-z0-9-]+)，([0-9]+)）", error.message)
            return "diagnostic-unavailable" + (f"-{match[1]}-{match[2]}" if match else "")
        finally:
            if duplicate:
                self.k.CloseHandle(duplicate)
            if token:
                self.k.CloseHandle(token)
            if descriptor:
                self.k.LocalFree(descriptor)

    def protect(self, path, user, app_sid=None, *, write=False, stage="private"):
        """只改私有副本/任务树的 ACL，不改系统运行时、系统目录或用户输入原件。"""
        _ordinary(path)
        grant = f"(A;OICI;{'FA' if write else 'GRGX'};;;{app_sid})" if app_sid else ""
        descriptor = w.LPVOID()
        sddl = f"D:P(A;OICI;FA;;;{user})(A;OICI;FA;;;SY){grant}S:(ML;OICI;NW;;;{'LW' if write else 'ME'})"
        self.check(self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None), "acl-descriptor")
        try:
            # stage 由可信调用点固定，不带文件名；失败证据能定位资源类别而不泄漏路径。
            kind = "directory" if path.is_dir() else "file"
            # 自建资源的 owner 具有 WRITE_DAC，但继承 DACL 未必含 WRITE_OWNER。
            # 先用合法 owner 权限保护 DACL，再按新 DACL 设置 label；不用任何接管/提升特权。
            # 任一步失败都不创建脚本进程，因此中间状态不能成为低完整性写入入口。
            for flags, operation in ((0x4 | 0x80000000, "dacl"), (0x10, "label")):
                if not self.a.SetFileSecurityW(str(path), flags, descriptor):
                    error = ctypes.get_last_error()
                    diagnostic = self.acl_diagnostics(path, user)
                    raise IsolationError("M18_ISOLATION_UNAVAILABLE", f"Windows 隔离初始化失败（acl-{stage}-{kind}-{operation}，{error}，{diagnostic}）")
        finally:
            self.k.LocalFree(descriptor)

    def protect_tree(self, root, user, app_sid=None, *, write=False, stage="private"):
        self.protect(root, user, app_sid, write=write, stage=stage)
        for path in root.rglob("*"):
            self.protect(path, user, app_sid, write=write, stage=stage)

    def active(self, job):
        accounting = _ACCOUNTING()
        self.check(self.k.QueryInformationJobObject(job, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None), "job-accounting")
        return accounting.ActiveProcesses


def run_script(runtime: Path, task_root: Path, *, cancel_event: threading.Event, timeout=30) -> dict:
    """仅在 LPAC 令牌及 Job 已验证后恢复线程；取消与任何退出路径都回收整棵树。

    task_root 是可信服务创建的独立任务目录，必须含 script.py、input、output。
    输入不可写、输出可写；脚本不能访问后端目录。LPAC 自身有 Windows 私有
    profile 存储，该 profile 在进程树退出后移除，不当作用户可回传输出。
    """
    if not isinstance(cancel_event, threading.Event) or not 0 < timeout <= 30:
        raise IsolationError("M18_ISOLATION_INVALID", "脚本取消标识或时间预算无效")
    with _RUN_LOCK:
        return _run(runtime, task_root, cancel_event, timeout)


def _run(runtime, task_root, cancel, timeout):
    _verify_runtime(Path(runtime))
    task = _ordinary(Path(task_root))
    script, inputs, outputs = task / "script.py", task / "input", task / "output"
    for path in (script, inputs, outputs):
        _ordinary(path)
    if not script.is_file() or not 0 < script.stat().st_size <= 32 * 1024 or not inputs.is_dir() or not outputs.is_dir():
        raise IsolationError("M18_ISOLATION_INVALID", "脚本任务结构或源码预算无效")
    if any(path.name not in {"script.py", "input", "output"} for path in task.iterdir()):
        raise IsolationError("M18_ISOLATION_INVALID", "隔离任务不能包含未声明文件")
    for root in (inputs, outputs):
        for path in root.rglob("*"):
            _ordinary(path)
            if path.is_file() and path.stat().st_nlink != 1:
                raise IsolationError("M18_ISOLATION_INVALID", "隔离输入输出不能包含硬链接")
    if not _file_budget(inputs, count=8) or not _file_budget(outputs, count=12):
        raise IsolationError("M18_ISOLATION_INVALID", "隔离输入输出超过文件预算")
    native = _Native()
    user = native.user_sid()
    name = "Orvia.M18." + uuid4().hex
    sid = w.LPVOID()
    created_profile = False
    handles = []
    attribute_buffer = None
    initialized_attributes = False
    info = _PROCESS_INFORMATION()
    job = None
    readers = []
    buffers = [bytearray(), bytearray()]
    buffer_lock = threading.Lock()
    overflow = threading.Event()
    token_verified = False
    reaped = False
    status = "failed"
    try:
        hr = native.u.CreateAppContainerProfile(name, "Orvia script", "M18 isolated script", None, 0, ctypes.byref(sid))
        if hr < 0:
            raise IsolationError("M18_ISOLATION_UNAVAILABLE", "无法创建本次 LPAC 身份")
        created_profile = True
        app_sid = native.sid_string(sid)
        native.protect_tree(Path(runtime).parent, user, app_sid, stage="runtime")
        native.protect(task, user, app_sid, stage="task")
        native.protect(script, user, app_sid, stage="source")
        native.protect_tree(inputs, user, app_sid, stage="input")
        native.protect_tree(outputs, user, app_sid, write=True, stage="output")

        job = native.k.CreateJobObjectW(None, None)
        native.check(job, "job-create")
        handles.append(job)
        limit = _EXTENDED_LIMIT()
        limit.BasicLimitInformation.LimitFlags = 0x2000 | 0x8 | 0x100 | 0x200
        limit.BasicLimitInformation.ActiveProcessLimit = 4
        limit.ProcessMemoryLimit = limit.JobMemoryLimit = _MEMORY_LIMIT
        native.check(native.k.SetInformationJobObject(job, 9, ctypes.byref(limit), ctypes.sizeof(limit)), "job-limit")
        verified_limit = _EXTENDED_LIMIT()
        native.check(native.k.QueryInformationJobObject(job, 9, ctypes.byref(verified_limit), ctypes.sizeof(verified_limit), None), "job-limit-check")
        if (verified_limit.BasicLimitInformation.LimitFlags & limit.BasicLimitInformation.LimitFlags != limit.BasicLimitInformation.LimitFlags
                or verified_limit.BasicLimitInformation.ActiveProcessLimit != 4
                or verified_limit.ProcessMemoryLimit != _MEMORY_LIMIT or verified_limit.JobMemoryLimit != _MEMORY_LIMIT):
            raise IsolationError("M18_ISOLATION_UNAVAILABLE", "脚本进程回收或资源上限核验失败")
        ui = w.DWORD(0xFF)
        native.check(native.k.SetInformationJobObject(job, 4, ctypes.byref(ui), ctypes.sizeof(ui)), "job-ui-limit")
        checked_ui = w.DWORD()
        native.check(native.k.QueryInformationJobObject(job, 4, ctypes.byref(checked_ui), ctypes.sizeof(checked_ui), None), "job-ui-check")
        if checked_ui.value != 0xFF:
            raise IsolationError("M18_ISOLATION_UNAVAILABLE", "脚本桌面与剪贴板隔离核验失败")

        attrs = _SECURITY_ATTRIBUTES(ctypes.sizeof(_SECURITY_ATTRIBUTES), None, True)
        pipes = []
        for _ in range(3):
            read, write = w.HANDLE(), w.HANDLE()
            native.check(native.k.CreatePipe(ctypes.byref(read), ctypes.byref(write), ctypes.byref(attrs), 0), "pipe")
            handles.extend([read.value, write.value])
            pipes.append((read.value, write.value))
        stdin_read, stdin_write = pipes[0]
        out_read, out_write = pipes[1]
        err_read, err_write = pipes[2]
        for handle in (stdin_write, out_read, err_read):
            native.check(native.k.SetHandleInformation(handle, 1, 0), "pipe-inheritance")
        native.k.CloseHandle(stdin_write)
        handles.remove(stdin_write)

        size = ctypes.c_size_t()
        native.k.InitializeProcThreadAttributeList(None, 4, 0, ctypes.byref(size))
        attribute_buffer = ctypes.create_string_buffer(size.value)
        native.check(native.k.InitializeProcThreadAttributeList(attribute_buffer, 4, 0, ctypes.byref(size)), "attributes")
        initialized_attributes = True
        capabilities = _CAPABILITIES(sid, None, 0, 0)
        opt_out = w.DWORD(1)
        inherited = (w.HANDLE * 3)(stdin_read, out_write, err_write)
        mitigation = ctypes.c_uint64(1 << 28)
        for identifier, value in ((0x20009, capabilities), (0x2000F, opt_out), (0x20002, inherited), (0x20007, mitigation)):
            native.check(native.k.UpdateProcThreadAttribute(attribute_buffer, 0, identifier, ctypes.byref(value), ctypes.sizeof(value), None, None), "attribute")
        startup = _STARTUPINFOEX()
        startup.StartupInfo.cb = ctypes.sizeof(startup)
        startup.StartupInfo.dwFlags = 0x100
        startup.StartupInfo.hStdInput, startup.StartupInfo.hStdOutput, startup.StartupInfo.hStdError = stdin_read, out_write, err_write
        startup.lpAttributeList = ctypes.cast(attribute_buffer, w.LPVOID)
        # 不继承后端环境；仅保留系统 DLL 定位及任务内部临时位置。
        env = {"SystemRoot": os.environ.get("SystemRoot", r"C:\Windows"), "WINDIR": os.environ.get("WINDIR", r"C:\Windows"),
               "LOCALAPPDATA": _local_appdata(), "TEMP": str(outputs), "TMP": str(outputs)}
        environment = ctypes.create_unicode_buffer("\0".join(f"{key}={value}" for key, value in sorted(env.items())) + "\0\0")
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(runtime), "-I", "-S", "-B", "-u", "-X", "utf8", str(script)]))
        flags = 0x80000 | 0x400 | 0x4 | 0x8  # DETACHED_PROCESS 不创建或连接个人控制台。
        native.check(native.k.CreateProcessW(str(runtime), command, None, None, True, flags, environment, str(task), ctypes.byref(startup), ctypes.byref(info)), "lpac-create")
        handles.extend([info.hProcess, info.hThread])
        native.check(native.k.AssignProcessToJobObject(job, info.hProcess), "job-assign")
        token = native.token(info.hProcess)
        try:
            token_verified = native.verify_lpac(token, user, app_sid)
        finally:
            native.k.CloseHandle(token)
        if not token_verified:
            raise IsolationError("M18_ISOLATION_UNAVAILABLE", "脚本 LPAC 身份或零能力令牌核验失败")
        mitigation_check = w.DWORD()
        native.check(native.k.GetProcessMitigationPolicy(info.hProcess, 4, ctypes.byref(mitigation_check), ctypes.sizeof(mitigation_check)), "win32k-check")
        if not mitigation_check.value & 1:
            raise IsolationError("M18_ISOLATION_UNAVAILABLE", "脚本 Win32k 禁用核验失败")
        for handle in (stdin_read, out_write, err_write):
            native.k.CloseHandle(handle)
            handles.remove(handle)

        def read_pipe(handle, index):
            chunk = ctypes.create_string_buffer(1024)
            count = w.DWORD()
            while native.k.ReadFile(handle, chunk, len(chunk), ctypes.byref(count), None) and count.value:
                with buffer_lock:
                    remaining = _OUTPUT_LIMIT - sum(map(len, buffers))
                    buffers[index].extend(chunk.raw[:min(count.value, remaining)])
                    if count.value > remaining:
                        overflow.set()
                        return

        for index, handle in enumerate((out_read, err_read)):
            reader = threading.Thread(target=read_pipe, args=(handle, index), daemon=True)
            readers.append(reader)
            reader.start()
        if cancel.is_set():
            status = "cancelled"
        else:
            if native.k.ResumeThread(info.hThread) == 0xFFFFFFFF:
                raise IsolationError("M18_ISOLATION_UNAVAILABLE", "隔离线程不能启动")
            deadline = time.monotonic() + timeout
            while native.k.WaitForSingleObject(info.hProcess, 25) == 0x102:
                if cancel.is_set():
                    status = "cancelled"
                    break
                if overflow.is_set():
                    status = "output_limit"
                    break
                if not _file_budget(outputs, count=12):
                    status = "output_limit"
                    break
                if time.monotonic() >= deadline:
                    status = "timed_out"
                    break
            else:
                code = w.DWORD()
                native.check(native.k.GetExitCodeProcess(info.hProcess, ctypes.byref(code)), "exit-code")
                status = "completed" if code.value == 0 else "failed"
        # 根进程退出也结束遗留子进程，不能允许后台脚本继续写入隔离结果。
        native.check(native.k.TerminateJobObject(job, 0xE018), "job-terminate")
        deadline = time.monotonic() + 5
        while native.active(job) and time.monotonic() < deadline:
            time.sleep(0.02)
        reaped = native.active(job) == 0
        if not reaped:
            raise IsolationError("M18_ISOLATION_UNAVAILABLE", "未确认隔离进程树退出，禁止回传结果")
        for reader in readers:
            reader.join(timeout=2)
        if any(reader.is_alive() for reader in readers):
            raise IsolationError("M18_ISOLATION_UNAVAILABLE", "隔离输出管道未正常收尾")
        if overflow.is_set() and status in {"completed", "failed"}:
            status = "output_limit"
        if not _file_budget(outputs, count=12):
            status = "output_limit"
        code = w.DWORD()
        native.check(native.k.GetExitCodeProcess(info.hProcess, ctypes.byref(code)), "exit-code")
        display, remaining = [], _OUTPUT_LIMIT
        for data in buffers:
            text = bytes(data).decode("utf-8", errors="replace")
            clean = "".join(char for char in text if char >= " " or char in "\r\n\t")
            encoded = clean.encode("utf-8")
            if clean != text or len(encoded) > remaining:
                status = "output_limit"
            limited = encoded[:remaining].decode("utf-8", errors="ignore")
            remaining -= len(limited.encode("utf-8"))
            display.append(limited)
        return {"status": status, "exit_code": code.value, "stdout": display[0],
                "stderr": display[1], "token_verified": token_verified,
                "processes_reaped": reaped, "isolation": "lpac"}
    finally:
        # KILL_ON_JOB_CLOSE 同样覆盖父进程异常退出；本进程的正常异常路径先显式终止。
        if job:
            native.k.TerminateJobObject(job, 0xE018)
        if info.hProcess and not reaped:
            native.k.TerminateProcess(info.hProcess, 0xE018)
            native.k.WaitForSingleObject(info.hProcess, 5000)
        for reader in readers:
            reader.join(timeout=2)
        for handle in reversed(handles):
            native.k.CloseHandle(handle)
        if initialized_attributes:
            native.k.DeleteProcThreadAttributeList(attribute_buffer)
        if sid:
            native.a.FreeSid(sid)
        if created_profile:
            native.u.DeleteAppContainerProfile(name)
