"""Computer 路径策略：所有文件观察都限制在用户明确授权的目录内。"""

from __future__ import annotations

import os
import stat
from pathlib import Path


class ToolError(Exception):
    """向协议层传递稳定的只读工具错误码，不携带本地路径细节。"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def sensitive(name: str) -> bool:
    """隐藏凭据目录和应用内部目录，避免扫描泄露配置。"""
    return name.casefold() in {".git", ".env", ".env.local", ".orvia", "node_modules", ".venv"}


def _reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as exc:
        raise ToolError("path_unavailable", "路径无法访问。") from exc
    attrs = getattr(info, "st_file_attributes", 0)
    return path.is_symlink() or bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


class PathPolicy:
    """保存一次授权根，并在每次调用前重新校验根身份和目标边界。"""

    def __init__(self, root: str):
        candidate = Path(root)
        if not candidate.is_absolute() or candidate.is_reserved():
            raise ToolError("invalid_root", "授权目录必须是本地绝对路径。")
        if candidate.anchor.startswith("\\\\"):
            raise ToolError("invalid_root", "不允许授权 UNC 或网络路径。")
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise ToolError("invalid_root", "授权目录不存在或不可访问。") from exc
        if not resolved.is_dir() or _reparse(resolved):
            raise ToolError("invalid_root", "授权根必须是普通目录，不能是链接或联接。")
        self.root = resolved
        self._identity = self._stat_identity(resolved)

    @staticmethod
    def _stat_identity(path: Path) -> tuple[int, int, int, int]:
        try:
            info = path.stat()
            # 目录内容变化是正常扫描场景；只绑定目录身份，避免新增文件导致授权失效。
            return (info.st_dev, info.st_ino, 0, 0)
        except OSError as exc:
            raise ToolError("path_unavailable", "授权目录无法访问。") from exc

    def _check_root(self) -> None:
        if _reparse(self.root) or not self.root.is_dir() or self._stat_identity(self.root) != self._identity:
            raise ToolError("permission_denied", "授权目录身份已变化，请重新授权。")

    def resolve(self, relative: str, expected: str | None = None) -> Path:
        """解析授权根内相对路径；绝对路径、越界路径和重解析点全部拒绝。"""
        self._check_root()
        if not isinstance(relative, str) or not relative or len(relative) > 1000:
            raise ToolError("invalid_path", "路径参数无效。")
        supplied = Path(relative)
        if supplied.is_absolute() or supplied.drive or supplied.anchor:
            raise ToolError("path_denied", "工具只接受授权根内相对路径。")
        if any(part == ".." for part in supplied.parts):
            raise ToolError("path_denied", "路径不能越过授权目录。")
        if any(sensitive(part) for part in supplied.parts):
            raise ToolError("path_denied", "不允许读取应用内部或凭据目录。")
        target = self.root.joinpath(supplied)
        try:
            resolved = target.resolve(strict=True)
        except OSError as exc:
            raise ToolError("path_unavailable", "目标路径不存在或不可访问。") from exc
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ToolError("path_denied", "目标路径不在授权目录内。") from exc
        if _reparse(resolved) or any(_reparse(parent) for parent in resolved.parents if parent != self.root):
            raise ToolError("path_denied", "不允许访问符号链接或重解析路径。")
        if expected == "directory" and not resolved.is_dir():
            raise ToolError("type_mismatch", "目标不是目录。")
        if expected == "file" and not resolved.is_file():
            raise ToolError("type_mismatch", "目标不是普通文件。")
        return resolved

    def validate_open_file(self, fd: int, target: Path) -> os.stat_result:
        """读取前后复核句柄元数据，降低路径替换导致的 TOCTOU 风险。"""
        try:
            info = os.fstat(fd)
        except OSError as exc:
            raise ToolError("path_unavailable", "文件句柄无法读取。") from exc
        if not stat.S_ISREG(info.st_mode):
            raise ToolError("type_mismatch", "目标不是普通文件。")
        try:
            current = target.stat()
        except OSError as exc:
            raise ToolError("path_unavailable", "文件状态无法读取。") from exc
        if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
            raise ToolError("file_changed", "文件身份在读取期间发生变化。")
        return info


def safe_stat(path: Path) -> os.stat_result:
    """只返回已经通过路径策略的普通文件或目录状态。"""
    try:
        info = path.stat()
    except OSError as exc:
        raise ToolError("path_unavailable", "路径状态无法读取。") from exc
    if _reparse(path):
        raise ToolError("path_denied", "不允许读取重解析路径。")
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
        raise ToolError("type_mismatch", "仅支持普通文件和目录。")
    return info
