"""Browser 窄接口：HTTP 优先、动态页受控渲染、搜索摘要与页面正文分离。"""

import asyncio
import json
from datetime import UTC, datetime
from urllib.parse import urljoin

import httpx
import trafilatura
from playwright.async_api import Error as PlaywrightError, async_playwright
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from typing import Literal

from .network import BrowserError, SafeHTTP, origin, validate_url

MAX_BODY = 512_000
MAX_TEXT = 8000


class ReadRequest(BaseModel):
    """仅由可信主进程提交 URL；没有点击、脚本、Cookie 或上传参数。"""
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    mission_id: str = Field(min_length=1, max_length=128)
    url: str = Field(min_length=1, max_length=2048)
    mode: Literal["auto", "http", "playwright"] = "auto"


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    mission_id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=500)
    max_results: int = Field(default=5, ge=1, le=5, strict=True)


def evidence(url=None, *, mode=None, content="", truncated=False, error=None):
    return {"source_url": url, "accessed_at": datetime.now(UTC).isoformat(), "mode": mode,
            "title": "", "content": content[:MAX_TEXT], "truncated": truncated or len(content) > MAX_TEXT, "error": error}


def page_title(markup):
    """提取短标题只用于文本展示，不接受 HTML 渲染。"""
    metadata = trafilatura.extract_metadata(markup)
    return (metadata.title or "")[:200] if metadata else ""


class BrowserService:
    """每次 read 显式 URL 即单页访问范围；资源限同源，无递归抓取。"""
    def __init__(self, key: SecretStr | None = None, *, network=None):
        self.key = key
        self.network = network or SafeHTTP()

    async def web_search(self, query: str, *, max_results=5) -> dict:
        """固定 Tavily 端点、无重试；缺 Key 不联网，也不返回伪造摘要。"""
        result = {**evidence("https://api.tavily.com/search", mode="search"), "available": self.key is not None, "results": []}
        if self.key is None:
            return result | {"error": {"code": "SEARCH_UNAVAILABLE", "message": "未配置 Tavily 搜索凭据"}}
        if not isinstance(query, str) or not query.strip() or len(query) > 500 or type(max_results) is not int or not 1 <= max_results <= 5:
            return result | {"error": {"code": "QUERY_INVALID", "message": "搜索参数无效"}}
        try:
            async with asyncio.timeout(10):
                status, headers, body = await self.network.fetch("https://api.tavily.com/search", limit=128_000, method="POST",
                    payload={"api_key": self.key.get_secret_value(), "query": query.strip(), "max_results": max_results,
                             "search_depth": "basic", "include_answer": False, "include_raw_content": False})
                if status != 200 or headers.get("content-type", "").split(";")[0] != "application/json":
                    raise BrowserError("SEARCH_FAILED", "搜索服务返回非成功 JSON 响应")
                data = json.loads(body)
                if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                    raise ValueError()
                for item in data["results"][:max_results]:
                    if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in ("url", "title", "content")):
                        raise ValueError()
                    try:
                        url = validate_url(item["url"])
                    except BrowserError:
                        continue
                    result["results"].append({**evidence(url, mode="search_snippet", content=item["content"][:1000],
                        truncated=len(item["content"]) > 1000), "title": item["title"][:200]})
                return result
        except BrowserError as error:
            return result | {"results": [], "error": {"code": error.code, "message": error.message}}
        except (TimeoutError, OSError, httpx.HTTPError, ValueError, RecursionError):
            return result | {"results": [], "error": {"code": "SEARCH_FAILED", "message": "搜索请求失败或响应格式无效"}}

    async def _fetch_page(self, url: str, *, budget=None):
        current = validate_url(url)
        for hop in range(4):
            if budget is not None:
                if budget["requests"] <= 0 or budget["bytes"] <= 0:
                    raise BrowserError("RESPONSE_TOO_LARGE", "页面请求次数或总字节预算已用尽")
                budget["requests"] -= 1
            status, headers, raw = await self.network.fetch(current, limit=min(MAX_BODY, budget["bytes"]) if budget else MAX_BODY)
            if budget is not None:
                budget["bytes"] -= len(raw)
            if status in {301, 302, 303, 307, 308}:
                if hop == 3 or not headers.get("location"):
                    raise BrowserError("REDIRECT_LIMIT", "重定向缺少目标或超过三次上限")
                target = validate_url(urljoin(current, headers["location"]))
                if origin(target) != origin(url):
                    raise BrowserError("SCOPE_BLOCKED", "重定向超出显式 URL 的同源范围")
                current = target
                continue
            if status != 200:
                raise BrowserError("HTTP_FAILED", f"网页返回 HTTP {status}")
            if "attachment" in headers.get("content-disposition", "").lower():
                raise BrowserError("RESOURCE_BLOCKED", "不允许下载附件")
            return current, headers, raw
        raise AssertionError("unreachable")

    async def read(self, url: str, *, mode="auto") -> dict:
        """auto 只在成功取得空壳 HTML 时渲染，不绕过 HTTP 或权限错误。"""
        current = None
        used = "http"
        try:
            async with asyncio.timeout(20):
                current = validate_url(url)
                if mode not in {"auto", "http", "playwright"}:
                    raise BrowserError("MODE_INVALID", "读取模式无效")
                if mode == "playwright":
                    used = "playwright"
                    return await self._render(current)
                current, headers, raw = await self._fetch_page(current)
                media = headers.get("content-type", "").split(";")[0].strip().lower()
                if media not in {"text/html", "application/xhtml+xml", "text/plain"}:
                    raise BrowserError("RESOURCE_BLOCKED", "仅允许 HTML 或纯文本页面")
                text = raw.decode("utf-8", errors="replace")
                content = (trafilatura.extract(text, include_comments=False, include_tables=False) or "") if media != "text/plain" else text
                if mode == "auto" and not content.strip() and media != "text/plain":
                    used = "playwright"
                    return await self._render(current)
                result = evidence(current, mode="http", content=content.strip())
                result["title"] = page_title(text) if media != "text/plain" else ""
                if not content.strip():
                    result["error"] = {"code": "EMPTY_CONTENT", "message": "页面没有可读取正文"}
                return result
        except BrowserError as error:
            return evidence(current, mode=used, truncated=error.code == "RESPONSE_TOO_LARGE", error={"code": error.code, "message": error.message})
        except (TimeoutError, OSError, httpx.HTTPError):
            return evidence(current, mode=used, error={"code": "READ_FAILED", "message": "网页读取超时或网络失败"})
        except PlaywrightError:
            return evidence(current, mode=used, error={"code": "PLAYWRIGHT_FAILED", "message": "动态读取失败；请检查 Chromium 安装或页面交互要求"})

    async def _render(self, url: str) -> dict:
        """浏览器无直接网络出口；route 的每条允许请求经固定 IP 的 HTTP 网关取得后 fulfill。

        仅主框架单次导航、同源 GET 文本资源，阻止 Cookie/认证头继承、表单、下载、
        WebSocket、iframe、Worker 与新窗口。网站的 GET 仍可能在服务器产生访问记录。
        """
        failures: set[str] = set()
        requests = 0
        document_seen = False
        budget = {"requests": 30, "bytes": 2_000_000}
        # 先解析主文档的 HTTP 重定向，再以最终地址建立浏览器文档，保证相对资源路径正确。
        final_url, first_headers, first_raw = await self._fetch_page(url, budget=budget)
        url = final_url
        fetch_lock = asyncio.Lock()
        async with async_playwright() as manager:
            # 浏览器自身网络走不可用代理；被 route 接管的资源不经过此代理。
            browser = await manager.chromium.launch(headless=True, proxy={"server": "http://127.0.0.1:9"},
                args=["--disable-background-networking", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"])
            try:
                context = await browser.new_context(accept_downloads=False, service_workers="block", permissions=[])
                await context.route_web_socket("**/*", lambda ws: ws.close())
                page = await context.new_page()
                async def route_request(route):
                    nonlocal requests, document_seen
                    request = route.request
                    try:
                        requests += 1
                        target = validate_url(request.url)
                        if requests > 30 or origin(target) != origin(url) or request.method != "GET":
                            raise BrowserError("SCOPE_BLOCKED", "请求不符合页面范围或预算")
                        if request.frame != page.main_frame or request.resource_type not in {"document", "script", "stylesheet", "xhr", "fetch"}:
                            raise BrowserError("RESOURCE_BLOCKED", "不允许此资源或子页面")
                        if request.resource_type == "document":
                            if document_seen:
                                raise BrowserError("NAVIGATION_BLOCKED", "不允许页面二次导航")
                            document_seen = True
                        if request.resource_type == "document":
                            headers, raw = first_headers, first_raw
                        else:
                            # 串行扣减共享预算，重定向也计数，防止并发资源绕过页面总量限制。
                            async with fetch_lock:
                                _, headers, raw = await self._fetch_page(target, budget=budget)
                        media = headers.get("content-type", "").split(";")[0].strip().lower()
                        allowed = {"document": {"text/html", "application/xhtml+xml", "text/plain"},
                                   "script": {"application/javascript", "text/javascript"}, "stylesheet": {"text/css"},
                                   "xhr": {"application/json", "text/plain", "text/html"}, "fetch": {"application/json", "text/plain", "text/html"}}
                        if media not in allowed[request.resource_type]:
                            raise BrowserError("RESOURCE_BLOCKED", "资源响应类型不符")
                        # 不透传 Set-Cookie、Refresh 或任何服务端授权信息；CSP 封闭非 HTTP 通道。
                        safe_headers = {"content-type": headers["content-type"], "content-security-policy": "sandbox allow-scripts allow-same-origin; default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; form-action 'none'; frame-src 'none'; worker-src 'none'; base-uri 'none'"}
                        await route.fulfill(status=200, headers=safe_headers, body=raw)
                    except (BrowserError, httpx.HTTPError, OSError) as error:
                        failures.add(error.code if isinstance(error, BrowserError) else "NETWORK_FAILED")
                        await route.abort()
                await context.route("**/*", route_request)
                await page.goto(url, wait_until="networkidle", timeout=10_000)
                # 固定读取表达式，无调用方脚本入口；在浏览器内截断，避免传回无限 DOM 正文。
                rendered = await page.evaluate("""() => {
                    const text = document.body?.innerText || '';
                    return {text: text.slice(0, 8000), title: (document.title || '').slice(0, 200), truncated: text.length > 8000};
                }""")
                # JavaScript 按 UTF-16 截断；单独携带截断位，并净化边界孤立代理项，
                # 避免 emoji 被截成半个字符时破坏 UTF-8 stdio 帧。
                content = rendered["text"].encode("utf-8", errors="replace").decode("utf-8").strip()
                result = evidence(final_url, mode="playwright", content=content, truncated=rendered["truncated"])
                # 动态标题也先在页面内限长，避免把无限脚本生成文本跨进程传回。
                result["title"] = rendered["title"].encode("utf-8", errors="replace").decode("utf-8")
                if not content.strip():
                    result["error"] = {"code": "EMPTY_CONTENT", "message": "页面没有可读取正文，可能需要交互"}
                if failures:
                    result["error"] = {"code": "RESOURCE_RESTRICTED", "message": "部分页面请求受限制，正文可能不完整（" + ",".join(sorted(failures)) + "）"}
                    result["truncated"] = True
                return result
            finally:
                await browser.close()
