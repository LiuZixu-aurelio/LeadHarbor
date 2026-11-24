"""Google 可编程搜索采集器：直接按关键词找到公司官网/域名。

使用官方 Custom Search JSON API：
  GET https://www.googleapis.com/customsearch/v1
需要 GOOGLE_SEARCH_API_KEY 与 GOOGLE_SEARCH_CX（搜索引擎 ID）。
适合「先搜官网、再交给 website 采集器抓联系方式」的两段式打法。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

from app.collectors.base import BaseCollector
from app.collectors.http import RateLimiter, acquire_client, fetch_with_retry
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.lead import RawLead

logger = get_logger(__name__)

_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
_PAGE_SIZE = 10


def _extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _clean_title(title: str | None) -> str | None:
    """Google 标题常带 " | 官网" 之类后缀，简单截断首个分隔符前内容。"""
    if not title:
        return None
    for sep in (" | ", " - ", " — ", " · "):
        if sep in title:
            head = title.split(sep, 1)[0].strip()
            if head:
                return head
    return title.strip() or None


def parse_google_search_response(
    data: dict[str, Any], source: str = "google_search"
) -> list[RawLead]:
    """纯函数：把 Custom Search JSON 返回体解析为 RawLead（便于单测）。"""
    leads: list[RawLead] = []
    for item in data.get("items", []) or []:
        link = item.get("link")
        leads.append(
            RawLead(
                source=source,
                name=_clean_title(item.get("title")),
                domain=_extract_domain(link),
                website=link,
                industry=None,
                raw=item,
            )
        )
    return leads


class GoogleSearchCollector(BaseCollector):
    source_name = "google_search"
    label = "Google 搜索"
    requires_key = "GOOGLE_SEARCH_API_KEY"
    default_region = "KZ"
    supported_regions = ["KZ", "UZ", "KG", "TJ", "TM", "RU", "DE", "US", "GB", "AE", "TR"]

    def __init__(
        self,
        api_key: str | None = None,
        cx: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.google_search_api_key
        self._cx = cx or settings.google_search_cx
        self._limiter = RateLimiter(settings.crawler_requests_per_second)

    async def collect(self, query: dict[str, Any]) -> AsyncIterator[RawLead]:
        if not self._api_key or not self._cx:
            raise RuntimeError(
                "GOOGLE_SEARCH_API_KEY / GOOGLE_SEARCH_CX 未配置，无法使用 google_search 采集器"
            )

        text_query = query.get("text_query") or query.get("q")
        if not text_query:
            raise ValueError("google_search 采集需要 query['text_query']")

        max_items = int(query.get("max_items", 20))
        region = query.get("region") or settings.default_region
        language = query.get("language", "en")

        yielded = 0
        # Custom Search start 是 1-based，每轮任务传入 skip 后翻到下一页
        start = max(1, int(query.get("skip", 0)) + 1)
        async with acquire_client() as client:
            while yielded < max_items and start <= 91:
                await self._limiter.wait()
                params: dict[str, Any] = {
                    "key": self._api_key,
                    "cx": self._cx,
                    "q": text_query,
                    "num": min(_PAGE_SIZE, max_items - yielded),
                    "start": start,
                    "gl": (region or "").lower() or "kz",
                    "hl": language,
                }
                resp = await fetch_with_retry(
                    client, "GET", _SEARCH_URL, params=params
                )
                if resp.status_code != 200:
                    body = resp.text[:300]
                    if start == 1:
                        raise RuntimeError(
                            f"Google 搜索 API 返回 HTTP {resp.status_code}: {body}"
                        )
                    logger.error(
                        "google_search HTTP %s: %s", resp.status_code, body
                    )
                    break

                data = resp.json()
                if isinstance(data, dict) and data.get("error") and start == 1:
                    err = data["error"]
                    msg = err.get("message") if isinstance(err, dict) else str(err)
                    raise RuntimeError(f"Google 搜索 API 错误: {msg}")
                batch = parse_google_search_response(data)
                if not batch:
                    break
                for lead in batch:
                    if yielded >= max_items:
                        break
                    yield lead
                    yielded += 1

                # 若返回条数不足一页，说明已到末尾
                if len(batch) < params["num"]:
                    break
                start += _PAGE_SIZE
