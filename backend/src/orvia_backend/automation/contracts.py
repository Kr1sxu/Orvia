"""M18 私有协议白名单：路径字段仅供主进程原生选择器注入。"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

RelativeInput = Annotated[str, Field(min_length=1, max_length=240)]


class Conversation(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    id: UUID


class ScriptPreview(Conversation):
    source: str = Field(min_length=1, max_length=32768)
    inputs: list[RelativeInput] = Field(default_factory=list, max_length=8)

    @field_validator("source")
    @classmethod
    def source_budget(cls, value):
        if len(value.encode("utf-8")) > 32768 or "\x00" in value:
            raise ValueError("脚本超过 UTF-8 字节预算")
        return value


class ScriptFile(Conversation):
    path: str = Field(min_length=1, max_length=1000)
    inputs: list[RelativeInput] = Field(default_factory=list, max_length=8)


class ModelPreview(Conversation):
    requirement: str = Field(min_length=1, max_length=1000)


class ModelGenerate(ModelPreview):
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_id: UUID


class Operation(Conversation):
    operation_id: UUID


class Approval(Operation):
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class Export(Approval):
    index: int = Field(ge=0, lt=12, strict=True)
    path: str = Field(min_length=1, max_length=1000)


class DesktopGrant(Conversation):
    target_id: str = Field(min_length=1, max_length=160)


class DesktopObserve(Conversation):
    grant_id: str = Field(min_length=1, max_length=160)


Category = Literal["local", "form", "message", "upload", "delete", "transaction"]


class DesktopPreview(DesktopObserve):
    control_id: str = Field(min_length=1, max_length=160)
    action: Literal["invoke", "set_value", "select", "toggle", "focus", "save_new"]
    value: str = Field(default="", max_length=2048)
    state_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    category: Category = "local"
    expectation: str = Field(min_length=1, max_length=300)


class DesktopExecute(Approval):
    selected_path: str | None = Field(default=None, max_length=1000)


class BrowserOpen(Conversation):
    url: str = Field(min_length=1, max_length=2048)
    allowed_actions: list[Literal["form", "message", "upload", "delete", "transaction"]] = Field(min_length=1, max_length=5)
    get_write_paths: list[str] = Field(default_factory=list, max_length=10)


class BrowserSession(Conversation):
    session_id: str = Field(min_length=1, max_length=160)


class BrowserPreview(BrowserSession):
    control_id: str = Field(min_length=1, max_length=160)
    action: Literal["fill", "select", "check", "click", "upload"]
    value: str = Field(default="", max_length=4000)
    state_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    category: Literal["form", "message", "upload", "delete", "transaction"]
    expectation: str = Field(min_length=1, max_length=300)


class BrowserExecute(Approval):
    selected_path: str | None = Field(default=None, max_length=1000)


class BrowserRequest(BrowserSession):
    request_id: str = Field(min_length=1, max_length=160)
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    approved: StrictBool


class BrowserOrigin(BrowserSession):
    url: str = Field(min_length=1, max_length=2048)


CONTRACTS = {
    "script.preview": ScriptPreview, "script.file": ScriptFile,
    "script.model_preview": ModelPreview, "script.model_generate": ModelGenerate,
    "script.execute": Approval, "script.status": Operation, "script.export": Export,
    "desktop.windows": Conversation, "desktop.grant": DesktopGrant, "desktop.observe": DesktopObserve,
    "desktop.preview": DesktopPreview, "desktop.execute": DesktopExecute,
    "browser.open": BrowserOpen, "browser.observe": BrowserSession, "browser.pending": BrowserSession,
    "browser.preview": BrowserPreview, "browser.execute": BrowserExecute,
    "browser.request": BrowserRequest, "browser.origin": BrowserOrigin, "browser.close": BrowserSession,
    "cancel": Approval, "history": Conversation,
}
