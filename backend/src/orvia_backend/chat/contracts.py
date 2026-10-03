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


class Continue(Cancel):
    """一次性接续原请求；文字只补必要信息，不包含批准或绝对路径。"""
    continuation_id: UUID
    answer: str | None = Field(default=None, min_length=1, max_length=2000)


class MaterialRemove(Conversation):
    kind: Literal["document", "browser"]
    evidence_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class ScanPage(Conversation):
    scan_id: UUID
    offset: int = Field(default=0, ge=0, le=5000, strict=True)


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
    stream_mode: Literal["stream", "confirmed_nonstream"] | None = None


class PublicationPreview(Conversation):
    """仅编辑已保存 M15 结果的文字；引用身份、来源与结论类型不可由 UI 改写。"""
    message_id: UUID
    format: Literal["docx", "pptx", "pdf"]
    title: str = Field(min_length=1, max_length=40)
    answer: str = Field(min_length=1, max_length=2200)
    claim_texts: list[str] = Field(min_length=1, max_length=8)


class PublicationSave(PublicationPreview):
    request_id: UUID
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    path: str = Field(min_length=1, max_length=1000)


class DevelopmentContext(Conversation):
    """仅预览显式选择的代码文件；目录 grant 不自动上传整个项目。"""
    requirement: str = Field(min_length=1, max_length=1200)
    paths: list[str] = Field(default_factory=list, max_length=3)
    sources: list[SynthesisSource] = Field(default_factory=list, max_length=2)
    result_message_id: UUID | None = None


class DevelopmentGenerate(DevelopmentContext):
    request_id: UUID
    kind: Literal["code", "prototype"]
    stack: Literal["react-vite", "web-native"]
    context_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class DevelopmentDraft(Conversation):
    draft_id: UUID


class DevelopmentApply(DevelopmentDraft):
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    index: int = Field(ge=0, le=11, strict=True)


class CleanupPlan(Conversation):
    plan_id: UUID


class CleanupExecute(CleanupPlan):
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    indices: list[int] = Field(min_length=1, max_length=50)


class CleanupRestore(CleanupPlan):
    index: int = Field(ge=0, le=49, strict=True)


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
