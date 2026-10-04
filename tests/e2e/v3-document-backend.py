"""V3-005 真实文档服务，局部缺页/OCR不可用仅在此测试入口注入。"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import m20_backend
import orvia_backend.chat as chat
from orvia_backend.documents.parser import failure

original = chat.extract_document


async def extract(data, suffix):
    if suffix == '.png':
        return failure(suffix, 'ocr_unavailable')
    result = await original(data, suffix)
    if suffix == '.pdf' and b'V3-PARTIAL' in data:
        result['total_units'] = 2
        result['missing_units'] = [2]
    return result


chat.extract_document = extract
asyncio.run(m20_backend.serve(sys.stdin.buffer, sys.stdout.buffer))
