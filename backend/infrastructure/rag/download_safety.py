"""出站目标逐跳校验并绑定已校验 IP；不信任环境代理或响应自动扩白名单。"""

import asyncio
import ipaddress
import json
import logging
import socket
from urllib.parse import urljoin, urlsplit

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend

from backend.application.errors import PermanentTaskError, TransientTaskError

# HTTP库的默认INFO/DEBUG会输出能力URL；各调用只记录应用层安全错误码。
for _name in ("httpx", "httpcore"):
    logging.getLogger(_name).setLevel(logging.CRITICAL + 1)


class PublicNetworkBackend(httpcore.AsyncNetworkBackend):
    def __init__(self):
        self.backend = AutoBackend()

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        addresses = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
        ips = list(dict.fromkeys(item[4][0] for item in addresses))
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise PermanentTaskError("OUTBOUND_TARGET_UNSAFE", "出站地址不在公网允许范围")
        # TLS 在 httpcore 后续仍以原请求 hostname 做 SNI／证书校验；只固定 TCP 地址。
        return await self.backend.connect_tcp(ips[0], port, timeout, local_address, socket_options)

    async def connect_unix_socket(self, *args, **kwargs):
        raise PermanentTaskError("OUTBOUND_TARGET_UNSAFE", "不允许本地socket")

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


class SafeHTTP:
    def __init__(self, hosts, *, transport=None):
        self.hosts = frozenset(hosts)
        if not self.hosts or any("*" in host or "/" in host or ":" in host for host in self.hosts):
            raise PermanentTaskError("OUTBOUND_TARGET_UNSAFE", "出站域白名单无效")
        if transport is None:
            transport = httpx.AsyncHTTPTransport(retries=0, trust_env=False)
            transport._pool = httpcore.AsyncConnectionPool(network_backend=PublicNetworkBackend())
        self.transport = transport

    def validate(self, url):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in self.hosts
            or parsed.port not in {None, 443}
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            raise PermanentTaskError("OUTBOUND_TARGET_UNSAFE", "目标URL不在受信范围")

    async def request(
        self,
        method,
        url,
        *,
        headers=None,
        json_body=None,
        content=None,
        max_bytes=2 * 1024**2,
        timeout=30,
    ):
        self.validate(url)
        try:
            async with asyncio.timeout(timeout):
                async with httpx.AsyncClient(
                    transport=self.transport,
                    trust_env=False,
                    follow_redirects=False,
                    timeout=httpx.Timeout(timeout, connect=min(5, timeout)),
                ) as client:
                    for hop in range(4):
                        self.validate(url)
                        async with client.stream(
                            method, url, headers=headers, json=json_body, content=content
                        ) as response:
                            if response.status_code in {301, 302, 303, 307, 308}:
                                # 非幂等请求不自动跟随重放；GET逐跳验证，跨origin清凭据。
                                if (
                                    method != "GET"
                                    or hop == 3
                                    or "location" not in response.headers
                                ):
                                    raise PermanentTaskError(
                                        "OUTBOUND_REDIRECT_UNSAFE", "重定向不受支持"
                                    )
                                next_url = urljoin(url, response.headers["location"])
                                if urlsplit(url).netloc != urlsplit(next_url).netloc:
                                    headers = None
                                url = next_url
                                continue
                            data = bytearray()
                            async for block in response.aiter_bytes():
                                data.extend(block)
                                if len(data) > max_bytes:
                                    raise PermanentTaskError(
                                        "UPSTREAM_RESPONSE_LIMIT", "上游响应超过上限"
                                    )
                            return response.status_code, bytes(data)
        except (httpx.HTTPError, TimeoutError, OSError):
            raise TransientTaskError("UPSTREAM_TEMPORARY_UNAVAILABLE", "上游网络暂不可用") from None


def decode_json(content, code="UPSTREAM_PROTOCOL_INVALID"):
    try:
        value = json.loads(content)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise PermanentTaskError(code, "上游响应协议无效") from None
