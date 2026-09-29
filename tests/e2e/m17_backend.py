"""M17 E2E 只替换 Computer 云模型与当前用户目录定位；文件网关和 SQLite 真实运行。"""

import asyncio
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend/src"))
from orvia_backend.cleanup.service import CleanupService
from orvia_backend.configuration.client import Completion, ModelClient
from orvia_backend.server import serve


original_init = CleanupService.__init__


def synthetic_local_base(self, store, local_base=None):
    original_init(self, store, Path(os.environ["ORVIA_M17_LOCAL_BASE"]))


CleanupService.__init__ = synthetic_local_base


async def synthetic_complete(self, profile, messages, **kwargs):
    assert profile.role == "computer" and profile.model == "glm-5.3-flashx"
    payload = json.loads(messages[1]["content"])
    assert payload["requirement"] and kwargs["max_tokens"] == 4096
    if "原型提案器" in messages[0]["content"]:
        result = {"title": "合成原型", "pages": [
            {"id": "home", "title": "首页", "body": "演示数据", "buttons": [{"label": "详情", "target": "detail"}], "form": None},
            {"id": "detail", "title": "详情页", "body": "离线演示", "buttons": [{"label": "返回", "target": "home"}],
             "form": {"label": "姓名", "success": "演示已提交"}},
        ]}
    else:
        assert payload["stack"] == "react-vite" and payload["selected_context"][0]["path"] == "App.tsx"
        result = {"files": [{"path": "App.tsx", "content": "export const App = () => <p>new synthetic</p>;"}]}
    return Completion(json.dumps(result, ensure_ascii=False), (), "stop", {"total_tokens": 60})


ModelClient.complete = synthetic_complete
asyncio.run(serve(sys.stdin.buffer, sys.stdout.buffer))
