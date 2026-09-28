"""公开网络策略：解析全部地址后固定连接 IP，阻止 DNS 重绑定和代理绕过。"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit

import httpx


class BrowserError(Exception):
    """只携带固定错误证据，不回显请求、响应或底层网络异常。"""

    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(message)


def validate_url(value: str) -> str:
    """仅准许标准端口的公开 HTTP(S)，拒绝凭据、片段和歧义 URL。"""
    try:
        if not isinstance(value, str) or len(value) > 2048 or any(ord(c) <= 32 for c in value) or "\\" in value:
            raise ValueError()
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError()
        if parsed.fragment or parsed.port not in {None, 80 if parsed.scheme == "http" else 443}:
            raise ValueError()
        host = parsed.hostname.rstrip(".").encode("idna").decode("ascii").lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")) or "." not in host:
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not public_ip(str(address)):
            raise ValueError()
        return str(httpx.URL(urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))))
    except (ValueError, UnicodeError, httpx.InvalidURL):
        raise BrowserError("URL_BLOCKED", "只允许无凭据、标准端口的公开 HTTP(S) 地址") from None


def public_ip(value: str) -> bool:
    address = ipaddress.ip_address(value)
    # 额外拒绝 IPv4 映射和隧道形式，避免不同网络栈对地址分类产生歧义。
    return address.is_global and not address.is_multicast and not getattr(address, "ipv4_mapped", None) and not getattr(address, "sixtofour", None) and not getattr(address, "teredo", None)


async def resolve(host: str, port: int) -> list[str]:
    records = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(record[4][0] for record in records))


def origin(url: str) -> tuple[str, str, int]:
    parsed = httpx.URL(url)
    return parsed.scheme, parsed.host, parsed.port or (443 if parsed.scheme == "https" else 80)


class SafeHTTP:
    """所有网页流量经过此出口；每次新建无 Cookie 客户端且禁用环境代理。"""

    def __init__(self, *, transport=None, resolver=resolve):
        self.transport, self.resolver = transport, resolver

    async def fetch(self, url: str, *, limit: int, method: str = "GET", payload=None) -> tuple[int, dict, bytes]:
        target = httpx.URL(validate_url(url))
        addresses = await self.resolver(target.host, target.port or (443 if target.scheme == "https" else 80))
        if not addresses or any(not public_ip(address) for address in addresses):
            raise BrowserError("ADDRESS_BLOCKED", "DNS 解析包含非公开地址")
        # 保留 Host 和 TLS SNI/证书主机名，但连接已验证的 IP；不会二次解析原主机。
        pinned = target.copy_with(host=addresses[0])
        headers = {"host": target.netloc.decode("ascii"), "accept-encoding": "identity", "user-agent": "Orvia-ReadOnly/0.1"}
        async with httpx.AsyncClient(transport=self.transport, trust_env=False, follow_redirects=False, timeout=5) as client:
            async with client.stream(method, pinned, headers=headers, json=payload,
                                     extensions={"sni_hostname": target.host}) as response:
                if response.headers.get("content-encoding", "identity").lower() not in {"", "identity"}:
                    raise BrowserError("ENCODING_BLOCKED", "拒绝压缩响应以保持响应内存上限")
                data = bytearray()
                async for chunk in response.aiter_raw():
                    if len(data) + len(chunk) > limit:
                        raise BrowserError("RESPONSE_TOO_LARGE", "响应超过字节上限，未返回不完整正文")
                    data.extend(chunk)
                return response.status_code, dict(response.headers), bytes(data)
