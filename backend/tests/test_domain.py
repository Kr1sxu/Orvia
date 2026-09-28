"""契约目标测试全部使用合成输入，不需要模型凭据。"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orvia_backend.domain import Mission, MissionCreate, ModelProfile, get_profiles


def mission_values():
    return dict(id=uuid4(), client_request_id=uuid4(), title="合成草稿", status="draft", created_at=datetime.now(timezone.utc), models=get_profiles())


def test_fixed_profiles_and_immutable_snapshots():
    mission = Mission(**mission_values())
    assert [profile.role for profile in mission.models] == ["main", "computer", "browser"]
    with pytest.raises(ValidationError):
        mission.models[0].model = "replacement"
    with pytest.raises(ValidationError):
        mission.title = "replacement"
    assert Mission.model_validate_json(mission.model_dump_json()) == mission


@pytest.mark.parametrize("field,value", [("provider", "other"), ("model", "other"), ("base_url", "https://example.invalid"), ("credential_ref", "OTHER_KEY"), ("revision", 2), ("revision", True), ("revision", "1")])
def test_profile_rejects_changed_mapping(field, value):
    values = get_profiles()[0].model_dump()
    values[field] = value
    with pytest.raises(ValidationError):
        ModelProfile(**values)


@pytest.mark.parametrize("title", ["", "   ", "x" * 201, None])
def test_invalid_titles(title):
    with pytest.raises(ValidationError):
        MissionCreate(client_request_id=uuid4(), title=title)


def test_create_normalizes_and_forbids_extra():
    assert MissionCreate(client_request_id=uuid4(), title="  草稿 \n").title == "草稿"
    with pytest.raises(ValidationError):
        MissionCreate(client_request_id=uuid4(), title="草稿", path="outside")


def test_mission_requires_three_distinct_roles_and_timezone():
    values = mission_values()
    values["models"] = (get_profiles()[0],) * 3
    with pytest.raises(ValidationError):
        Mission(**values)
    values = mission_values()
    values["created_at"] = datetime(2026, 1, 1)
    with pytest.raises(ValidationError):
        Mission(**values)


def test_exported_schema_keeps_fixed_mapping_and_role_counts():
    schema = ModelProfile.model_json_schema()
    assert len(schema["oneOf"]) == 3
    assert schema["oneOf"][0]["properties"]["model"] == {"const": "deepseek-flash"}
    counts = Mission.model_json_schema()["properties"]["models"]["allOf"]
    assert {rule["contains"]["properties"]["role"]["const"] for rule in counts} == {"main", "computer", "browser"}
    assert all(rule["minContains"] == rule["maxContains"] == 1 for rule in counts)
