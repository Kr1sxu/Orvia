"""真实冻结解析入口验证；仅合成字节，默认跳过，不读取开发凭据。"""
import json
import os
from io import BytesIO
from pathlib import Path
import subprocess

import pytest
from PIL import Image, ImageDraw, ImageFont
from test_m13_parser import docx, text_pdf, office

EXE = os.environ.get('ORVIA_FROZEN_BACKEND')
pytestmark = pytest.mark.skipif(not EXE, reason='需显式指定本轮冻结后端')

@pytest.mark.parametrize('suffix', ['.pdf', '.docx', '.pptx', '.png'])
def test_frozen_worker(suffix):
    if suffix == '.pdf':
        data = text_pdf()
        expected = 'Synthetic'
    elif suffix == '.docx':
        data = docx(['Orvia synthetic license'])
        expected = 'license'
    elif suffix == '.pptx':
        data = office({'ppt/presentation.xml': '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst></p:presentation>', 'ppt/_rels/presentation.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="slides/slide1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"/></Relationships>', 'ppt/slides/slide1.xml': '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:t>Orvia synthetic slide</a:t></p:sld>'})
        expected = 'slide'
    else:
        image = Image.new('RGB', (900, 220), 'white')
        ImageDraw.Draw(image).text((40, 60), 'ORVIA TEST 2026', fill='black', font=ImageFont.truetype('arial.ttf', 60))
        out = BytesIO(); image.save(out, format='PNG'); data = out.getvalue()
        expected = '2026'
    env = {name: os.environ[name] for name in ('SystemRoot', 'WINDIR', 'TEMP', 'TMP') if name in os.environ}
    env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
    reply = subprocess.run([EXE, '--document-worker', suffix], input=data, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
    assert reply.returncode == 0, '冻结解析进程退出异常'
    result = json.loads(reply.stdout)
    assert result['error'] is None, result
    assert expected in result['units'][0]['text']
    assert result['units'][0]['method'] == ('ocr' if suffix == '.png' else 'text')
