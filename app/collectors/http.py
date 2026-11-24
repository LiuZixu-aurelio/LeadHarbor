"""采集用 HTTP 客户端与限速工具。

规则（见 AGENTS.md）：所有网络请求必须限速、超时、可重试、遵守 robots.txt。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_client(extra_headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    headers = {"User-Agent": settings.crawler_user_agent}
    if extra_headers:
        headers.update(extra_headers)
    return httpx.AsyncClient(
        headers=headers,
        timeout=settings.crawler_timeout_seconds,
        follow_redirects=True,
    )


@asynccontextmanager
async def acquire_client(
    extra_headers: dict[str, str] | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    """复用客户端的上下文管理器。"""
    client = build_client(extra_headers)
    try:
        yield client
    finally:
        await client.aclose()


class RateLimiter:
    """全局最小间隔限速器：保证相邻请求间隔 >= 1/rps 秒。"""

    def __init__(self, requests_per_second: float) -> None:
        self._interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            delay = self._last + self._interval - now
            if delay > 0:
                await asyncio.sleep(delay)
                now = loop.time()
            self._last = now


async def fetch_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    retries: int = 3,
    backoff: float = 1.5,
    **kwargs: object,
) -> httpx.Response:
    """带指数退避的请求；仅对 5xx/网络异常重试，4xx 直接返回。"""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = await client.request(method, url, **kwargs)  # type: ignore[arg-type]
            if resp.status_code >= 500 and attempt < retries:
                raise httpx.HTTPStatusError(
                    "server error", request=resp.request, response=resp
                )
            return resp
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            logger.warning(
                "request failed (attempt %d/%d): %s %s -> %s",
                attempt,
                retries,
                method,
                url,
                exc,
            )
            if attempt < retries:
                await asyncio.sleep(backoff**attempt)
    assert last_exc is not None
    raise last_exc


def can_fetch(url: str) -> bool:
    """基于 robots.txt 判断是否允许抓取。失败时保守放行首页判定。"""
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:  # noqa: BLE001 - robots 不可达时不阻塞
        return True
    return parser.can_fetch(settings.crawler_user_agent, url)
