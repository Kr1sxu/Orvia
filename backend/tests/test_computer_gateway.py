from pathlib import Path
from uuid import uuid4

import pytest

from orvia_backend.computer.contracts import GrantRequest, ToolRequest
from orvia_backend.computer.gateway import ComputerGateway
from orvia_backend.computer.paths import ToolError


def test_gateway_binds_mission_grant_and_role(tmp_path: Path):
    mission = uuid4()
    gateway = ComputerGateway()
    status = gateway.grant(GrantRequest(mission_id=mission, root=str(tmp_path), allow_text=True))
    request = ToolRequest.model_validate({"mission_id": str(mission), "grant_id": status["grant_id"],
                                         "call": {"tool": "list_directory", "arguments": {}}})
    result = gateway.execute("computer", request)
    assert result["tool"] == "list_directory"
    with pytest.raises(ToolError) as exc:
        gateway.execute("main", request)
    assert exc.value.code == "ROLE_DENIED"
    gateway.revoke(str(mission))
    with pytest.raises(ToolError) as exc:
        gateway.execute("computer", request)
    assert exc.value.code == "PERMISSION_DENIED"


def test_gateway_requires_text_permission(tmp_path: Path):
    mission = uuid4()
    gateway = ComputerGateway()
    status = gateway.grant(GrantRequest(mission_id=mission, root=str(tmp_path)))
    request = ToolRequest.model_validate({"mission_id": str(mission), "grant_id": status["grant_id"],
                                         "call": {"tool": "read_text_file", "arguments": {"path": "x.txt"}}})
    with pytest.raises(ToolError) as exc:
        gateway.execute("computer", request)
    assert exc.value.code == "PERMISSION_DENIED"
