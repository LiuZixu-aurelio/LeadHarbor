"""Yandex Maps Geosearch 官方 API 采集器。

Yandex 在俄语区和中亚有较好覆盖。需要 YANDEX_GEOSEARCH_API_KEY，
不抓取 Yandex 页面，使用官方 JSON API。
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

_REGION_COORDS = {
    "KZ": (43.2389, 76.8897),
    "UZ": (41.2995, 69.2401),
    "KG": (42.8746, 74.5698),
    "TJ": (38.5598, 68.7870),
    "TM": (37.9601, 58.3261),
    "RU": (55.7558, 37.6173),
}


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    except ValueError:
        return None
    return host.removeprefix("www.").split(":", 1)[0] or None


def _contact(item: dict[str, Any], kind: str) -> str | None:
    for prop in item.get("properties", {}).get("CompanyMetaData", {}).get("Phones", []) or []:
        if kind == "phone" and prop.get("formatted"):
            return prop["formatted"]
    return None


def parse_yandex_response(data: dict[str, Any], region: str | None = None) -> list[RawLead]:
    """纯函数：解析 Yandex GeoObjectCollection。"""
    leads: list[RawLead] = []
    for feature in data.get("features", []) or []:
        props = feature.get("properties") or {}
        meta = props.get("CompanyMetaData") or {}
        name = meta.get("name") or props.get("name")
        if not name:
            continue
        url = meta.get("url")
        categories = meta.get("Categories") or []
        category = categories[0] if categories and isinstance(categories[0], dict) else {}
        industry = category.get("name")
        leads.append(
            RawLead(
                source="yandex_maps",
                name=name,
                domain=_domain(url),
                website=url,
                phone=_contact(feature, "phone"),
                country=region,
                address=meta.get("address") or props.get("description"),
                industry=industry,
                raw=feature,
            )
        )
    return leads


class YandexMapsCollector(BaseCollector):
    source_name = "yandex_maps"
    label = "Yandex 地图"
    requires_key = "YANDEX_GEOSEARCH_API_KEY"
    default_region = "KZ"
    supported_regions = ["KZ", "UZ", "KG", "TJ", "TM", "RU"]

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.yandex_geosearch_api_key
        self._limiter = RateLimiter(settings.crawler_requests_per_second)

    async def collect(self, query: dict[str, Any]) -> AsyncIterator[RawLead]:
        if not self._api_key:
            raise RuntimeError(
                "YANDEX_GEOSEARCH_API_KEY 未配置，无法使用 yandex_maps 采集器"
            )
        text_query = str(query.get("text_query") or query.get("q") or "").strip()
        if not text_query:
            raise ValueError("yandex_maps 采集需要 query['text_query']")
        region = str(query.get("region") or settings.default_region).upper()
        coords = _REGION_COORDS.get(region)
        if not coords:
            raise ValueError(f"yandex_maps 暂不支持区域 {region!r}")
        max_items = min(50, int(query.get("max_items", 20)))
        params: dict[str, Any] = {
            "apikey": self._api_key,
            "text": text_query,
            "lang": query.get("language", "ru_RU"),
            "ll": f"{coords[1]},{coords[0]}",
            "type": "biz",
            "results": max_items,
            "skip": int(query.get("skip", 0)),
        }
        await self._limiter.wait()
        async with acquire_client() as client:
            resp = await fetch_with_retry(
                client, "GET", settings.yandex_geosearch_url, params=params
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Yandex Maps 返回 HTTP {resp.status_code}: {resp.text[:200]}"
                )
            for lead in parse_yandex_response(resp.json(), region):
                yield lead
