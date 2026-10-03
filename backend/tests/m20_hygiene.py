"""M20实际index与产物卫生检查；复用原固定资源/hash规则，不重跑M19功能验收。"""

import argparse
import os
from pathlib import Path

import m19_hygiene as common


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--working", action="store_true", help="只读工作树，不能代替实际暂存验收")
    # 仅变更本轮忽略产物范围；原件许可/图标白名单和index字节审计原样复用。
    result = common.ROOT / "artifacts/test-results/M20"
    # 保留中间包的嵌套Chromium路径可能超过MAX_PATH；显式长路径扫描，不能跳过缺读文件。
    common.RESULT = Path("\\\\?\\" + str(result)) if os.name == "nt" else result
    raise SystemExit(common.main(parser.parse_args().working))
