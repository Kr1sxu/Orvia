"""M02 显式真实模型预检：仅合成文本、固定配置、零重试，不输出凭据或原始响应。"""

import argparse
import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


ROOT = Path(__file__).resolve().parents[2]
TARGETS = (
    ("main", "deepseek-flash", "https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    ("computer", "glm-5.3-flashx", "https://open.bigmodel.cn/api/paas/v4", "ZHIPU_API_KEY"),
    ("browser", "mimo-v2.6-flash", "https://api.xiaomimimo.com/v1", "MIMO_API_KEY"),
)


class NoRedirect(HTTPRedirectHandler):
    """拒绝跳转，防止认证头离开用户指定的固定服务地址。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def credentials() -> dict[str, str]:
    """只在本进程内读取开发密钥；不继承其他文件或猜测缺失值。"""
    path = ROOT / ".env.local"
    values: dict[str, str] = {}
    if path.exists():
        allowed = {target[3] for target in TARGETS}
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.partition("=")
            name = name.strip()
            if separator and name in allowed:
                values[name] = value.strip().strip('"').strip("'")
    return values


def probe(model: str, base_url: str, key: str, max_tokens: int) -> dict:
    """单次非流式请求，有界输出、20 秒 socket 超时，无自动重试。"""
    payload = {"model": model, "messages": [{"role": "user", "content": "Reply with exactly OK. This is a synthetic connectivity test."}],
               "max_tokens": max_tokens, "stream": False}
    request = Request(base_url + "/chat/completions", data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json", "Authorization": "Bearer " + key}, method="POST")
    started = time.monotonic()
    try:
        with build_opener(NoRedirect()).open(request, timeout=20) as response:
            data = response.read(65537)
            if len(data) > 65536:
                result = {"status": "failed", "reason": "RESPONSE_TOO_LARGE"}
            else:
                body = json.loads(data)
                choices = body.get("choices")
                content = choices[0].get("message", {}).get("content") if isinstance(choices, list) and choices else None
                result = {"status": "passed" if isinstance(content, str) and content.strip() else "failed",
                          "http_status": response.status, "text_present": bool(content)}
                if isinstance(choices, list) and choices:
                    reason = choices[0].get("finish_reason")
                    result["finish_reason"] = reason if reason in ("stop", "length", "tool_calls", "content_filter") else "other"
                    result["reasoning_present"] = bool(choices[0].get("message", {}).get("reasoning_content"))
                usage = body.get("usage", {})
                result["usage"] = {name: usage[name] for name in ("prompt_tokens", "completion_tokens", "total_tokens")
                                   if isinstance(usage.get(name), int)}
                if not content:
                    result["reason"] = "NO_TEXT_RESPONSE"
    except HTTPError as error:
        # 服务错误正文可能包含敏感回显，只用于分类，不写入日志或报告。
        raw = error.read(65536).decode("utf-8", errors="replace").lower()
        reason = "HTTP_ERROR"
        if error.code in (401, 403):
            reason = "AUTH_OR_ACCESS_DENIED"
        elif "model" in raw and any(word in raw for word in ("not exist", "not found", "invalid model", "不存在")):
            reason = "MODEL_UNAVAILABLE"
        result = {"status": "failed", "http_status": error.code, "reason": reason}
    except (URLError, TimeoutError, socket.timeout):
        result = {"status": "failed", "reason": "NETWORK_OR_TIMEOUT"}
    except (ValueError, KeyError, TypeError, AttributeError):
        result = {"status": "failed", "reason": "INVALID_RESPONSE"}
    result["elapsed_seconds"] = round(time.monotonic() - started, 2)
    return result


def main() -> int:
    """必须显式启用真实调用；任一角色失败后停止，不换配置或继续付费请求。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true")
    parser.add_argument("--role", action="append", choices=[target[0] for target in TARGETS])
    parser.add_argument("--max-tokens", type=int, choices=(64, 256), default=64)
    args = parser.parse_args()
    if not args.run_live:
        parser.error("真实调用必须显式提供 --run-live")
    values = credentials()
    targets = [target for target in TARGETS if not args.role or target[0] in args.role]
    report = {"time_utc": datetime.now(timezone.utc).isoformat(), "mock": False, "real_model": True,
              "max_requests": len(targets), "max_output_tokens_per_request": args.max_tokens, "retries": 0, "results": []}
    blocked = any(not values.get(target[3]) for target in TARGETS)
    for role, model, url, variable in targets:
        result = {"role": role, "model": model, "base_url": url}
        if not values.get(variable):
            result.update(status="failed", reason="MISSING_CREDENTIAL")
        elif blocked:
            result.update(status="not_run", reason="STOPPED_AFTER_BLOCKER")
        else:
            result.update(probe(model, url, values[variable], args.max_tokens))
        report["results"].append(result)
        blocked = blocked or result["status"] != "passed"
    target = ROOT / "artifacts/test-results/M02/live-preflight.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
