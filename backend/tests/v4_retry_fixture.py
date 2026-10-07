"""V4-011 Electron专用：真实合成TCP静态页，复用安全HTTP解析，固定Main仅测试替身。

只替换公开测试域的DNS/套接字去向及模型，真实RetryService、stdio、SQLite、
不可变证据和自然任务目标核验全部保留。该文件不在生产入口注册、不读取密钥。
"""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v4_research_fixture as base


if __name__ == "__main__":
    base.install(int(sys.argv[1]), sys.argv[2])
    # Application初始化会把实际持久RetryService注入browser.retry；不替换其策略或账本。
    from orvia_backend.server import serve
    asyncio.run(serve(sys.stdin.buffer, sys.stdout.buffer))
