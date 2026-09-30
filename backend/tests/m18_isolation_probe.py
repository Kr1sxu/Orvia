"""显式合成 LPAC 子进程探针，只允许 M18 忽略产物目录中的固定任务。"""

import argparse
import asyncio
import json
from pathlib import Path
import threading

from orvia_backend.automation.windows_isolation import IsolationError, run_script


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--report")
    request = parser.parse_args()
    allowed = Path(__file__).resolve().parents[2] / "artifacts/test-results/M18"
    paths = [Path(request.runtime).resolve(strict=True), Path(request.task).resolve(strict=True)]
    if request.report:
        paths.append(Path(request.report).resolve())
    for path in paths:
        if not path.is_relative_to(allowed.resolve()):
            parser.error("探针仅允许 M18 合成产物目录")
    try:
        async def execute():
            # 产品经 asyncio worker 执行 Native 适配；探针保持同样线程边界。
            return await asyncio.to_thread(run_script, paths[0], paths[1], cancel_event=threading.Event())
        value = asyncio.run(execute())
        report = {key: value[key] for key in ("status", "exit_code", "token_verified", "processes_reaped", "isolation")}
        report.update({"stdout_bytes": len(value["stdout"].encode()), "stderr_bytes": len(value["stderr"].encode())})
    except IsolationError as error:
        # 仅固定代码、阶段与错误编号；从不输出请求、脚本、凭据或原始异常。
        report = {"status": "unavailable", "code": error.code, "message": error.message}
    if request.report:
        paths[2].write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
