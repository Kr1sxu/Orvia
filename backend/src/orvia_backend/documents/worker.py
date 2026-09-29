"""固定子进程入口；禁用凭据继承，仅接收有界 stdin 文档字节。"""

import json
import os
import sys
import threading
import time

import psutil

from .parser import MAX_BYTES, parse_document


def main():
    # 主进程意外关闭时，不让离线解析无限孤立运行；正常硬超时仍由父进程 kill/wait 执行。
    parent = psutil.Process(os.getppid())
    started = time.monotonic()

    def watchdog():
        while time.monotonic() - started < 45:
            if not parent.is_running():
                os._exit(124)
            time.sleep(0.25)
        os._exit(124)

    threading.Thread(target=watchdog, daemon=True).start()
    suffix = sys.argv[-1] if len(sys.argv) > 1 else ""
    data = sys.stdin.buffer.read(MAX_BYTES + 1)
    result = parse_document(data, suffix)
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
