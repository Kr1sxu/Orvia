"""调研私有协议：身份与审批来自主进程，来源正文不能扩大权限。"""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Conversation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    # JSON协议的UUID使用严格字符串再解析，拒绝布尔值或隐式数字转换。
    id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")

    def model_post_init(self, _context):
        self.id = str(UUID(self.id))


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    kind: Literal["browser", "document"]
    evidence_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class Create(Conversation):
    question: str = Field(min_length=1, max_length=500)
    urls: list[str] = Field(default_factory=list, max_length=10)
    queries: list[str] = Field(default_factory=list, max_length=2)
    sites: list[str] = Field(default_factory=list, max_length=5)
    sources: list[Source] = Field(default_factory=list, max_length=3)


class Operation(Conversation):
    operation_id: str = Field(pattern=r"^[0-9a-fA-F-]{36}$")

    def model_post_init(self, context):
        super().model_post_init(context)
        self.operation_id = str(UUID(self.operation_id))


class Preview(Operation):
    stage: Literal["batch", "final"] = "final"
    sources: list[Source] | None = Field(default=None, max_length=10)


class Generate(Operation):
    stage: Literal["batch", "final"]
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
