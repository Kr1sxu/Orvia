"""将契约导出到仓库 contracts，便于桌面端核对 JSON 边界。"""

import json
from pathlib import Path

from . import Mission, MissionCreate, ModelProfile


def main() -> None:
    """开发期导出命令；不在后端服务运行期写入工程文件。"""
    destination = Path(__file__).resolve().parents[4] / "contracts" / "m02.schema.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    schema = {model.__name__: model.model_json_schema() for model in (ModelProfile, MissionCreate, Mission)}
    destination.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
