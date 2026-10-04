"""V3-005 识别依赖缺失使用固定原因，不泄露模块路径；真实模型零调用。"""
import builtins
from io import BytesIO
from PIL import Image
from orvia_backend.documents import parser


def test_missing_ocr_dependency_has_actionable_reason(monkeypatch):
    original = builtins.__import__
    def missing(name, *args, **kwargs):
        if name == 'rapidocr_onnxruntime':
            raise ModuleNotFoundError('synthetic-private-path')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', missing)
    data = BytesIO()
    Image.new('RGB', (20, 20)).save(data, 'PNG')
    result = parser.parse_document(data.getvalue(), '.png')
    assert result['error']['code'] == 'ocr_unavailable'
    assert 'synthetic-private-path' not in str(result)
