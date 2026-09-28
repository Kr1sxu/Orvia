"""M04 文件动作计划、审批、执行核验与受限撤销。"""

from __future__ import annotations

import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..storage import Store
from .paths import PathPolicy, ToolError, sensitive


class Action(BaseModel):
    """计划中的单个动作；只允许 mkdir、move 和 rename，不允许删除或覆盖。"""
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["mkdir", "move", "rename"]
    source: str | None = Field(default=None, max_length=1000)
    destination: str = Field(min_length=1, max_length=1000)


class ActionPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    mission_id: UUID
    root: str = Field(min_length=1, max_length=1000)
    actions: list[Action] = Field(min_length=1, max_length=100)


class ActionService:
    """所有写操作都必须经过计划创建和显式 approve；恢复不自动重放文件动作。"""

    def __init__(self, store: Store):
        self.store = store

    @staticmethod
    def _relative(policy: PathPolicy, value: str, *, allow_missing: bool = False,
                  planned_dirs: set[str] | None = None) -> Path:
        if not value or len(value) > 1000:
            raise ToolError("INVALID_PATH", "动作路径无效")
        raw = Path(value)
        if raw.is_absolute() or raw.drive or raw.anchor or any(part == ".." for part in raw.parts):
            raise ToolError("PATH_DENIED", "动作路径必须是授权根内相对路径")
        if any(sensitive(part) for part in raw.parts):
            raise ToolError("PATH_DENIED", "不允许操作应用内部或凭据目录")
        target = policy.root.joinpath(raw)
        parent = target.parent
        try:
            parent_resolved = parent.resolve(strict=True)
            parent_resolved.relative_to(policy.root)
        except (OSError, ValueError):
            parent_name = parent.relative_to(policy.root).as_posix()
            if not planned_dirs or parent_name not in planned_dirs:
                raise ToolError("PATH_UNAVAILABLE", "动作父目录不存在或不在授权范围") from None
            parent_resolved = parent
        if parent_resolved != policy.root and parent_resolved.is_symlink():
            raise ToolError("PATH_DENIED", "动作路径不能经过符号链接")
        if target.exists() or target.is_symlink():
            if not allow_missing:
                return target
            raise ToolError("CONFLICT", "目标已存在，拒绝覆盖")
        return target

    @staticmethod
    def _identity(path: Path) -> dict:
        info = path.stat()
        is_directory = stat.S_ISDIR(info.st_mode)
        return {"dev": info.st_dev, "ino": info.st_ino, "size": None if is_directory else info.st_size,
                "mtime_ns": None if is_directory else info.st_mtime_ns,
                "kind": "directory" if is_directory else "file"}

    async def create_plan(self, request: ActionPlanRequest) -> dict:
        policy = PathPolicy(request.root)
        normalized = []
        planned_dirs = {action.destination.strip("/\\") for action in request.actions if action.kind == "mkdir"}
        for sequence, action in enumerate(request.actions):
            if action.kind == "mkdir":
                if action.source is not None:
                    raise ToolError("INVALID_PLAN", "mkdir 不能携带 source")
                destination = self._relative(policy, action.destination, allow_missing=True, planned_dirs=planned_dirs)
            else:
                if action.source is None:
                    raise ToolError("INVALID_PLAN", "文件动作必须携带 source")
                source = policy.resolve(action.source, "file")
                destination = self._relative(policy, action.destination, allow_missing=True, planned_dirs=planned_dirs)
                if source == destination:
                    raise ToolError("INVALID_PLAN", "源和目标不能相同")
                if source.stat().st_dev != policy.root.stat().st_dev:
                    raise ToolError("CROSS_VOLUME", "不允许跨卷文件动作")
            normalized.append({"sequence": sequence, "kind": action.kind, "source": action.source,
                               "destination": action.destination})
        operation_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        operation = {"id": operation_id, "mission_id": str(request.mission_id), "root": str(policy.root),
                     "status": "planned", "created_at": now, "plan": {"actions": normalized}}
        await self.store.create_operation(operation)
        return {"operation_id": operation_id, "mission_id": str(request.mission_id), "status": "planned",
                "actions": normalized, "requires_approval": True}

    async def approve(self, operation_id: str) -> dict:
        operation = await self._require(operation_id)
        if operation["status"] != "planned":
            raise ToolError("INVALID_STATE", "只有 planned 计划可以审批")
        await self.store.update_operation(operation_id, "approved")
        return {"operation_id": operation_id, "status": "approved"}

    async def execute(self, operation_id: str) -> dict:
        operation = await self._require(operation_id)
        if operation["status"] != "approved":
            raise ToolError("APPROVAL_REQUIRED", "文件动作必须先获得用户审批")
        policy = PathPolicy(operation["root"])
        await self.store.update_operation(operation_id, "running")
        completed = 0
        try:
            for entry in operation["plan"]["actions"]:
                sequence, kind = entry["sequence"], entry["kind"]
                persisted_entry = next(item for item in operation["entries"] if item["sequence"] == sequence)
                if persisted_entry["status"] == "completed":
                    completed += 1
                    continue
                planned_dirs = {x["destination"] for x in operation["plan"]["actions"] if x["kind"] == "mkdir"}
                destination = self._relative(policy, entry["destination"], allow_missing=True, planned_dirs=planned_dirs)
                before = None
                if kind == "mkdir":
                    destination.mkdir()
                    after = self._identity(destination)
                else:
                    source = policy.resolve(entry["source"], "file")
                    if destination.exists() or destination.is_symlink():
                        raise ToolError("CONFLICT", "目标已存在，拒绝覆盖")
                    before = self._identity(source)
                    os.rename(source, destination)
                    after = self._identity(destination)
                await self.store.update_operation(operation_id, "running", sequence=sequence,
                                                  entry_status="completed", before=before, after=after)
                completed += 1
        except (OSError, ToolError) as error:
            message = error.message if isinstance(error, ToolError) else "文件动作执行失败"
            await self.store.update_operation(operation_id, "failed", error=message,
                                              sequence=completed, entry_status="failed")
            return {"operation_id": operation_id, "status": "failed", "completed": completed,
                    "error": message, "needs_recovery_check": True}
        await self.store.update_operation(operation_id, "completed")
        return {"operation_id": operation_id, "status": "completed", "completed": completed,
                "verified": await self.verify(operation_id)}

    async def resume(self, operation_id: str) -> dict:
        """恢复被连接中断标记的计划；已记账步骤跳过，未记账步骤重新核验后执行。"""
        operation = await self._require(operation_id)
        if operation["status"] != "interrupted":
            raise ToolError("INVALID_STATE", "只有 interrupted 计划可以恢复")
        await self.store.update_operation(operation_id, "approved")
        return await self.execute(operation_id)

    async def verify(self, operation_id: str) -> dict:
        operation = await self._require(operation_id)
        policy = PathPolicy(operation["root"])
        checks = []
        for entry in operation["plan"]["actions"]:
            destination = self._relative(policy, entry["destination"], allow_missing=False)
            exists = destination.exists() and not destination.is_symlink()
            source_exists = False
            if entry["source"]:
                try:
                    source_exists = policy.resolve(entry["source"]).exists()
                except ToolError:
                    source_exists = False
            checks.append({"sequence": entry["sequence"], "destination_exists": exists,
                           "source_absent": not source_exists})
        return {"operation_id": operation_id, "complete": all(x["destination_exists"] and x["source_absent"] for x in checks), "checks": checks}

    async def undo_latest(self, mission_id: str) -> dict:
        """只允许该 Mission 最近一个已完成任务，且目标身份未被外部修改时反向移动。"""
        candidates = []
        # Store 没有暴露任意 SQL；使用有限 ID 查询由调用方保留最近任务，M04 任务数受上限约束。
        # 当前实现由 get_latest_operation 查询，避免将撤销范围扩大到其他 Mission。
        operation = await self.store.get_latest_operation(mission_id)
        if operation is None or operation["status"] != "completed":
            raise ToolError("UNDO_UNAVAILABLE", "没有可安全撤销的最近文件变更任务")
        policy = PathPolicy(operation["root"])
        undone = 0
        for entry in reversed(operation["entries"]):
            if entry["status"] != "completed":
                continue
            destination = self._relative(policy, entry["destination"], allow_missing=False)
            after = __import__("json").loads(entry["after_json"]) if entry["after_json"] else None
            if not destination.exists() or self._identity(destination) != after:
                await self.store.update_operation(operation["id"], "partially_undone", error="目标已变化，停止撤销")
                raise ToolError("UNDO_CONFLICT", "目标在任务后发生变化，已停止撤销")
            if entry["kind"] == "mkdir":
                try:
                    destination.rmdir()
                except OSError:
                    await self.store.update_operation(operation["id"], "partially_undone", error="目录不为空")
                    raise ToolError("UNDO_CONFLICT", "新建目录已被使用，无法撤销") from None
            else:
                source = self._relative(policy, entry["source"], allow_missing=True)
                if source.exists():
                    raise ToolError("UNDO_CONFLICT", "原位置已有文件，拒绝覆盖")
                os.rename(destination, source)
            await self.store.update_operation(operation["id"], "completed", sequence=entry["sequence"], entry_status="undone")
            undone += 1
        await self.store.update_operation(operation["id"], "undone")
        return {"operation_id": operation["id"], "status": "undone", "undone": undone}

    async def _require(self, operation_id: str) -> dict:
        operation = await self.store.get_operation(operation_id)
        if operation is None:
            raise ToolError("NOT_FOUND", "操作计划不存在")
        return operation
