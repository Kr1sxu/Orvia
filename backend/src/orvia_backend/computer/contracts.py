"""M03 请求契约：固定工具、相对路径和程序控制的预算，不接受任意命令。"""

import json
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class GrantRequest(Params):
    """仅可信 Electron 授权流程使用，模型与 renderer 不能设置绝对根目录。"""
    mission_id: UUID
    root: str | None = None
    allow_text: bool = False
    allow_system: bool = False


class MissionRequest(Params):
    mission_id: UUID


class DirectoryArgs(Params):
    path: str = Field(default=".", max_length=1000)
    limit: int = Field(default=100, ge=1, le=100, strict=True)


class SearchArgs(DirectoryArgs):
    query: str = Field(min_length=1, max_length=100)
    extension: str | None = Field(default=None, max_length=20)
    recursive: bool = True


class PathArgs(Params):
    path: str = Field(min_length=1, max_length=1000)


class ReadArgs(PathArgs):
    start_line: int = Field(default=1, ge=1, le=10000, strict=True)
    max_lines: int = Field(default=100, ge=1, le=200, strict=True)
    max_chars: int = Field(default=8000, ge=1, le=8000, strict=True)


class SpaceArgs(Params):
    path: str = Field(default=".", max_length=1000)
    top_n: int = Field(default=10, ge=1, le=30, strict=True)
    min_size: int = Field(default=0, ge=0, le=2**53 - 1, strict=True)


class ProcessArgs(Params):
    name: str = Field(default="", max_length=100)
    limit: int = Field(default=50, ge=1, le=100, strict=True)


class TemplateArgs(Params):
    template_id: Literal["runtime_version"] = "runtime_version"
    runtime: Literal["powershell", "git_bash", "wsl"] = "powershell"


class DirectoryCall(Params):
    tool: Literal["list_directory"]
    arguments: DirectoryArgs


class SearchCall(Params):
    tool: Literal["search_files"]
    arguments: SearchArgs


class MetadataCall(Params):
    tool: Literal["get_file_metadata"]
    arguments: PathArgs


class ReadCall(Params):
    tool: Literal["read_text_file"]
    arguments: ReadArgs


class SpaceCall(Params):
    tool: Literal["analyze_directory_space"]
    arguments: SpaceArgs


class RuntimeCall(Params):
    tool: Literal["detect_runtimes"]
    arguments: Params


class ProcessCall(Params):
    tool: Literal["list_processes"]
    arguments: ProcessArgs


class TemplateCall(Params):
    tool: Literal["run_readonly_template"]
    arguments: TemplateArgs


Call = Annotated[DirectoryCall | SearchCall | MetadataCall | ReadCall | SpaceCall | RuntimeCall | ProcessCall | TemplateCall,
                 Field(discriminator="tool")]


class ToolRequest(Params):
    mission_id: UUID
    grant_id: UUID
    call: Call


if __name__ == "__main__":
    # Schema 只在显式开发命令生成；运行工具不会写项目源码。
    target = Path(__file__).resolve().parents[4] / "contracts/m03.schema.json"
    target.write_text(json.dumps(ToolRequest.model_json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
