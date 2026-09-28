"""冻结入口：固定资源路径并保留控制台 stdio，Electron 负责隐藏子进程窗口。"""
import os
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # 不接受环境变量将发布浏览器/Node 换成用户机器上的其它程序。
    resources = Path(sys.executable).resolve().parent.parent
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(resources / 'chromium')
    for name in ('PLAYWRIGHT_NODEJS_PATH', 'NODE_OPTIONS', 'NODE_EXTRA_CA_CERTS'):
        os.environ.pop(name, None)
    os.environ['PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD'] = '1'

from orvia_backend.__main__ import main

if __name__ == '__main__':
    main()
