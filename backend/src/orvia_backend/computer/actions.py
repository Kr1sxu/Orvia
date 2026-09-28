"""M04 文件动作计划、审批、执行核验与受限撤销。"""

from __future__ import annotations

import os
import stat
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..storage import Store
from .paths import PathPolicy, ToolError, sensitive, _reparse


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
        if raw.is_absolute() or raw.drive or raw.anchor or raw.is_reserved() or any(part == ".." or ":" in part for part in raw.parts):
            raise ToolError("PATH_DENIED", "动作路径必须是授权根内相对路径")
        if any(sensitive(part) for part in raw.parts):
            raise ToolError("PATH_DENIED", "不允许操作应用内部或凭据目录")
        target = policy.root.joinpath(raw)
        policy._check_root()
        # 必须检查原始路径链；resolve 后再检查会抹掉链接/Windows 联接的信息。
        current = policy.root
        for part in raw.parts:
            current = current / part
            if current.exists() or current.is_symlink():
                if _reparse(current):
                    raise ToolError("PATH_DENIED", "动作路径不能经过链接或重解析点")
                if current != target and not current.is_dir():
                    raise ToolError("PATH_DENIED", "动作父路径必须是目录")
            elif current != target and (not planned_dirs or current.relative_to(policy.root).as_posix() not in planned_dirs):
                raise ToolError("PATH_UNAVAILABLE", "动作父目录不存在")
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

    @staticmethod
    def _revision(plan: dict) -> str:
        """摘要绑定完整计划及身份快照；磁盘计划变更不能借用旧审批。"""
        content = {key: value for key, value in plan.items() if key != "revision"}
        return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

    def _policy(self, operation: dict) -> PathPolicy:
        plan = operation["plan"]
        if not plan.get("revision") or plan["revision"] != self._revision(plan):
            raise ToolError("STALE_PLAN", "计划快照无效，请重新生成计划")
        if plan.get("root") != operation["root"] or plan.get("mission_id") != operation["mission_id"]:
            raise ToolError("STALE_PLAN", "计划所属任务或授权根已变化")
        root = Path(operation["root"])
        if not root.exists() or _reparse(root):
            raise ToolError("ROOT_CHANGED", "授权根已变化，请重新选择目录和生成计划")
        policy = PathPolicy(str(root))
        if self._identity(policy.root) != plan.get("root_identity"):
            raise ToolError("ROOT_CHANGED", "授权根身份已变化，请重新生成计划")
        return policy

    def _check_source(self, policy: PathPolicy, entry: dict) -> Path:
        source = self._relative(policy, entry["source"])
        source = policy.resolve(entry["source"], "file")
        if self._identity(source) != entry.get("source_identity"):
            raise ToolError("SOURCE_CHANGED", "源文件在计划生成后发生变化，请重新生成计划")
        return source

    async def create_plan(self, request: ActionPlanRequest) -> dict:
        policy = PathPolicy(request.root)
        normalized = []
        planned_dirs: set[str] = set()
        seen_sources: set[str] = set()
        seen_destinations: set[str] = set()
        for sequence, action in enumerate(request.actions):
            # 同一计划内冲突在审批之前拒绝，避免执行到一半才发现重复源/目标。
            destination_key = str(Path(action.destination)).casefold()
            source_key = str(Path(action.source)).casefold() if action.source else None
            if destination_key in seen_destinations or source_key and source_key in seen_sources:
                raise ToolError("CONFLICT", "计划包含重复源或重复目标，请重新规划")
            if action.kind == "mkdir":
                if action.source is not None:
                    raise ToolError("INVALID_PLAN", "mkdir 不能携带 source")
                destination = self._relative(policy, action.destination, allow_missing=True, planned_dirs=planned_dirs)
            else:
                if action.source is None:
                    raise ToolError("INVALID_PLAN", "文件动作必须携带 source")
                self._relative(policy, action.source)
                source = policy.resolve(action.source, "file")
                destination = self._relative(policy, action.destination, allow_missing=True, planned_dirs=planned_dirs)
                if source == destination:
                    raise ToolError("INVALID_PLAN", "源和目标不能相同")
                if source.stat().st_dev != policy.root.stat().st_dev:
                    raise ToolError("CROSS_VOLUME", "不允许跨卷文件动作")
            normalized.append({"sequence": sequence, "kind": action.kind, "source": action.source,
                               "destination": action.destination,
                               "source_identity": self._identity(source) if action.source else None})
            seen_destinations.add(destination_key)
            if source_key:
                seen_sources.add(source_key)
            if action.kind == "mkdir":
                planned_dirs.add(Path(action.destination).as_posix())
        operation_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        operation = {"id": operation_id, "mission_id": str(request.mission_id), "root": str(policy.root),
                     "status": "planned", "created_at": now,
                     "plan": {"actions": normalized, "root_identity": self._identity(policy.root),
                              "root": str(policy.root), "mission_id": str(request.mission_id)}}
        operation["plan"]["revision"] = self._revision(operation["plan"])
        await self.store.create_operation(operation)
        return {"operation_id": operation_id, "mission_id": str(request.mission_id), "status": "planned",
                "actions": normalized, "requires_approval": True, "revision": operation["plan"]["revision"]}

    async def approve(self, operation_id: str, revision: str | None = None) -> dict:
        operation = await self._require(operation_id)
        if operation["status"] != "planned":
            raise ToolError("INVALID_STATE", "只有 planned 计划可以审批")
        policy = self._policy(operation)
        if revision is not None and revision != operation["plan"]["revision"]:
            raise ToolError("STALE_PLAN", "审批版本已过期")
        for entry in operation["plan"]["actions"]:
            if entry["source"]:
                self._check_source(policy, entry)
        await self.store.update_operation(operation_id, "approved")
        return {"operation_id": operation_id, "status": "approved"}

    async def execute(self, operation_id: str) -> dict:
        operation = await self._require(operation_id)
        if operation["status"] != "approved":
            raise ToolError("APPROVAL_REQUIRED", "文件动作必须先获得用户审批")
        policy = self._policy(operation)
        await self.store.update_operation(operation_id, "running")
        completed = 0
        try:
            for entry in operation["plan"]["actions"]:
                sequence, kind = entry["sequence"], entry["kind"]
                persisted_entry = next(item for item in operation["entries"] if item["sequence"] == sequence)
                if persisted_entry["status"] == "completed":
                    destination = self._relative(policy, entry["destination"])
                    if not destination.exists() or self._identity(destination) != json.loads(persisted_entry["after_json"] or "null"):
                        raise ToolError("RECOVERY_CONFLICT", "已完成步骤的目标发生变化，停止恢复")
                    if entry["source"] and self._relative(policy, entry["source"]).exists():
                        raise ToolError("RECOVERY_CONFLICT", "已完成步骤的源位置重新出现文件，停止恢复")
                    completed += 1
                    continue
                planned_dirs = {x["destination"] for x in operation["plan"]["actions"] if x["kind"] == "mkdir"}
                destination = self._relative(policy, entry["destination"], allow_missing=True, planned_dirs=planned_dirs)
                before = None
                if kind == "mkdir":
                    destination.mkdir()
                    after = self._identity(destination)
                else:
                    source = self._check_source(policy, entry)
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
        verification = await self.verify(operation_id)
        if not verification["complete"]:
            await self.store.update_operation(operation_id, "failed", error="执行核验未通过")
            return {"operation_id": operation_id, "status": "failed", "completed": completed,
                    "error": "执行核验未通过", "needs_recovery_check": True}
        await self.store.update_operation(operation_id, "completed")
        return {"operation_id": operation_id, "status": "completed", "completed": completed,
                "verified": verification}

    async def resume(self, operation_id: str) -> dict:
        """恢复被连接中断标记的计划；已记账步骤跳过，未记账步骤重新核验后执行。"""
        operation = await self._require(operation_id)
        if operation["status"] != "interrupted":
            raise ToolError("INVALID_STATE", "只有 interrupted 计划可以恢复")
        policy = self._policy(operation)
        # 动作和 SQLite 无法形成跨系统事务；无法证明未执行的步骤绝不重放。
        for entry, persisted in zip(operation["plan"]["actions"], operation["entries"], strict=True):
            destination = self._relative(policy, entry["destination"], planned_dirs={x["destination"] for x in operation["plan"]["actions"] if x["kind"] == "mkdir"})
            if persisted["status"] == "completed":
                if not destination.exists() or self._identity(destination) != json.loads(persisted["after_json"] or "null"):
                    raise ToolError("RECOVERY_CONFLICT", "已完成步骤发生变化，无法安全恢复")
                if entry["source"] and self._relative(policy, entry["source"]).exists():
                    raise ToolError("RECOVERY_CONFLICT", "已完成步骤的源位置重新出现文件，无法安全恢复")
            else:
                if destination.exists():
                    raise ToolError("RECOVERY_CONFLICT", "动作可能已执行但未记账，拒绝自动重放")
                if entry["source"]:
                    self._check_source(policy, entry)
        await self.store.update_operation(operation_id, "approved")
        return await self.execute(operation_id)

    async def verify(self, operation_id: str) -> dict:
        operation = await self._require(operation_id)
        policy = self._policy(operation)
        checks = []
        for entry in operation["plan"]["actions"]:
            destination = self._relative(policy, entry["destination"], allow_missing=False)
            persisted = next(item for item in operation["entries"] if item["sequence"] == entry["sequence"])
            exists = (destination.exists() and persisted["status"] == "completed"
                      and self._identity(destination) == json.loads(persisted["after_json"] or "null"))
            source_exists = False
            if entry["source"]:
                source_exists = self._relative(policy, entry["source"]).exists()
            checks.append({"sequence": entry["sequence"], "destination_exists": exists,
                           "source_absent": not source_exists})
        return {"operation_id": operation_id, "complete": all(x["destination_exists"] and x["source_absent"] for x in checks), "checks": checks}

    async def undo_latest(self, mission_id: str) -> dict:
        """只允许该 Mission 最近一个已完成任务，且目标身份未被外部修改时反向移动。"""
        # Store 没有暴露任意 SQL；使用有限 ID 查询由调用方保留最近任务，M04 任务数受上限约束。
        # 当前实现由 get_latest_operation 查询，避免将撤销范围扩大到其他 Mission。
        operation = await self.store.get_latest_operation(mission_id)
        if operation is None or operation["status"] != "completed":
            raise ToolError("UNDO_UNAVAILABLE", "没有可安全撤销的最近文件变更任务")
        policy = self._policy(operation)
        undone = 0
        # 撤销开始即记录未完成状态，崩溃发生在逆向动作与记账之间时也不能显示 completed。
        await self.store.update_operation(operation["id"], "partially_undone")
        try:
            for entry in reversed(operation["entries"]):
                if entry["status"] != "completed":
                    continue
                destination = self._relative(policy, entry["destination"], allow_missing=False)
                after = json.loads(entry["after_json"]) if entry["after_json"] else None
                if not destination.exists() or self._identity(destination) != after:
                    raise ToolError("UNDO_CONFLICT", "目标在任务后发生变化，已停止撤销")
                if entry["kind"] == "mkdir":
                    destination.rmdir()
                else:
                    source = self._relative(policy, entry["source"], allow_missing=True)
                    os.rename(destination, source)
                await self.store.update_operation(operation["id"], "partially_undone", sequence=entry["sequence"], entry_status="undone",
                                                  before=json.loads(entry["before_json"] or "null"), after=after)
                undone += 1
        except (OSError, ToolError) as error:
            # 即使逆向动作中途失败，也不能把已经变化的文件系统继续显示为 completed。
            message = error.message if isinstance(error, ToolError) else "撤销文件动作失败，已停止"
            await self.store.update_operation(operation["id"], "partially_undone", error=message)
            raise ToolError("UNDO_CONFLICT", message) from None
        await self.store.update_operation(operation["id"], "undone")
        return {"operation_id": operation["id"], "status": "undone", "undone": undone}

    async def _require(self, operation_id: str) -> dict:
        operation = await self.store.get_operation(operation_id)
        if operation is None:
            raise ToolError("NOT_FOUND", "操作计划不存在")
        return operation
