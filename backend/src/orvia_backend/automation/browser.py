"""M18 专用可见浏览器：动作和实际外发分开确认，页面内容不能创建授权。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email import policy as email_policy
from email.parser import BytesParser
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import httpx
from playwright.async_api import Error as PlaywrightError, async_playwright

from ..browser.network import BrowserError, origin
from ..browser.write_network import WriteNetwork, write_url
from ..computer.paths import PathPolicy, ToolError, sensitive


_KINDS = {"form", "message", "upload", "delete", "transaction"}
_SECRET = re.compile(r"pass|pwd|secret|token|auth|cookie|session|csrf|credit|card|cvv|cvc|otp|credential|signature|assertion|api.?key|(^|[\s_.-])(key|code|state|ticket|cc|pin)([\s_.-]|$)", re.I)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _public_url(url):
    """认证回跳可能在查询参数带秘密；DTO仅显示遮盖地址，真实URL只留当前route内存。"""
    parsed = urlsplit(url)
    try:
        pairs = parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=80)
        query = urlencode([(key, "[敏感字段已隐藏]" if _SECRET.search(key) else value) for key, value in pairs])
    except ValueError:
        query = "[查询参数已隐藏]"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


def _request_preview(body, content_type, url):
    """预算内展示完整普通叶字段；遮盖、深层/超量字段和二进制都明确标注。

    multipart仅在当前内存解析，不保存原文；文件清单来自实际待发字节，非网页宣称，
    同时保留整个请求SHA256以绑定用户实际审批的不可变快照。
    """
    fields, files = [], []
    redacted, truncated, unreadable = False, False, False
    preview_bytes = 0

    def append(key, value):
        nonlocal redacted, truncated, preview_bytes
        if len(fields) >= 30:
            truncated = True
            return
        key = str(key)
        is_secret = bool(_SECRET.search(key))
        if len(key) > 160:
            key, truncated = key[:160], True
        if is_secret:
            value, redacted = "[敏感字段已隐藏]", True
        elif not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False)
        entry = {"name": key, "value": value}
        needed = len(json.dumps(entry, ensure_ascii=False).encode())
        if preview_bytes + needed > 8192:
            entry["value"] = "[超出8KiB预览预算，字段值未展示]"
            truncated = True
            needed = len(json.dumps(entry, ensure_ascii=False).encode())
            if preview_bytes + needed > 8192:
                return
        fields.append(entry)
        preview_bytes += needed

    def flatten(key, value, depth=0):
        nonlocal truncated
        if len(fields) >= 30:
            truncated = True
            return
        if _SECRET.search(key):
            append(key, "[敏感字段已隐藏]")
        elif depth > 6:
            append(key, "[超过预览深度，结构未展示]")
            truncated = True
        elif isinstance(value, dict):
            if not value:
                append(key or "json", "{}")
            for index, (nested, child) in enumerate(value.items()):
                flatten(f"{key}.{nested}" if key else str(nested), child, depth + 1)
                if len(fields) >= 30:
                    truncated = index < len(value) - 1 or truncated
                    break
        elif isinstance(value, list):
            if not value:
                append(key or "json", "[]")
            for index, child in enumerate(value):
                flatten(f"{key}[{index}]", child, depth + 1)
                if len(fields) >= 30:
                    truncated = index < len(value) - 1 or truncated
                    break
        else:
            append(key or "json", value)

    try:
        media = content_type.lower()
        if "multipart/form-data" in media:
            message = BytesParser(policy=email_policy.default).parsebytes(
                b"Content-Type: " + content_type.encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
            if not message.is_multipart() or message.defects:
                raise ValueError()
            for part in message.iter_parts():
                if part.is_multipart() or part.get_content_disposition() != "form-data":
                    truncated = True
                    continue
                name = part.get_param("name", header="content-disposition") or "unnamed"
                content = part.get_payload(decode=True) or b""
                filename = part.get_filename()
                if filename is not None:
                    if files or len(content) > 2 * 1024 * 1024:
                        raise BrowserError("BROWSER_UPLOAD_LIMIT", "实际请求仅允许一个最多2MiB的文件")
                    item = {"field": str(name)[:160], "name": str(filename)[:240], "bytes": len(content),
                            "sha256": hashlib.sha256(content).hexdigest()}
                    files.append(item)
                    if len(str(name)) > 160 or len(str(filename)) > 240:
                        truncated = True
                    append(str(name) + " (文件)", json.dumps(item, ensure_ascii=False))
                else:
                    append(name, content.decode(part.get_content_charset() or "utf-8"))
        elif "application/json" in media:
            flatten("", json.loads(body.decode()))
        elif "application/x-www-form-urlencoded" in media or not body:
            pairs = parse_qsl(body.decode() if body else urlsplit(url).query, keep_blank_values=True, max_num_fields=1000)
            for key, value in pairs:
                append(key, value)
        else:
            # 无法辨识普通文本中的凭据，明确拒绝把遮盖预览声称为全量正文。
            append("body", "[未解析的正文已隐藏；请核对页面填写内容和字节摘要]")
            redacted, unreadable = True, True
    except (ValueError, UnicodeError, RecursionError, LookupError):
        fields, redacted, unreadable = [{"name": "body", "value": "[正文格式无法安全预览，已隐藏]"}], True, True
    complete = not (truncated or redacted or unreadable or files)
    notice = ("普通字段在预算内完整展示；二进制文件仅展示实际名称、大小和SHA256" if files and not truncated and not redacted else
              "预览不完整：存在截断、未展开、无法解析或敏感遮盖，不能视作全量正文" if not complete else
              "普通结构化字段已完整展示；实际发送以整个请求字节摘要绑定")
    return fields, redacted, {"fields_truncated": truncated, "body_preview_complete": complete,
                              "preview_notice": notice, "files": files}


def _preview_fields(body, content_type, url):
    """保持内部旧调用的两值形式；实际审批DTO另携明确完整性元数据。"""
    fields, redacted, _metadata = _request_preview(body, content_type, url)
    return fields, redacted


@dataclass
class _Session:
    cid: str
    sid: str
    browser: object
    context: object
    page: object
    allowed_origins: set
    allowed_actions: set
    get_write_paths: set
    controls: dict = field(default_factory=dict)
    routes: set = field(default_factory=set)
    pending: dict | None = None
    active: object | None = None
    status: str = "ready"
    result: dict | None = None
    category: str = "manual"
    sent: int = 0
    requests: int = 0
    response_bytes: int = 0
    document_count: int = 0
    initial_url: str = ""
    pending_ready: object = field(default_factory=asyncio.Event)
    in_flight: int = 0
    queued_count: int = 0
    queued_bytes: int = 0
    before_text: str = ""
    closed: bool = False
    queue_lock: object = field(default_factory=asyncio.Lock)
    network_lock: object = field(default_factory=asyncio.Lock)


class BrowserAdapter:
    """每会话单页、内存 Cookie；公开 HTTPS exact origin、一步审批、实际写请求再审批。

    headless=True 只由测试代码显式构造；产品默认可见配套 Chromium。没有调用方
    evaluate/任意选择器、已有个人 profile、环境变量放宽网络或自动重放入口。
    """

    def __init__(self, network=None, *, headless=False, runtime_root=None):
        self.network = network or WriteNetwork()
        self.headless = headless
        self.runtime_root = runtime_root
        self._sessions = {}
        self._manager = None

    def _get(self, cid, session_id):
        session = self._sessions.get(session_id)
        if not session or session.cid != cid or session.closed:
            raise ToolError("BROWSER_SESSION_INVALID", "浏览器会话已关闭或不属于当前任务")
        return session

    async def open(self, cid, url, *, allowed_actions=None, get_write_paths=None):
        try:
            target = write_url(url)
        except BrowserError as error:
            raise ToolError(error.code, error.message) from error
        kinds = set(allowed_actions or [])
        if not kinds or not kinds <= _KINDS:
            raise ToolError("BROWSER_PERMISSION_DENIED", "浏览器任务动作类别无效")
        if len(self._sessions) >= 4:
            raise ToolError("BROWSER_SESSION_LIMIT", "最多同时保留四个专用浏览器会话，请先关闭旧会话")
        paths = set(get_write_paths or [])
        if any(not isinstance(path, str) or not path.startswith("/") or len(path) > 500 for path in paths):
            raise ToolError("BROWSER_PERMISSION_DENIED", "GET 写端点必须是明确的站内路径")
        if self._manager is None:
            self._manager = await async_playwright().start()
        executable = None
        if os.name == "nt" and not self.headless:
            from .browser_runtime import prepare_chromium
            executable = str(await asyncio.to_thread(prepare_chromium, self._manager.chromium.executable_path, self.runtime_root))
        try:
            browser = await self._manager.chromium.launch(headless=self.headless, executable_path=executable, chromium_sandbox=True, timeout=10_000, proxy={"server": "http://127.0.0.1:9"},
                args=["--disable-background-networking", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"])
        except PlaywrightError as exc:
            raise ToolError("BROWSER_RUNTIME_UNAVAILABLE", "配套 Chromium 不可用；可见会话需要完整 Chromium 运行时") from exc
        try:
            context = await asyncio.wait_for(browser.new_context(accept_downloads=False, service_workers="block", permissions=[]), timeout=8)
            page = await asyncio.wait_for(context.new_page(), timeout=8)
        except (PlaywrightError, TimeoutError) as exc:
            # sid尚未交付时也要关闭本次自有浏览器；页面沙箱初始化不能无限占据协议。
            try:
                await asyncio.wait_for(browser.close(), timeout=5)
            except (PlaywrightError, TimeoutError):
                raise ToolError("BROWSER_RUNTIME_UNAVAILABLE", "页面初始化失败，关闭未确认；请退出专用浏览器并核对，不会自动重试") from None
            raise ToolError("BROWSER_RUNTIME_UNAVAILABLE", "专用浏览器页面初始化失败；未禁用沙箱或改用个人浏览器") from exc
        sid = str(uuid4())
        session = _Session(cid, sid, browser, context, page, {origin(target)}, kinds, paths)
        self._sessions[sid] = session
        try:
            await context.route_web_socket("**/*", lambda ws: ws.close())
            context.on("page", lambda popup: asyncio.create_task(popup.close()))
            page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))
            page.on("download", lambda download: asyncio.create_task(download.cancel()))
            await context.route("**/*", lambda route: self._route(session, route))
            # 初次GET或重定向也可能是声明写端点；先交付sid供实际外发审批，不能
            # 等goto完成才让用户看见请求。about:blank仅表示目标网页尚未加载。
            session.initial_url = target
            async def navigate():
                try:
                    await page.goto(target, wait_until="domcontentloaded", timeout=195_000)
                except (PlaywrightError, BrowserError, OSError):
                    if not session.closed and not session.result:
                        session.status = "blocked"
                        session.result = {"status": "blocked", "verified": False, "evidence": {},
                                          "message": "初始页面未加载；未绕过站点/审批边界，请关闭专用会话"}
            session.active = asyncio.create_task(navigate())
            ready = asyncio.create_task(session.pending_ready.wait())
            try:
                done, _ = await asyncio.wait({session.active, ready}, timeout=10, return_when=asyncio.FIRST_COMPLETED)
                if session.active.done() and (session.result or {}).get("evidence", {}).get("code") == "BROWSER_REDIRECT_REVIEW":
                    raise ToolError("BROWSER_REDIRECT_REVIEW", "初始HTTP重定向不直接跟随；请明确授权站点的最终HTTPS页面，再处理该页面的实际外发确认")
                if not done or session.active.done() and session.page.url == "about:blank" and not session.pending:
                    raise ToolError("BROWSER_OPEN_FAILED", "初始页面未加载且没有可审批请求，请关闭专用会话")
            finally:
                ready.cancel()
                await asyncio.gather(ready, return_exceptions=True)
            return await self.observe(cid, sid)
        except ToolError:
            # 初次观察超预算时还没有返回session_id，必须回收未交付的可见会话。
            await self.close(cid, sid)
            raise
        except (PlaywrightError, BrowserError, OSError) as exc:
            await self.close(cid, sid)
            raise ToolError("BROWSER_OPEN_FAILED", "专用页面打开失败；未绕过站点或网络限制") from exc

    async def grant_origin(self, cid, session_id, url):
        """调用方必须先让主进程原生批准准确站点，网页重定向不能调用这个接口。"""
        session = self._get(cid, session_id)
        try:
            target = origin(write_url(url))
        except BrowserError as error:
            raise ToolError(error.code, error.message) from error
        if target not in session.allowed_origins and len(session.allowed_origins) >= 8:
            raise ToolError("BROWSER_SITE_LIMIT", "单任务最多准确授权八个站点")
        session.allowed_origins.add(target)
        return {"granted": True}

    async def _route(self, session, route):
        task = asyncio.current_task()
        session.routes.add(task)
        request = route.request
        sending = False
        queued = False
        body = b""
        try:
            session.requests += 1
            target = write_url(request.url)
            if session.closed or session.requests > 200 or session.response_bytes >= 8_000_000:
                raise BrowserError("BROWSER_BUDGET_EXCEEDED", "浏览器会话网络预算已用完")
            if origin(target) not in session.allowed_origins:
                raise BrowserError("BROWSER_SITE_BLOCKED", "请求站点未获准确授权；请另行确认站点后重新观察")
            if request.frame != session.page.main_frame or request.resource_type not in {"document", "script", "stylesheet", "image", "xhr", "fetch", "other"}:
                raise BrowserError("RESOURCE_BLOCKED", "禁止子页面、Worker、媒体或未知资源")
            method = request.method.upper()
            body = request.post_data_buffer or b""
            if len(body) > 3 * 1024 * 1024:
                raise BrowserError("REQUEST_TOO_LARGE", "外发正文超过预算")
            headers = await request.all_headers()
            if request.resource_type == "document":
                session.document_count += 1
            # GET也可能写服务器状态；页面发起的业务fetch/xhr和后续导航都须实际外发确认。
            # 初次任务grant只覆盖首个bootstrap文档，HTTP重定向明确拒绝；资源有独立预算。
            bootstrap = request.resource_type == "document" and session.document_count == 1
            is_write = (method != "GET" or request.resource_type in {"xhr", "fetch"}
                        or request.resource_type == "document" and not bootstrap
                        or urlsplit(target).path in session.get_write_paths)
            if is_write:
                if session.queued_count >= 4 or session.queued_bytes + len(body) > 4 * 1024 * 1024:
                    raise BrowserError("BROWSER_QUEUE_EXCEEDED", "未审批请求队列已满；请先处理现有外发确认")
                session.queued_count += 1
                session.queued_bytes += len(body)
                queued = True
                async with session.queue_lock:
                    if session.closed:
                        await route.abort()
                        return
                    fields, redacted, preview_metadata = _request_preview(body, headers.get("content-type", ""), target)
                    if preview_metadata["files"] and "upload" not in session.allowed_actions:
                        raise BrowserError("BROWSER_PERMISSION_DENIED", "本任务未授权实际文件上传")
                    preview = {"request_id": str(uuid4()), "url": _public_url(target), "method": method, "fields": fields,
                               "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                               "url_sha256": hashlib.sha256(target.encode()).hexdigest(),
                               "sensitive_redacted": redacted, "category": session.category,
                               "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=180)).isoformat(),
                               **preview_metadata}
                    preview["revision"] = _digest(preview)
                    decision = asyncio.get_running_loop().create_future()
                    session.pending = {"preview": preview, "decision": decision}
                    session.pending_ready.set()
                    session.status = "awaiting_approval"
                    try:
                        approved = await asyncio.wait_for(decision, timeout=180)
                    finally:
                        session.pending = None
                    if not approved or session.closed:
                        await route.abort()
                        session.status = "cancelled" if session.closed else "rejected"
                        return
                    sending = True
                    session.sent += 1
                    session.in_flight += 1
                    session.status = "running"
                    session.before_text = "" if session.page.url == "about:blank" else await self._body_text(session)
                    # 批准只覆盖这个内存快照；不重复调用 fetch，不跟随 HTTP 重定向。
                    status, response_headers, raw = await self._fetch(session, target, method, body, headers)
            else:
                status, response_headers, raw = await self._fetch(session, target, method, body, headers)
            if 300 <= status < 400 and response_headers.get("location"):
                # Chromium的HTTP重定向不保证再次进入Playwright route，不能让跳转
                # 绕过固定出口或偷偷打开直连。明确拒绝，最终页面需另行准确授权。
                raise BrowserError("BROWSER_REDIRECT_REVIEW", "HTTP重定向未直接跟随，请明确授权最终HTTPS页面后重新观察")
            if "attachment" in response_headers.get("content-disposition", "").lower():
                raise BrowserError("DOWNLOAD_BLOCKED", "本轮浏览器不允许下载")
            media = response_headers.get("content-type", "").split(";")[0].lower()
            allowed_media = {"text/html", "application/xhtml+xml", "text/plain", "application/json", "text/css", "text/javascript", "application/javascript", "image/png", "image/jpeg", "image/webp", "image/gif"}
            if raw and media not in allowed_media:
                raise BrowserError("RESOURCE_BLOCKED", "响应类型不在安全资源范围")
            safe = {key: value for key, value in response_headers.items() if key.lower() in
                    {"content-type", "location", "set-cookie", "cache-control", "access-control-allow-origin", "access-control-allow-credentials"}}
            if request.resource_type == "document":
                sources = " ".join(f"{scheme}://{host}" for scheme, host, _port in session.allowed_origins)
                safe["content-security-policy"] = ("sandbox allow-scripts allow-same-origin allow-forms; default-src 'none'; "
                    f"script-src {sources} 'unsafe-inline'; style-src {sources} 'unsafe-inline'; img-src {sources} data:; "
                    f"connect-src {sources}; form-action {sources}; frame-src 'none'; worker-src 'none'; base-uri 'none'")
            await route.fulfill(status=status, headers=safe, body=raw)
            if sending:
                # HTTP 成功不证明业务完成；仅记录回执，必须再核验事先批准的页面条件。
                session.result = {"status": "response_received" if 200 <= status < 400 else "failed", "verified": False,
                    "evidence": {"http_status": status, "request_sha256": hashlib.sha256(body).hexdigest(),
                                 "response_sha256": hashlib.sha256(raw).hexdigest(), "response_bytes": len(raw)},
                    "message": "实际请求已收到响应；请核对页面业务结果，HTTP 状态不证明业务语义正确"}
                session.status = session.result["status"]
        except asyncio.CancelledError:
            if sending:
                session.status = "uncertain"
                session.result = {"status": "uncertain", "verified": False, "evidence": {}, "message": "实际请求已进入发送阶段；中断后不确定服务器是否已写入，禁止自动重放"}
            try:
                await route.abort()
            except PlaywrightError:
                pass
            raise
        except (BrowserError, PlaywrightError, httpx.HTTPError, OSError, TimeoutError) as error:
            code = error.code if isinstance(error, BrowserError) else "BROWSER_NETWORK_FAILED"
            if sending:
                session.status = "uncertain"
                evidence = {"code": code}
                if code == "BROWSER_REDIRECT_REVIEW":
                    evidence.update(http_status=status, request_sha256=hashlib.sha256(body).hexdigest(),
                                    response_sha256=hashlib.sha256(raw).hexdigest(), response_bytes=len(raw))
                session.result = {"status": "uncertain", "verified": False, "evidence": evidence, "message": "发送后未取得可靠核验；请人工检查外部结果，不会自动重试"}
            elif not session.closed:
                session.result = {"status": "blocked", "verified": False, "evidence": {"code": code}, "message": "未批准或超出边界的网络请求已阻止"}
            try:
                await route.abort()
            except PlaywrightError:
                pass
        finally:
            session.routes.discard(task)
            if sending:
                session.in_flight -= 1
            if queued:
                session.queued_count -= 1
                session.queued_bytes -= len(body)

    async def _fetch(self, session, target, method, body, headers):
        async with session.network_lock:
            if session.closed:
                raise BrowserError("BROWSER_SESSION_CLOSED", "浏览器会话已关闭")
            result = await self.network.fetch(target, method=method, body=body, headers=headers,
                                              limit=min(512_000, 8_000_000 - session.response_bytes))
            session.response_bytes += len(result[2])
            return result

    async def observe(self, cid, session_id):
        """敌意脚本可让页面主线程无响应；有界等待后返回固定错误供用户关闭专用会话。"""
        try:
            return await asyncio.wait_for(self._observe(cid, session_id), timeout=8)
        except TimeoutError as exc:
            raise ToolError("BROWSER_OBSERVE_FAILED", "页面观察超时；请关闭专用会话，不会继续盲目操作") from exc

    async def _observe(self, cid, session_id):
        session = self._get(cid, session_id)
        try:
            blocked_redirect = (session.result or {}).get("evidence", {}).get("code") == "BROWSER_REDIRECT_REVIEW"
            if session.initial_url and session.page.url == "about:blank" or blocked_redirect and session.page.url == "chrome-error://chromewebdata/":
                state = {"url": session.page.url, "title": "", "controls": [], "page_text": ""}
                return {"session_id": session_id, **state, "state_hash": _digest(state), "status": session.status,
                        "notice": "目标页面尚未加载；先在Orvia处理实际外发确认，这不是已读取网页的结果"}
            # history.replaceState可在不发HTTP的情况下改写超长地址；不能让敌意页面
            # 绕过网络URL限制并撑破stdio帧，也不能截断后继续以不完整身份审批。
            if len(session.page.url) > 2048:
                raise ToolError("BROWSER_OBSERVATION_LIMIT", "页面地址超过观察预算；请关闭专用会话，不会截断目标身份")
            parsed = urlsplit(session.page.url)
            try:
                # data/file/blob导航未必进入HTTP route；观察与动作也必须复核当前站点。
                # 页内hash导航不外发，仍绑定准确origin及完整控件/正文状态摘要。
                actual_url = write_url(urlunsplit((*parsed[:4], "")))
            except BrowserError as error:
                raise ToolError(error.code, error.message) from error
            if origin(actual_url) not in session.allowed_origins:
                raise ToolError("BROWSER_SITE_BLOCKED", "当前页面站点没有准确授权，请停止观察与操作")
            public_url = _public_url(session.page.url)
            if len(public_url) > 2048:
                raise ToolError("BROWSER_OBSERVATION_LIMIT", "页面地址超过观察预算；请关闭专用会话，不会截断目标身份")
            title = await asyncio.wait_for(session.page.evaluate("() => (document.title || '').slice(0,200)"), timeout=2)
            matches = session.page.locator("input,textarea,select,button,a[href],[role=button],[role=checkbox]")
            # 先取数量标量，再最多获取80个句柄；不能先让Playwright传回全部敌意DOM。
            count = min(await matches.count(), 80)
            controls = []
            session.controls = {}
            for index in range(count):
                element = await matches.nth(index).element_handle(timeout=1000)
                if element is None:
                    continue
                if not await element.is_visible():
                    continue
                item = await element.evaluate("""el => {
                    let label='';if(el.labels?.[0]){const clone=el.labels[0].cloneNode(true);
                      for(const nested of clone.querySelectorAll('input,textarea,select,button'))nested.remove();label=clone.textContent||'';}
                    return {tag:el.tagName.toLowerCase(),type:el.type||'',role:(el.getAttribute('role')||'').slice(0,100),
                    identity:[el.getAttribute('name'),el.getAttribute('id'),el.getAttribute('autocomplete'),el.getAttribute('aria-label')].join(' ').slice(0,500),
                    name:(el.getAttribute('aria-label')||label||el.innerText||el.name||el.id||'').trim().slice(0,100),
                    value:String(el.value||'').slice(0,200),checked:!!el.checked,disabled:!!el.disabled};}""")
                if item["type"] in {"hidden", "password"} or _SECRET.search(item["name"]) or _SECRET.search(item["identity"]):
                    continue
                actions = ["click"]
                if item["tag"] in {"input", "textarea"}:
                    actions = ["upload"] if item["type"] == "file" else ["check"] if item["type"] in {"checkbox", "radio"} else ["fill"]
                elif item["tag"] == "select":
                    actions = ["select"]
                control_id = f"c{index}"
                public = {"control_id": control_id, "role": item["role"] or item["tag"], "name": item["name"],
                          "actions": actions, "value": str(item["value"])[:200], "checked": item["checked"], "disabled": item["disabled"]}
                if len(json.dumps(controls + [public], ensure_ascii=False).encode()) > 16_000:
                    break
                controls.append(public)
                session.controls[control_id] = {"element": element, "public": public}
            state = {"url": public_url, "title": title, "controls": controls,
                     "page_text": await self._body_text(session)}
            observation = {"session_id": session_id, **state, "state_hash": _digest(state)}
            if len(json.dumps(observation, ensure_ascii=False).encode()) > 24 * 1024:
                raise ToolError("BROWSER_OBSERVATION_LIMIT", "页面观察超过协议预算；请关闭专用会话，不会返回截断身份")
            return observation
        except PlaywrightError as exc:
            raise ToolError("BROWSER_OBSERVE_FAILED", "页面已改变或关闭；请停止操作并重新观察") from exc

    async def _body_text(self, session):
        """固定只读遍历先截断，排除全部输入/textarea与隐藏节点，不读取控件凭据值。"""
        text = await asyncio.wait_for(session.page.evaluate("""() => {
          if(!document.body)return '';
          const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,{acceptNode(node){
            const parent=node.parentElement;if(!parent||parent.closest('script,style,input,textarea,select,[hidden],[aria-hidden="true"]'))return NodeFilter.FILTER_REJECT;
            const style=getComputedStyle(parent);return style.display==='none'||style.visibility==='hidden'?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT;
          }});let value='',count=0,node;
          while((node=walker.nextNode())&&count++<2000&&value.length<4000)value+=(node.textContent||'').slice(0,4000-value.length)+'\\n';
          return value.slice(0,4000);
        }"""), timeout=2)
        return text.encode("utf-8", errors="replace").decode("utf-8")

    async def verify_result(self, cid, session_id, expected_text):
        """仅核验原生审批前指定的正文条件；网页宣称成功、HTTP200均不能自行完成任务。

        期待文本须在本次外发前基线中不存在并在收到回执后出现，减少页面已有“成功”
        字样导致的误判。此证据仍不是站点服务器业务真值或交易结算的独立证明。
        """
        session = self._get(cid, session_id)
        if not isinstance(expected_text, str) or not expected_text.strip() or len(expected_text) > 1000:
            raise ToolError("BROWSER_VERIFICATION_INVALID", "网页核验需要审批前明确的1到1000字期待文本")
        previous = session.result
        if not previous or previous["status"] not in {"response_received", "awaiting_verification"} or previous["evidence"].get("http_status", 0) not in range(200, 400):
            return {"status": "awaiting_verification", "verified": False, "evidence": {}, "message": "当前步骤尚无实际外发回执，不能仅凭页面文字标记完成"}
        text = ""
        for _ in range(10):
            try:
                text = await self._body_text(session)
            except (PlaywrightError, TimeoutError):
                session.status = "uncertain"
                session.result = {"status": "uncertain", "verified": False, "evidence": previous["evidence"],
                                  "message": "外发后页面已关闭或无响应，无法核验业务条件；不会自动重发"}
                return session.result
            if expected_text in text and expected_text not in session.before_text:
                session.result = {"status": "verified", "verified": True,
                    "evidence": {**previous["evidence"], "expected_sha256": hashlib.sha256(expected_text.encode()).hexdigest(),
                                 "page_sha256": hashlib.sha256(text.encode()).hexdigest(), "matched": True},
                    "message": "已收到外发回执，页面出现审批前指定的新期待文本；业务语义仍需人工核对"}
                session.status = "verified"
                return session.result
            await asyncio.sleep(0.1)
        session.result = {"status": "awaiting_verification", "verified": False,
            "evidence": {**previous["evidence"], "expected_sha256": hashlib.sha256(expected_text.encode()).hexdigest(),
                         "page_sha256": hashlib.sha256(text.encode()).hexdigest(), "matched": False},
            "message": "已收到HTTP回执，但未出现事先指定的新期待文本；请人工核对，不会自动重发"}
        session.status = "awaiting_verification"
        return session.result

    async def start_action(self, cid, session_id, control_id, action, value, expected_state_hash,
                           upload_path=None, *, category="form"):
        session = self._get(cid, session_id)
        if category not in session.allowed_actions or (action == "upload" and category != "upload"):
            raise ToolError("BROWSER_PERMISSION_DENIED", "此任务未授权相应网页动作类别")
        if session.active and not session.active.done() or session.pending:
            raise ToolError("BROWSER_ACTION_BUSY", "上一步动作或外发确认尚未完成")
        observation = await self.observe(cid, session_id)
        if observation["state_hash"] != expected_state_hash:
            raise ToolError("STALE_APPROVAL", "页面状态已变化；请重新观察并逐步确认")
        control = session.controls.get(control_id)
        if not control or action not in control["public"]["actions"] or control["public"]["disabled"]:
            raise ToolError("BROWSER_TARGET_INVALID", "网页控件或动作无效")
        if not isinstance(value, (str, bool, type(None))) or isinstance(value, str) and len(value) > 4000:
            raise ToolError("BROWSER_VALUE_INVALID", "网页输入超过范围")
        checked = None
        if action == "check":
            if value not in {True, False, "true", "false", "1", "0", "", None}:
                raise ToolError("BROWSER_VALUE_INVALID", "勾选动作只接受true或false")
            checked = value is True or value in {"true", "1"}
        upload = None
        if action == "upload":
            if not upload_path:
                raise ToolError("BROWSER_UPLOAD_REQUIRED", "上传需要主进程原生选择一个本地文件")
            path = Path(upload_path)
            if not path.is_absolute() or any(sensitive(part) for part in path.parts):
                raise ToolError("BROWSER_UPLOAD_DENIED", "不允许上传凭据或内部文件")
            policy = PathPolicy(str(path.parent))
            target = policy.resolve(path.name, "file")
            with target.open("rb") as stream:
                info = policy.validate_open_file(stream.fileno(), target)
                if info.st_nlink != 1:
                    raise ToolError("BROWSER_UPLOAD_DENIED", "上传只接受独立普通文件，不能通过硬链接别名绕过敏感路径检查")
                if info.st_size > 2 * 1024 * 1024:
                    raise ToolError("BROWSER_UPLOAD_LIMIT", "单文件上传最多 2 MiB")
                content = stream.read(2 * 1024 * 1024 + 1)
                after = policy.validate_open_file(stream.fileno(), target)
                if after.st_nlink != 1 or len(content) > 2 * 1024 * 1024 or (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ToolError("BROWSER_UPLOAD_CHANGED", "上传文件读取期间已变化")
            upload = {"name": path.name, "mimeType": mimetypes.guess_type(path.name)[0] or "application/octet-stream", "buffer": content}
        session.category, session.status, session.result = category, "running", None
        session.sent = 0
        element = control["element"]
        async def execute():
            try:
                if action == "fill":
                    await element.fill(str(value or ""), timeout=5000)
                elif action == "check":
                    await element.set_checked(checked, timeout=5000)
                elif action == "select":
                    await element.select_option(str(value or ""), timeout=5000)
                elif action == "upload":
                    await element.set_input_files(upload, timeout=5000)
                else:
                    await element.click(timeout=5000, no_wait_after=True)
                if not session.pending and not session.result:
                    actual = None
                    if action in {"fill", "select"}:
                        actual = await element.input_value()
                        matched = actual == str(value or "")
                    elif action == "check":
                        matched = await element.is_checked() == checked
                    elif action == "upload":
                        actual = await element.evaluate("el=>Array.from(el.files||[]).map(f=>({name:f.name,size:f.size}))")
                        matched = actual == [{"name": upload["name"], "size": len(upload["buffer"])}]
                    else:
                        matched = False
                    session.status = "ready"
                    session.result = {"status": "verified" if matched else "awaiting_verification", "verified": matched,
                        "evidence": {"action": action, "control_matched": matched},
                        "message": "已读回核验控件状态；实际外发仍需逐项确认" if matched else "点击已执行但尚无可证明完成的页面条件；实际外发仍需确认"}
            except (PlaywrightError, OSError):
                if not session.result and not session.pending:
                    session.status = "uncertain" if session.sent else "failed"
                    session.result = {"status": session.status, "verified": False, "evidence": {}, "message": "页面动作未取得可靠核验；不会自动重复点击或提交"}
        session.active = asyncio.create_task(execute())
        # 立即返回让 stdio 串行请求继续处理待外发审批，不能 await click 的导航等待。
        return {"started": True, "session_id": session_id}

    async def pending(self, cid, session_id):
        session = self._get(cid, session_id)
        observation = await self.observe(cid, session_id)
        value = {"pending_request": session.pending["preview"] if session.pending else None,
                 "status": session.status, "observation": observation, "result": session.result}
        if len(json.dumps(value, ensure_ascii=False).encode()) > 48 * 1024:
            raise ToolError("BROWSER_OBSERVATION_LIMIT", "待审批请求和观察超过协议预算；未发送或截断请求，请关闭专用会话")
        return value

    async def approve_request(self, cid, session_id, request_id, revision, approved):
        session = self._get(cid, session_id)
        item = session.pending
        if type(approved) is not bool or not item or item["preview"]["request_id"] != request_id or item["preview"]["revision"] != revision or item["decision"].done():
            raise ToolError("STALE_APPROVAL", "外发请求已变化或审批已使用")
        preview = item["preview"]
        parsed = urlsplit(preview["url"])
        # GET查询也可能包含正文；用于账本的元数据遮盖全部查询，不复用完整审批预览。
        audit_url = urlunsplit((*parsed[:3], "[查询内容仅留审批内存]" if parsed.query else "", ""))
        request_meta = {"method": preview["method"], "url": audit_url,
                        "body_bytes": preview["bytes"], "body_sha256": preview["sha256"],
                        "url_sha256": preview["url_sha256"], "category": preview["category"],
                        "body_preview_complete": preview["body_preview_complete"],
                        "fields_truncated": preview["fields_truncated"], "file_count": len(preview["files"])}
        item["decision"].set_result(approved)
        return {"approved": approved, "request_id": request_id, "request_meta": request_meta}

    async def cancel(self, cid, session_id):
        """关闭页面阻止后续请求；发送阶段取消仍可能已在服务器产生副作用。"""
        session = self._get(cid, session_id)
        # HTTP回执并不能确认外部业务效果；尚未核验的已发送步骤关闭后仍属不确定。
        uncertain = (session.in_flight > 0 or session.status == "uncertain" or
                     session.sent > 0 and not (session.result or {}).get("verified"))
        if session.pending and not session.pending["decision"].done():
            session.pending["decision"].set_result(False)
        if session.active and not session.active.done():
            session.active.cancel()
        session.status = "uncertain" if uncertain else "cancelled"
        result = {"cancelled": True, "status": session.status, "verified": False,
                  "message": "已停止后续浏览器操作；已外发请求需人工核对，不会自动重放"}
        await self.close(cid, session_id)
        return result

    async def close(self, cid, session_id):
        session = self._get(cid, session_id)
        session.closed = True
        if session.pending and not session.pending["decision"].done():
            session.pending["decision"].set_result(False)
        if session.active and not session.active.done():
            session.active.cancel()
        route_tasks = [task for task in list(session.routes) if task is not asyncio.current_task() and not task.done()]
        for task in route_tasks:
            task.cancel()
        if route_tasks:
            await asyncio.gather(*route_tasks, return_exceptions=True)
        await session.context.close()
        await session.browser.close()
        self._sessions.pop(session_id, None)
        return {"closed": True}

    async def close_all(self):
        for session in list(self._sessions.values()):
            if not session.closed:
                await self.close(session.cid, session.sid)
        if self._manager:
            await self._manager.stop()
            self._manager = None
