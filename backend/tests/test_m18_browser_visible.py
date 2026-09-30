"""产品干净环境中的可见Chromium验收；测试启动时须显式授权浏览器测试。"""

import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest


@pytest.mark.skipif(os.name != "nt" or os.environ.get("ORVIA_BROWSER_TEST") != "1", reason="Windows真实可见Chromium须显式启用")
def test_visible_chromium_in_product_clean_environment(tmp_path):
    # Chromium缓存及沙箱内SxS仍使用部分MAX_PATH API；真实产品Temp是短目录。
    # 保留长路径报告，原生运行目录放在同一忽略结果根的短随机子目录。
    native_temp = Path(__file__).resolve().parents[2] / "artifacts/test-results/M18" / ("v-" + uuid4().hex[:8])
    native_temp.mkdir()
    report = tmp_path / "visible-report.json"
    environment = {key: value for key, value in os.environ.items() if key.upper() in {"SYSTEMROOT", "WINDIR"}}
    environment.update(TEMP=str(native_temp), TMP=str(native_temp))
    arguments = [sys.executable, "-I", "-X", "utf8", str(Path(__file__).with_name("m18_browser_visible_probe.py")), str(report)]
    process = subprocess.run(arguments,
                             env=environment, cwd=str(Path(__file__).resolve().parents[2]), stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=55)
    assert report.exists(), "可见探针未形成固定诊断，禁止输出原始stderr"
    diagnostic = json.loads(report.read_text(encoding="utf-8"))
    assert process.returncode == 0, diagnostic
    assert diagnostic["clean_environment"] and diagnostic["headless"] is False and diagnostic["visible_window"]
    assert diagnostic["phase"] == "verified" and diagnostic["writes"] == 1
    assert diagnostic["chromium_sandbox"] is True
    assert diagnostic["renderer_tokens"] and diagnostic["owned_processes_reaped"]
