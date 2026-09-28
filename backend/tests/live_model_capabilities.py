"""显式真实能力探测：仅发送合成工具定义，不执行工具，不输出原始响应。"""

import argparse
import asyncio
import json
from datetime import datetime, timezone

from live_model_preflight import ROOT, TARGETS, credentials
from orvia_backend.configuration import Credentials, ModelRegistry
from orvia_backend.configuration.client import ModelClient, ModelUnavailable
from orvia_backend.domain import get_profiles


async def run() -> int:
    values = credentials()
    missing = [role for role, _, _, name in TARGETS if not values.get(name)]
    if missing:
        print(json.dumps({"status": "blocked", "missing_roles": missing}))
        return 1
    registry = ModelRegistry(Credentials(**{role: values[name] for role, _, _, name in TARGETS}))
    client = ModelClient(registry)
    tool = {"type": "function", "function": {"name": "report_probe", "description": "Report the synthetic test status; no side effects.",
            "parameters": {"type": "object", "properties": {"status": {"type": "string", "enum": ["ok"]}}, "required": ["status"], "additionalProperties": False}}}
    report = {"time_utc": datetime.now(timezone.utc).isoformat(), "mock": False, "real_model": True,
              "max_requests": 3, "max_output_tokens_per_request": 512, "retries": 0, "results": []}
    blocked = False
    for profile in get_profiles():
        result = {"role": profile.role, "model": profile.model, "base_url": profile.base_url}
        if blocked:
            result.update(status="not_run", reason="STOPPED_AFTER_BLOCKER")
        else:
            try:
                completion = await client.complete(profile, [{"role": "user", "content": 'Call report_probe with {"status":"ok"}. Do not answer in text. This is a synthetic schema test.'}], max_tokens=512, tools=[tool])
                calls = completion.tool_calls
                valid = len(calls) == 1 and calls[0].get("type") == "function" and calls[0].get("function", {}).get("name") == "report_probe"
                if valid:
                    valid = json.loads(calls[0]["function"]["arguments"]) == {"status": "ok"}
                result.update(status="passed" if valid else "failed", structured_tool_call=valid, usage=completion.usage)
                if not valid:
                    result["reason"] = "TOOL_SCHEMA_NOT_SATISFIED"
            except ModelUnavailable as error:
                result.update(status="failed", reason=str(error))
            except (ValueError, KeyError, TypeError):
                result.update(status="failed", reason="INVALID_TOOL_ARGUMENTS")
            blocked = result["status"] != "passed"
        report["results"].append(result)
    destination = ROOT / "artifacts/test-results/M02/live-capabilities.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 1 if blocked else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true")
    if not parser.parse_args().run_live:
        parser.error("真实调用必须显式提供 --run-live")
    raise SystemExit(asyncio.run(run()))
