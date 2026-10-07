"""固定角色配置与仅驻留内存的模型凭据；不持久化密钥。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from orvia_backend.domain import ModelProfile, get_profiles


Role = Literal["main", "computer", "browser"]


class Credentials(BaseModel):
    """跨私有管道接收凭据；repr/JSON 默认隐藏内容，禁止通用日志记录。"""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    main: SecretStr | None = None
    computer: SecretStr | None = None
    browser: SecretStr | None = None
    tavily: SecretStr | None = None
    # Redis 独立凭据只供辅助连接使用，不参与三个角色的模型配置。
    redis: SecretStr | None = None

    @field_validator("main", "computer", "browser", "tavily", "redis")
    @classmethod
    def bounded_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            raw = value.get_secret_value()
            if not raw.strip() or len(raw) > 4096 or "\r" in raw or "\n" in raw:
                raise ValueError("凭据格式无效")
        return value


class ModelRegistry:
    """固定映射不接受 UI 覆盖；更新密钥不会改变任何 Mission 配置。"""

    def __init__(self, credentials: Credentials | None = None):
        self._credentials = credentials or Credentials()

    def replace_credentials(self, credentials: Credentials) -> None:
        self._credentials = credentials

    def status(self) -> dict:
        return {"profiles": [{**profile.model_dump(mode="json"), "configured": getattr(self._credentials, profile.role) is not None}
                             for profile in get_profiles()], "search_available": self._credentials.tavily is not None}

    def key_for(self, profile: ModelProfile) -> str:
        """只为当前固定且已校验的配置取得 Key；缺失就拒绝，不选择备用供应商。"""
        secret = getattr(self._credentials, profile.role)
        if secret is None:
            raise ValueError("MISSING_CREDENTIAL")
        return secret.get_secret_value()
