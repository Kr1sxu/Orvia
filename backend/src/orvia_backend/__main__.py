"""模块入口：二进制 stdio 保持 Windows 与其他平台的 UTF-8 协议一致。"""

import asyncio
import sys

from .server import serve


def main() -> None:
    """由 Electron 启动；不加载凭据、不访问用户文件，也不调用模型。"""
    try:
        asyncio.run(serve(sys.stdin.buffer, sys.stdout.buffer))
    except BrokenPipeError:
        # 父进程关闭响应管道即结束服务，不把输入或内部信息写入 stdout。
        print("Orvia 响应管道已关闭", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
