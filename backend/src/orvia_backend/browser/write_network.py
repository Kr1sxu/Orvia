"""M18 专用网络出口：准确站点授权后固定公共 IP，秘密只在当前请求内存中流转。"""

from __future__ import annotations

import httpx

from .network import BrowserError, origin, public_ip, resolve, validate_url


def write_url(value: str) -> str:
    """写会话仅允许公开 HTTPS；合成测试通过注入 transport/resolver，不放宽产品策略。"""
    target = validate_url(value)
    if origin(target)[0] != "https":
        raise BrowserError("URL_BLOCKED", "浏览器写会话仅允许准确授权的公开 HTTPS 站点")
    return target


class WriteNetwork:
    """不允许浏览器直连，也不使用持久客户端 Cookie 或环境代理。

    仅从专用浏览器当前请求提取 Cookie/Authorization；调用方必须先核对准确 origin
    与一次性审批。HTTP客户端不跟随重定向；适配器停止3xx并要求明确授权最终页。
    """

    def __init__(self, *, transport=None, resolver=resolve):
        self.transport, self.resolver = transport, resolver

    async def fetch(self, url: str, *, method="GET", body: bytes | None = None,
                    headers: dict | None = None, limit=512_000) -> tuple[int, dict, bytes]:
        target = httpx.URL(write_url(url))
        if method not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
            raise BrowserError("METHOD_BLOCKED", "此网络请求方法不在浏览器写会话范围")
        if body and len(body) > 3 * 1024 * 1024:
            raise BrowserError("REQUEST_TOO_LARGE", "外发正文超过浏览器预算")
        addresses = await self.resolver(target.host, 443)
        if not addresses or any(not public_ip(address) for address in addresses):
            raise BrowserError("ADDRESS_BLOCKED", "DNS 解析包含非公开地址")
        allowed = {"accept", "accept-language", "content-type", "cookie", "authorization", "origin",
                   "referer", "x-csrf-token", "x-xsrf-token", "x-requested-with"}
        outbound = {key.lower(): value for key, value in (headers or {}).items()
                    if key.lower() in allowed and isinstance(value, str) and "\r" not in value and "\n" not in value}
        outbound.update({"host": target.netloc.decode("ascii"), "accept-encoding": "identity", "user-agent": "Orvia-Automation/0.2"})
        pinned = target.copy_with(host=addresses[0])
        async with httpx.AsyncClient(transport=self.transport, trust_env=False, follow_redirects=False, timeout=5) as client:
            async with client.stream(method, pinned, content=body, headers=outbound,
                                     extensions={"sni_hostname": target.host}) as response:
                if response.headers.get("content-encoding", "identity").lower() not in {"", "identity"}:
                    raise BrowserError("ENCODING_BLOCKED", "拒绝压缩响应以保持内存上限")
                data = bytearray()
                async for chunk in response.aiter_raw():
                    if len(data) + len(chunk) > limit:
                        raise BrowserError("RESPONSE_TOO_LARGE", "网页响应超过预算，未返回不完整内容")
                    data.extend(chunk)
                # 保留当前 context 所需的 Set-Cookie；它只交还浏览器，不进入外部 DTO/账本。
                returned = dict(response.headers)
                cookies = response.headers.get_list("set-cookie")
                if cookies:
                    returned["set-cookie"] = "\n".join(cookies)
                return response.status_code, returned, bytes(data)
