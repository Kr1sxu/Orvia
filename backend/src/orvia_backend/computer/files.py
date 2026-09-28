"""Computer 只读工具：流式扫描、预算截断与句柄核验。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import heapq
import json
import os
from pathlib import Path
import stat
import time
from typing import Any

from .paths import PathPolicy, ToolError, safe_stat, sensitive

MAX_ENTRIES = 5000
MAX_OUTPUT = 48 * 1024
MAX_SECONDS = 2.0
MAX_READ_BYTES = 256 * 1024
TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".log"}


def _entry(path: Path, root: Path, info: os.stat_result) -> dict[str, Any]:
    kind = "directory" if stat.S_ISDIR(info.st_mode) else "file"
    return {"path": path.relative_to(root).as_posix(), "name": path.name, "kind": kind,
            "size": info.st_size if kind == "file" else 0,
            "modified_at": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat()}


def _integer(value: int, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ToolError("invalid_arguments", "参数超出允许范围。")
    return value


@dataclass
class Scan:
    """一次操作共用条数和时间预算；截断与不可访问均显式表示不完整。"""
    started: float = field(default_factory=time.monotonic)
    count: int = 0
    complete: bool = True
    truncated: bool = False
    errors: list[dict] = field(default_factory=list)

    def error(self, code: str) -> None:
        self.complete = False
        if len(self.errors) < 20:
            self.errors.append({"code": code})

    def stop(self) -> None:
        self.complete = False
        self.truncated = True

    def budget(self) -> bool:
        if self.count >= MAX_ENTRIES or time.monotonic() - self.started >= MAX_SECONDS:
            self.stop()
            return False
        return True

    def result(self, data: dict) -> dict:
        """最终 UTF-8 JSON 有硬上限；裁剪明细时保留 partial 标志。"""
        result = {"data": data, "complete": self.complete, "truncated": self.truncated,
                  "errors": self.errors, "scanned_at": datetime.now(timezone.utc).isoformat(),
                  "scanned_entries": self.count}
        while len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > MAX_OUTPUT:
            lists = [value for value in data.values() if isinstance(value, list) and value]
            if lists:
                max(lists, key=len).pop()
            elif isinstance(data.get("text"), str) and data["text"]:
                data["text"] = data["text"][:len(data["text"]) // 2]
            else:
                raise ToolError("output_too_large", "结果超出允许大小。")
            result["complete"] = False
            result["truncated"] = True
        return result


class FileTools:
    """只读能力公共接口；每次调用重新检查授权根身份。"""

    def __init__(self, policy: PathPolicy):
        self.policy = policy

    def _walk(self, base: Path, recursive: bool, scan: Scan):
        # 显式栈避免深目录触发 Python 递归；目录也占用统一扫描预算。
        stack = [base]
        while stack and scan.budget():
            directory = stack.pop()
            try:
                self.policy.resolve(directory.relative_to(self.policy.root).as_posix(), "directory")
                with os.scandir(directory) as items:
                    for item in items:
                        if not scan.budget():
                            return
                        scan.count += 1
                        if sensitive(item.name):
                            scan.error("sensitive_path")
                            continue
                        child = Path(item.path)
                        try:
                            self.policy.resolve(child.relative_to(self.policy.root).as_posix())
                            info = safe_stat(child)
                        except ToolError as exc:
                            scan.error(exc.code)
                            continue
                        if recursive and stat.S_ISDIR(info.st_mode):
                            stack.append(child)
                        yield child, info
            except ToolError as exc:
                scan.error(exc.code)
            except OSError:
                scan.error("path_unavailable")

    def list_directory(self, path: str = ".", limit: int = 100) -> dict:
        """枚举一级目录；到达返回条数上限即保守标记截断。"""
        _integer(limit, 1, 500)
        base = self.policy.resolve(path, "directory")
        scan, entries = Scan(), []
        for child, info in self._walk(base, False, scan):
            entries.append(_entry(child, self.policy.root, info))
            if len(entries) >= limit:
                scan.stop()
                break
        return scan.result({"entries": entries})

    def search_files(self, path: str = ".", query: str = "", extension: str | None = None,
                     recursive: bool = True, limit: int = 100) -> dict:
        """按文件名子串与扩展名过滤，大小写不敏感，不读取文件内容。"""
        _integer(limit, 1, 500)
        if not isinstance(query, str) or len(query) > 256 or type(recursive) is not bool:
            raise ToolError("invalid_arguments", "搜索参数无效。")
        if extension is not None and (not isinstance(extension, str) or len(extension) > 32
                                      or any(c in extension for c in '/\\:*?')):
            raise ToolError("invalid_arguments", "扩展名参数无效。")
        wanted = "." + extension.lstrip(".").casefold() if extension else None
        base = self.policy.resolve(path, "directory")
        scan, entries = Scan(), []
        for child, info in self._walk(base, recursive, scan):
            if not stat.S_ISREG(info.st_mode) or query.casefold() not in child.name.casefold():
                continue
            if wanted and child.suffix.casefold() != wanted:
                continue
            entries.append(_entry(child, self.policy.root, info))
            if len(entries) >= limit:
                scan.stop()
                break
        return scan.result({"entries": entries})

    def get_file_metadata(self, path: str) -> dict:
        """返回普通文件或目录元数据，目录大小为零，不伪装为递归大小。"""
        target = self.policy.resolve(path)
        return Scan(count=1).result(_entry(target, self.policy.root, safe_stat(target)))

    def read_text_file(self, path: str, start_line: int = 1,
                       max_lines: int = 100, max_chars: int = 8000) -> dict:
        """严格 UTF-8 读取；跳行也计入 256 KiB 上限，前后验证版本。"""
        _integer(start_line, 1, 1_000_000)
        _integer(max_lines, 1, 1000)
        _integer(max_chars, 1, 8000)
        target = self.policy.resolve(path, "file")
        if target.suffix.casefold() not in TEXT_EXTENSIONS:
            raise ToolError("text_type_forbidden", "仅允许读取 txt、md、json、csv、log 文本。")
        fd = None
        try:
            fd = os.open(target, os.O_RDONLY | getattr(os, "O_BINARY", 0))
            before = self.policy.validate_open_file(fd, target)
            if before.st_size > MAX_READ_BYTES:
                raise ToolError("read_budget_exceeded", "文本超过 256 KiB 读取预算。")
            payload = bytearray()
            while len(payload) <= MAX_READ_BYTES:
                chunk = os.read(fd, min(16384, MAX_READ_BYTES + 1 - len(payload)))
                if not chunk:
                    break
                payload.extend(chunk)
            after = self.policy.validate_open_file(fd, target)
            if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
                raise ToolError("file_changed", "文件在读取期间发生变化，请重新读取。")
            if len(payload) > MAX_READ_BYTES:
                raise ToolError("read_budget_exceeded", "文本超过 256 KiB 读取预算。")
            try:
                text = payload.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise ToolError("encoding_invalid", "文件不是有效 UTF-8 文本。") from None
        except OSError:
            raise ToolError("path_unavailable", "文件无法访问。") from None
        finally:
            if fd is not None:
                os.close(fd)
        lines = text.splitlines(keepends=True)
        selected = lines[start_line - 1:start_line - 1 + max_lines]
        joined = "".join(selected)
        output = joined[:max_chars]
        truncated = len(output) < len(joined) or start_line - 1 + len(selected) < len(lines)
        # end_line 描述实际返回文本涉及的行；空结果为 start_line - 1。
        end_line = start_line + len(output.splitlines()) - 1
        scan = Scan(count=1, complete=not truncated, truncated=truncated)
        return scan.result({"path": target.relative_to(self.policy.root).as_posix(),
                            "text": output, "start_line": start_line, "end_line": end_line})

    def analyze_directory_space(self, path: str = ".", top_n: int = 10, min_size: int = 0) -> dict:
        """汇总逻辑字节数；仅保留有界大文件堆，不对所有文件排序。"""
        _integer(top_n, 1, 100)
        _integer(min_size, 0, 2**63 - 1)
        base = self.policy.resolve(path, "directory")
        scan = Scan()
        total = count = sequence = 0
        groups: dict[str, list[int]] = {}
        extensions: dict[str, list[int]] = {}
        large: list[tuple[int, int, dict]] = []
        for child, info in self._walk(base, True, scan):
            if not stat.S_ISREG(info.st_mode):
                continue
            size = info.st_size
            total += size
            count += 1
            relative = child.relative_to(base)
            group = relative.parts[0] if len(relative.parts) > 1 else "."
            for mapping, key in ((groups, group), (extensions, child.suffix.casefold() or "(none)")):
                slot = mapping.setdefault(key, [0, 0])
                slot[0] += size
                slot[1] += 1
            if size >= min_size:
                sequence += 1
                candidate = (size, sequence, _entry(child, self.policy.root, info))
                if len(large) < top_n:
                    heapq.heappush(large, candidate)
                elif size > large[0][0]:
                    heapq.heapreplace(large, candidate)
        def aggregate(mapping: dict) -> list[dict]:
            return [{"name": name, "bytes": value[0], "file_count": value[1]}
                    for name, value in mapping.items()]
        return scan.result({"total_bytes": total, "file_count": count,
                            "groups": aggregate(groups), "extensions": aggregate(extensions),
                            "large_files": [entry for _, _, entry in sorted(large, reverse=True)]})
