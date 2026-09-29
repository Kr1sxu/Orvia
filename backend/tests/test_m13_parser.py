"""M13 使用合成文档验证离线 OCR、顺序、预算与解析隔离。"""

import asyncio
import json
from io import BytesIO
import zipfile

from PIL import Image, ImageDraw, ImageFont
import pytest

from orvia_backend.documents import parser


def office(entries):
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return output.getvalue()


def docx(texts):
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in texts)
    return office({"word/document.xml": '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + '</w:body></w:document>'})


def text_pdf():
    stream = b"BT /F1 24 Tf 50 120 Td (Synthetic M13 PDF) Tj ET"
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 500 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    output = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(output)
    output += b"xref\n0 6\n0000000000 65535 f \n"
    output += b"".join(f"{offset:010} 00000 n \n".encode() for offset in offsets[1:])
    return output + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode()


def test_text_pdf_real_parser():
    result = parser.parse_document(text_pdf(), ".pdf")
    assert result["error"] is None
    assert "Synthetic M13 PDF" in result["units"][0]["text"]
    assert result["units"][0]["method"] == "text"
    assert result["units"][0]["locator"] == "第 1 页"


@pytest.mark.parametrize("suffix", [".png", ".jpg", ".pdf"])
def test_real_offline_ocr_synthetic_image_and_scan(suffix):
    image = Image.new("RGB", (900, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.text((50, 60), "ORVIA TEST 2026", fill="black", font=ImageFont.truetype("arial.ttf", 60))
    output = BytesIO()
    image.save(output, format={".png": "PNG", ".jpg": "JPEG", ".pdf": "PDF"}[suffix])
    result = parser.parse_document(output.getvalue(), suffix)
    assert result["error"] is None, result
    assert "2026" in result["units"][0]["text"]
    assert result["units"][0]["method"] == "ocr"
    assert 0 <= result["units"][0]["confidence"] <= 1


def test_docx_paragraphs_and_unicode_budget():
    result = parser.parse_document(docx(["合成😀" * 3000, "未覆盖"]), ".docx")
    assert result["truncated"]
    assert result["total_units"] == 2
    assert sum(len(unit["text"]) for unit in result["units"]) == 8000
    assert result["units"][0]["locator"] == "段落 1"
    assert result["missing_units"] == [2]


def test_unit_limit_and_empty_unit():
    result = parser.parse_document(docx([""] + ["合成"] * 55), ".docx")
    assert len(result["units"]) == 50
    assert result["total_units"] == 56 and result["truncated"]
    assert result["missing_units"] == [1]
    assert result["units"][0]["error"]["code"] == "no_text"


def test_slide_order_from_presentation_not_filename():
    data = office({
        "ppt/presentation.xml": '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId r:id="r2"/><p:sldId r:id="r1"/></p:sldIdLst></p:presentation>',
        "ppt/_rels/presentation.xml.rels": '<Relationships><Relationship Id="r1" Target="slides/slide1.xml"/><Relationship Id="r2" Target="slides/slide2.xml"/></Relationships>',
        "ppt/slides/slide1.xml": '<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:t>SECOND</a:t></a:p>',
        "ppt/slides/slide2.xml": '<a:p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:t>FIRST</a:t></a:p>',
    })
    result = parser.parse_document(data, ".pptx")
    assert [unit["text"] for unit in result["units"]] == ["FIRST", "SECOND"]


@pytest.mark.parametrize("entries,code", [
    ({"word/vbaProject.bin": "macro"}, "active_content"),
    ({"[Content_Types].xml": "application/vnd.ms-word.document.macroEnabled.main+xml"}, "active_content"),
    ({"word/_rels/document.xml.rels": '<Relationships><Relationship TargetMode="External" Target="https://invalid.example"/></Relationships>'}, "external_relationship"),
    ({"../escape": "x"}, "invalid_archive"),
    ({"word/document.xml": '<!DOCTYPE x [<!ENTITY attack SYSTEM "file:///fake">]><x>&attack;</x>'}, "invalid_document"),
    ({"word/document.xml": "x" * (32 * 1024 * 1024 + 1)}, "archive_limit"),
])
def test_archive_security(entries, code):
    result = parser.parse_document(office(entries), ".docx")
    assert result["error"]["code"] == code
    assert result["units"] == []


def test_input_and_corruption_limits():
    assert parser.parse_document(b"x", ".exe")["error"]["code"] == "unsupported_format"
    assert parser.parse_document(b"x" * (parser.MAX_BYTES + 1), ".pdf")["error"]["code"] == "input_size_limit"
    for suffix in [".pdf", ".docx", ".pptx", ".jpg"]:
        assert parser.parse_document(b"corrupt private content", suffix)["error"]["code"] == "invalid_document"
    assert parser.parse_document(b"%PDF /Encrypt", ".pdf")["error"]["code"] == "encrypted_document"


def test_real_worker_protocol():
    result = asyncio.run(parser.extract_document(docx(["SYNTHETIC worker"]), ".docx"))
    assert result["units"][0]["text"] == "SYNTHETIC worker"


def test_worker_timeout_is_bounded(monkeypatch):
    monkeypatch.setattr(parser, "TIMEOUT_SECONDS", 0.001)
    result = asyncio.run(parser.extract_document(docx(["SYNTHETIC"]), ".docx"))
    assert result["error"]["code"] == "extraction_timeout"


def test_wire_byte_budget_for_escape_heavy_text(monkeypatch):
    monkeypatch.setattr(parser, "_office", lambda *_: ([parser._unit(i + 1, f"段落 {i + 1}", "\x01" * 160) for i in range(50)], 50))
    result = parser.parse_document(b"synthetic", ".docx")
    assert result["truncated"]
    assert len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= 44 * 1024


def test_worker_spawn_failure_is_safe(monkeypatch):
    async def fail(*args, **kwargs):
        raise OSError("private local path")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", fail)
    result = asyncio.run(parser.extract_document(docx(["synthetic"]), ".docx"))
    assert result["error"]["code"] == "worker_unavailable"
    assert "private" not in str(result)
