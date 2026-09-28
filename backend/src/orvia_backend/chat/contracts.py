"""M10 私有会话协议：固定能力白名单，模型提案与用户审批分离。"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..computer.actions import Action


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Create(Params):
    client_request_id: UUID
    title: str = Field(min_length=1, max_length=100)


class Conversation(Params):
    id: UUID


class Send(Conversation):
    request_id: UUID
    text: str = Field(min_length=1, max_length=2000)


class Grant(Conversation):
    root: str = Field(min_length=1, max_length=1000)


ReadTool = Literal["list_directory", "search_files", "get_file_metadata", "analyze_directory_space"]


class Inspect(Conversation):
    tool: ReadTool
    arguments: dict


class Approval(Conversation):
    operation_id: UUID
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class Proposal(Params):
    """模型只返回意图；参数仍由 M03 / M04 契约与权限网关再次检查。"""
    kind: Literal["answer", "inspect", "plan"]
    text: str = Field(default="", max_length=2000)
    tool: ReadTool | None = None
    arguments: dict | None = None
    actions: list[Action] | None = Field(default=None, min_length=1, max_length=20)
