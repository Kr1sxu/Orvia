"""有界离线文档提取；内容只作为证据，不解释为命令或授权。"""

import asyncio
from contextlib import closing
from io import BytesIO
import json
import os
from pathlib import Path
import posixpath
import subprocess
import sys
import zipfile

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from PIL.Image import DecompressionBombError
from pypdfium2 import PdfiumError

MAX_BYTES = 10 * 1024 * 1024
MAX_TEXT = 8000
MAX_UNITS = 50
MAX_STDOUT = 256 * 1024
TIMEOUT_SECONDS = 45
SUPPORTED = {".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg"}


class DocumentError(Exception):
    """仅允许固定错误码离开解析边界，避免路径或原始内容泄漏。"""

    def __init__(self, code: str):
        self.code = code


def failure(suffix: str, code: str) -> dict:
    return {"format": suffix.lstrip("."), "units": [], "total_units": 0,
            "truncated": False, "missing_units": [],
            "error": {"code": code, "message": "文档未能安全提取，请检查格式、大小或稍后重试。"}}


def _unit(number: int, locator: str, text: str, method="text", confidence=None, error=None):
    return {"number": number, "locator": locator, "text": text,
            "method": method, "confidence": confidence, "error": error}


def _ocr(image):
    # 模型来自已安装 wheel；明确指定本地模型路径，不访问模型下载服务。
    import rapidocr_onnxruntime
    from rapidocr_onnxruntime import RapidOCR
    models = Path(rapidocr_onnxruntime.__file__).parent / "models"
    engine = RapidOCR(
        det_model_path=str(models / "ch_PP-OCRv4_det_infer.onnx"),
        rec_model_path=str(models / "ch_PP-OCRv4_rec_infer.onnx"),
        cls_model_path=str(models / "ch_ppocr_mobile_v2.0_cls_infer.onnx"),
        intra_op_num_threads=1, inter_op_num_threads=1,
    )
    import numpy as np
    result, _ = engine(np.array(image.convert("RGB"))[:, :, ::-1])
    if not result:
        return "", None
    return "\n".join(item[1] for item in result), sum(float(item[2]) for item in result) / len(result)


def _image(data: bytes):
    from PIL import Image, ImageOps
    with Image.open(BytesIO(data)) as source:
        if source.width * source.height > 16_000_000:
            raise DocumentError("image_pixel_limit")
        source.load()
        image = ImageOps.exif_transpose(source)
        image.thumbnail((2400, 2400))
        text, score = _ocr(image)
    return [_unit(1, "图像 1", text, "ocr", score)], 1


def _pdf(data: bytes):
    import pypdfium2 as pdfium
    # 加密内容不尝试口令、解密或权限绕过。
    if b"/Encrypt" in data:
        raise DocumentError("encrypted_document")
    units = []
    budget = MAX_TEXT
    with closing(pdfium.PdfDocument(data)) as pdf:
        total = len(pdf)
        for index in range(min(total, MAX_UNITS)):
            if budget <= 0:
                break
            with closing(pdf[index]) as page:
                with closing(page.get_textpage()) as textpage:
                    text = textpage.get_text_range(count=min(textpage.count_chars(), budget + 1)).strip()
                method, score = "text", None
                if not text:
                    width, height = page.get_size()
                    if width <= 0 or height <= 0:
                        raise DocumentError("invalid_page")
                    scale = min(2.0, 2400 / max(width, height))
                    bitmap = page.render(scale=scale)
                    try:
                        text, score = _ocr(bitmap.to_pil())
                    finally:
                        bitmap.close()
                    method = "ocr"
                units.append(_unit(index + 1, f"第 {index + 1} 页", text, method, score))
                budget -= len(text)
    return units, total


def _office(data: bytes, suffix: str):
    with zipfile.ZipFile(BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 4096 or sum(item.file_size for item in entries) > 32 * 1024 * 1024:
            raise DocumentError("archive_limit")
        if len({item.filename for item in entries}) != len(entries):
            raise DocumentError("invalid_archive")
        for item in entries:
            name = item.filename.lower()
            if item.flag_bits & 1:
                raise DocumentError("encrypted_document")
            if "vbaproject" in name or name.endswith(".bin"):
                raise DocumentError("active_content")
            if name == "[content_types].xml" and b"macroenabled" in archive.read(item).lower():
                raise DocumentError("active_content")
            if name.startswith("/") or ".." in name.split("/") or "\\" in name:
                raise DocumentError("invalid_archive")
            if name.endswith(".rels"):
                root = ET.fromstring(archive.read(item))
                if any(rel.get("TargetMode", "").lower() == "external" for rel in root):
                    raise DocumentError("external_relationship")
        if suffix == ".docx":
            root = ET.fromstring(archive.read("word/document.xml"))
            ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            paragraphs = list(root.iter(ns + "p"))
            units = [_unit(i + 1, f"段落 {i + 1}", "".join(node.text or "" for node in paragraph.iter(ns + "t")))
                     for i, paragraph in enumerate(paragraphs[:MAX_UNITS])]
            return units, len(paragraphs)
        root = ET.fromstring(archive.read("ppt/presentation.xml"))
        rels = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target", "") for rel in rels}
        pns = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
        rns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
        ans = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        slides = list(root.iter(pns + "sldId"))
        units = []
        for i, slide in enumerate(slides[:MAX_UNITS]):
            target = targets.get(slide.get(rns + "id"), "")
            name = posixpath.normpath(posixpath.join("ppt", target))
            if not name.startswith("ppt/slides/") or not name.endswith(".xml"):
                raise DocumentError("invalid_slide_reference")
            content = ET.fromstring(archive.read(name))
            text = "\n".join(node.text or "" for node in content.iter(ans + "t"))
            units.append(_unit(i + 1, f"第 {i + 1} 张幻灯片", text))
        return units, len(slides)


def parse_document(data: bytes, suffix: str) -> dict:
    """解析已由网关授权读取的字节；不会打开来自文档的路径或 URL。"""
    suffix = suffix.lower()
    if suffix not in SUPPORTED:
        return failure(suffix, "unsupported_format")
    if not data or len(data) > MAX_BYTES:
        return failure(suffix, "input_size_limit")
    try:
        if suffix == ".pdf":
            units, total = _pdf(data)
        elif suffix in {".docx", ".pptx"}:
            units, total = _office(data, suffix)
        else:
            units, total = _image(data)
        budget = MAX_TEXT
        kept = []
        truncated = total > len(units)
        for unit in units:
            if budget <= 0:
                truncated = True
                break
            text = unit["text"].replace("\x00", "")
            if len(text) > budget:
                truncated = True
            unit["text"] = text[:budget]
            budget -= len(unit["text"])
            if not text:
                unit["error"] = {"code": "no_text", "message": "此单元未识别出文字。"}
            kept.append(unit)
        present = {unit["number"] for unit in kept if unit["text"]}
        # 超大页数时避免响应按声明页数无界增长；被省略尾部由 total_units/truncated 表示。
        missing = [i for i in range(1, min(total, MAX_UNITS) + 1) if i not in present]
        result = {"format": suffix.lstrip("."), "units": kept, "total_units": total,
                  "truncated": truncated, "missing_units": missing, "error": None}
        # 控制 JSON 转义后的实际字节数，避免控制字符或四字节 Unicode 突破 stdio 帧预算。
        for unit in reversed(kept):
            if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= 43 * 1024:
                break
            result["truncated"] = True
            original = unit["text"]
            low, high = 0, len(original)
            while low < high:
                middle = (low + high + 1) // 2
                unit["text"] = original[:middle]
                if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= 43 * 1024:
                    low = middle
                else:
                    high = middle - 1
            unit["text"] = original[:low]
        result["missing_units"] = [i for i in range(1, min(total, MAX_UNITS) + 1)
                                   if not any(u["number"] == i and u["text"] for u in kept)]
        if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 44 * 1024:
            return failure(suffix, "document_output_limit")
        return result
    except DocumentError as error:
        return failure(suffix, error.code)
    except (zipfile.BadZipFile, ET.ParseError, DefusedXmlException, DecompressionBombError,
            PdfiumError, OSError, ValueError, KeyError):
        # 仅映射已知文档/解码异常；编程错误交给隔离进程失败，不伪装成正常提取。
        return failure(suffix, "invalid_document")


async def extract_document(data: bytes, suffix: str) -> dict:
    """隔离 CPU 解析，硬超时杀死并回收子进程；只传字节，环境不继承凭据。"""
    suffix = suffix.lower()
    if suffix not in SUPPORTED or not data or len(data) > MAX_BYTES:
        return parse_document(data, suffix)
    command = [sys.executable, "--document-worker", suffix] if getattr(sys, "frozen", False) else [
        sys.executable, "-m", "orvia_backend.documents.worker", suffix]
    env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP") if key in os.environ}
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    try:
        process = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, env=env, limit=MAX_STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except OSError:
        return failure(suffix, "worker_unavailable")

    async def exchange():
        async def send():
            process.stdin.write(data)
            await process.stdin.drain()
            process.stdin.close()
        sender = asyncio.create_task(send())
        try:
            output = await process.stdout.read(MAX_STDOUT + 1)
            # read(n) may return early; continue only within the fixed protocol budget.
            while len(output) <= MAX_STDOUT:
                chunk = await process.stdout.read(MAX_STDOUT + 1 - len(output))
                if not chunk:
                    break
                output += chunk
            if len(output) > MAX_STDOUT:
                raise DocumentError("worker_output_limit")
            await sender
            await process.wait()
            if process.returncode:
                raise DocumentError("worker_failed")
            return json.loads(output)
        finally:
            if not sender.done():
                sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)

    try:
        return await asyncio.wait_for(exchange(), TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return failure(suffix, "extraction_timeout")
    except (DocumentError, ValueError, BrokenPipeError, ConnectionResetError):
        return failure(suffix, "worker_failed")
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()
