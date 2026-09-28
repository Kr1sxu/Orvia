"""系统只读工具。

所有入口均使用固定的安全模板，不接受任意命令、参数或路径；返回值带有
扫描时间和截断标记，供上层在证据汇总时区分完整结果与部分结果。
"""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path
import subprocess
import stat
import threading
import time
from typing import Any

try:
    import psutil
except ImportError:  # 运行时依赖可由主工程安装
    psutil = None


class SystemToolError(Exception):
    """系统工具拒绝或执行失败时使用的稳定错误码。"""

    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(f"{code}: {message}")


def _stamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _result(data: Any, complete: bool, truncated: bool, errors: list[dict[str, str]], entries: int) -> dict[str, Any]:
    return {"data": data, "complete": complete, "truncated": truncated, "errors": errors,
            "scanned_at": _stamp(), "scanned_entries": entries}


class SystemTools:
    """提供运行时探测、进程摘要和固定版本模板执行。"""

    def _candidate(self, path: str) -> Path | None:
        p = Path(path)
        if not p.is_file() or p.is_symlink():
            return None
        # 拒绝候选及其祖先中的 reparse point，避免工具路径被重定向。
        cur = p
        while True:
            try:
                attrs = getattr(cur.lstat(), "st_file_attributes", 0)
                if cur.is_symlink() or attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                    return None
            except OSError:
                return None
            if cur.parent == cur:
                break
            cur = cur.parent
        return p

    def detect_runtimes(self) -> dict[str, Any]:
        """按可信固定路径探测 PowerShell、Git Bash 和 WSL，不查询 PATH。"""
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        root = os.environ.get("SystemRoot", r"C:\Windows")
        specs = [
            ("powershell", [os.path.join(pf, "PowerShell", "7", "pwsh.exe"), os.path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")]),
            ("git_bash", [os.path.join(pf, "Git", "bin", "bash.exe")]),
            ("wsl", [os.path.join(root, "System32", "wsl.exe")]),
        ]
        output, errors = [], []
        for runtime, paths in specs:
            found = next((p for x in paths if (p := self._candidate(x)) is not None), None)
            item: dict[str, Any] = {"runtime": runtime, "available": bool(found)}
            if found:
                item["path"] = str(found)
                if runtime == "wsl":
                    try:
                        proc = self._spawn([str(found), "--list", "--quiet"], timeout=3)
                        if proc.returncode:
                            raise SystemToolError("WSL_UNAVAILABLE", "WSL 发行版列表不可用")
                        names = [x.strip() for x in proc.stdout.splitlines() if x.strip()]
                        item["distributions"] = names
                    except (OSError, subprocess.TimeoutExpired, SystemToolError):
                        item["distributions"] = []
                        errors.append({"code": "WSL_UNAVAILABLE", "message": "WSL 发行版探测不可用或超时"})
            output.append(item)
        return _result(output, not errors, False, errors, len(output))

    def list_processes(self, name: str = "", limit: int = 50) -> dict[str, Any]:
        """枚举进程名称和 PID；不读取命令行、环境或用户文件。"""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise SystemToolError("INVALID_LIMIT", "limit 必须为 1 到 100 的整数")
        if not isinstance(name, str) or len(name) > 200:
            raise SystemToolError("INVALID_NAME", "name 必须是不超过 200 字的字符串")
        if psutil is None:
            return _result([], False, False, [{"code": "DEPENDENCY_MISSING", "message": "psutil 未安装"}], 0)
        needle = name.casefold()
        rows, errors, scanned = [], [], 0
        start = time.monotonic()
        try:
            iterator = psutil.process_iter(["pid", "name"])
            for proc in iterator:
                if scanned >= 2000 or time.monotonic() - start > 1:
                    return _result(rows, False, True, errors + [{"code": "SCAN_BUDGET", "message": "进程扫描达到预算"}], scanned)
                scanned += 1
                try:
                    pname = proc.info.get("name")
                    if pname is None:
                        errors.append({"code": "ACCESS_DENIED", "message": "部分进程名称不可读取"})
                        continue
                    if needle and needle not in pname.casefold():
                        continue
                    rows.append({"pid": int(proc.info["pid"]), "name": pname})
                    if len(rows) >= limit:
                        return _result(rows, False, True, errors, scanned)
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    errors.append({"code": "ACCESS_DENIED", "message": "部分进程不可读取"})
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            errors.append({"code": "PROCESS_ENUMERATION_FAILED", "message": "进程枚举未完成"})
            return _result(rows, False, False, errors, scanned)
        return _result(rows, not errors, False, errors, scanned)

    def _spawn(self, argv: list[str], timeout: float = 3) -> subprocess.CompletedProcess[str]:
        env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PROGRAMFILES"}}
        # 分线程持续读取两条管道，每条至多保留 8 KiB；越界仅终止本工具启动的子进程。
        proc = subprocess.Popen(argv, shell=False, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        buffers = [bytearray(), bytearray()]
        overflow = threading.Event()

        def read_pipe(pipe, index):
            try:
                while chunk := pipe.read(1024):
                    remaining = 8192 - len(buffers[index])
                    buffers[index].extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        overflow.set()
                        proc.kill()
                        break
            finally:
                pipe.close()

        readers = [threading.Thread(target=read_pipe, args=(pipe, i), daemon=True)
                   for i, pipe in enumerate((proc.stdout, proc.stderr))]
        for reader in readers:
            reader.start()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            raise
        finally:
            for reader in readers:
                reader.join(timeout=1)
        if overflow.is_set():
            raise SystemToolError("OUTPUT_LIMIT", "固定模板输出超过 8 KiB 限额")

        def decode(data):
            # WSL 在重定向管道下可能返回 UTF-16LE，版本模板其余输出均为 ASCII/UTF-8。
            encoding = "utf-16-le" if b"\x00" in data[:80] else "utf-8-sig"
            return bytes(data).decode(encoding, errors="replace").lstrip("\ufeff")

        return subprocess.CompletedProcess(argv, proc.returncode, decode(buffers[0]), decode(buffers[1]))

    def run_template(self, template_id: str, runtime: str = "powershell", distribution: str | None = None) -> dict[str, Any]:
        """执行唯一允许的版本模板；WSL 不启动发行版，拒绝 distribution 参数。"""
        if template_id != "runtime_version":
            raise SystemToolError("UNSUPPORTED_TEMPLATE", "仅支持 runtime_version")
        if distribution is not None:
            raise SystemToolError("UNSUPPORTED", "MVP 不执行 WSL 发行版任务")
        detected = self.detect_runtimes()["data"]
        item = next((x for x in detected if x["runtime"] == runtime), None)
        if not item or not item["available"]:
            raise SystemToolError("RUNTIME_UNAVAILABLE", f"运行时不可用: {runtime}")
        path = item["path"]
        if runtime == "powershell":
            argv = [path, "-NoProfile", "-NonInteractive", "-Command", "$PSVersionTable.PSVersion.ToString()"]
        elif runtime == "git_bash":
            argv = [path, "--noprofile", "--norc", "-c", 'printf "%s\\n" "$BASH_VERSION"']
        elif runtime == "wsl":
            argv = [path, "--version"]
        else:
            raise SystemToolError("UNSUPPORTED_RUNTIME", f"不支持运行时: {runtime}")
        try:
            proc = self._spawn(argv, timeout=3)
        except subprocess.TimeoutExpired:
            raise SystemToolError("TIMEOUT", "固定模板执行超时")
        except OSError:
            raise SystemToolError("RUNTIME_UNAVAILABLE", "无法启动指定运行时")
        out = (proc.stdout or "")[:8192]
        err = [] if proc.returncode == 0 else [{"code": "COMMAND_FAILED", "message": "固定版本模板执行失败"}]
        return _result({"runtime": runtime, "version": out[:2048].strip()}, proc.returncode == 0 and len(out) <= 2048, len(out) > 2048, err, 1)
