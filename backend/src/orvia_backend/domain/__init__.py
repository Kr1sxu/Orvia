"""M02 数据契约：只保存任务草稿与三个角色的不可变配置快照。"""

from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal["main", "computer", "browser"]
FIXED_PROFILES = (
    ("main", "deepseek", "deepseek-flash", "https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    ("computer", "zhipu", "glm-5.3-flashx", "https://open.bigmodel.cn/api/paas/v4", "ZHIPU_API_KEY"),
    ("browser", "mimo", "mimo-v2.6-flash", "https://api.xiaomimimo.com/v1", "MIMO_API_KEY"),
)


class Contract(BaseModel):
    """拒绝未声明字段；构造后禁止赋值，避免配置快照被意外改写。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelProfile(Contract):
    """模型配置只含凭据引用，绝不包含凭据值。"""

    model_config = ConfigDict(json_schema_extra={
        "oneOf": [
            {"properties": {field: {"const": value} for field, value in zip(
                ("role", "provider", "model", "base_url", "credential_ref"), profile
            )}}
            for profile in FIXED_PROFILES
        ]
    })

    role: Role
    provider: str
    model: str
    base_url: str
    credential_ref: str
    revision: Annotated[int, Field(strict=True, ge=1, le=1)] = 1

    @model_validator(mode="after")
    def fixed_mapping(self) -> Self:
        """固定角色映射不提供自动纠错或供应商回退。"""
        expected = next(profile for profile in FIXED_PROFILES if profile[0] == self.role)
        if (self.role, self.provider, self.model, self.base_url, self.credential_ref) != expected:
            raise ValueError("model profile does not match fixed role mapping")
        return self


def get_profiles() -> tuple[ModelProfile, ...]:
    """返回每个 Mission 应固化的三个角色配置，不解析任何凭据。"""
    fields = ("role", "provider", "model", "base_url", "credential_ref")
    return tuple(ModelProfile(**dict(zip(fields, profile))) for profile in FIXED_PROFILES)


class MissionCreate(Contract):
    """使用客户端请求标识保证重试不会重复创建草稿。"""

    client_request_id: UUID
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title", mode="before")
    @classmethod
    def trim_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class Mission(MissionCreate):
    """M02 仅有 draft 状态；真实执行状态由后续模块引入。"""

    id: UUID
    status: Literal["draft"]
    created_at: AwareDatetime
    models: tuple[ModelProfile, ...] = Field(
        min_length=3, max_length=3,
        json_schema_extra={
            # 逐角色计数避免省略默认 revision 时绕过 uniqueItems。
            "allOf": [
                {"contains": {"type": "object", "properties": {"role": {"const": role}}, "required": ["role"]},
                 "minContains": 1, "maxContains": 1}
                for role in ("main", "computer", "browser")
            ]
        },
    )

    @field_validator("models")
    @classmethod
    def all_roles(cls, models: tuple[ModelProfile, ...]) -> tuple[ModelProfile, ...]:
        if {profile.role for profile in models} != {"main", "computer", "browser"}:
            raise ValueError("mission requires exactly one profile for each role")
        return models
