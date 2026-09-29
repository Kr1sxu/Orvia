"""显式 --run-live 才调用固定 Computer；只发送本脚本创建的合成项目。"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from orvia_backend.application import Application


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "artifacts/test-results/M17"


def development_key():
    path = ROOT / ".env.local"
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip().startswith("ZHIPU_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"\'')
    return ""


async def call(app, method, params=None):
    return await app.handle(json.dumps({"v": 1, "id": str(uuid4()), "method": method, "params": params or {}}).encode())


async def run():
    key = development_key()
    if not key:
        print("M17 live: MISSING_CREDENTIAL; calls=0")
        return 2
    RESULTS.mkdir(parents=True, exist_ok=True)
    report = {"model": "glm-5.3-flashx", "base_url": "https://open.bigmodel.cn/api/paas/v4",
              "synthetic_only": True, "calls": 0, "cases": []}
    with TemporaryDirectory(prefix="live-", dir=RESULTS) as directory:
        app = Application()
        try:
            await call(app, "hello")
            initialized = await call(app, "initialize", {"data_directory": directory,
                "credentials": {"computer": key}})
            if not initialized["ok"]:
                print("M17 live: INIT_FAILED; calls=0")
                return 2
            project = Path(directory) / "synthetic-project"
            project.mkdir()
            (project / "App.tsx").write_text("export const label = 'synthetic';\n", encoding="utf-8")
            cid = (await call(app, "chat.create", {"client_request_id": str(uuid4()),
                "title": "M17 synthetic live"}))["result"]["id"]
            await call(app, "chat.grant", {"id": cid, "root": str(project)})
            cases = [
                ("code", "react-vite", "将合成 React 标签改为 'demo'。只修改 App.tsx，不增加依赖。", ["App.tsx"]),
                ("prototype", "web-native", "制作两页合成活动登记网页原型，首页可跳转表单页；反馈必须标注演示。", []),
            ]
            for kind, stack, requirement, paths in cases:
                base = {"id": cid, "requirement": requirement, "paths": paths,
                        "sources": [], "result_message_id": None}
                preview = await call(app, "chat.development.context", base)
                if not preview["ok"]:
                    report["cases"].append({"kind": kind, "status": "PREVIEW_FAILED", "code": preview["error"]["code"]})
                    break
                report["calls"] += 1
                result = await call(app, "chat.development.generate", {**base, "kind": kind, "stack": stack,
                    "context_revision": preview["result"]["revision"], "request_id": str(uuid4())})
                if not result["ok"]:
                    report["cases"].append({"kind": kind, "status": "FAILED", "code": result["error"]["code"]})
                    break
                draft = result["result"]
                report["cases"].append({"kind": kind, "status": "PASS", "files": len(draft["files"]),
                    "prototype_pages": len(draft["prototype"]["pages"]) if kind == "prototype" else None,
                    "writes": 0})
            report["pass"] = len(report["cases"]) == 2 and all(case["status"] == "PASS" for case in report["cases"])
        finally:
            await app.close()
    (RESULTS / "live-development.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("M17 live: " + ("PASS" if report["pass"] else "FAILED") + f" calls={report['calls']} cases=" +
          ",".join(case["kind"] + ":" + case["status"] for case in report["cases"]))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-live", action="store_true")
    if not parser.parse_args().run_live:
        print("M17 live: skipped (requires --run-live)")
        sys.exit(0)
    sys.exit(asyncio.run(run()))
