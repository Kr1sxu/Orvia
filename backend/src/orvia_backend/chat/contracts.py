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


class Cancel(Conversation):
    request_id: UUID


class Send(Cancel):
    text: str = Field(min_length=1, max_length=2000)


class Grant(Conversation):
    root: str = Field(min_length=1, max_length=1000)


ReadTool = Literal["list_directory", "search_files", "get_file_metadata", "analyze_directory_space"]


class Inspect(Conversation):
    tool: ReadTool
    arguments: dict


class BrowserSearch(Cancel):
    """会话内只读搜索；搜索结果由 Browser 校验 URL 后返回。"""
    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=5, strict=True)


class BrowserRead(Cancel):
    """会话内读取公开 URL，不接受脚本、Cookie 或上传参数。"""
    url: str = Field(min_length=1, max_length=2048)
    mode: Literal["auto", "http", "playwright"] = "auto"


class BrowserAsk(Cancel):
    query: str = Field(min_length=1, max_length=200)


class BrowserSource(Conversation):
    evidence_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class DocumentAttach(Cancel):
    """绝对文件路径仅由主进程原生选择器提供，不向 renderer 开放。"""
    path: str = Field(min_length=1, max_length=1000)


class DocumentPreview(BrowserSource):
    format: Literal["md", "json"]


class DocumentExport(DocumentPreview):
    """用户预览确定的内容版本与保存框确定的新路径缺一不可。"""
    request_id: UUID
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: str = Field(min_length=1, max_length=1000)


class SynthesisSource(Params):
    kind: Literal["document", "browser"]
    evidence_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class SynthesisPreview(Conversation):
    mode: Literal["summary", "answer"]
    question: str = Field(min_length=1, max_length=300)
    sources: list[SynthesisSource] = Field(min_length=1, max_length=3)


class SynthesisGenerate(SynthesisPreview):
    request_id: UUID
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")


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
