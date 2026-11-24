"""Google Places (New) 采集器：Text Search，按关键词 + 地区找公司。

官方文档：https://developers.google.com/maps/documentation/places/web-service/text-search
使用 Places API (v1)，需要 GOOGLE_PLACES_API_KEY。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse

from app.collectors.base import BaseCollector
from app.collectors.http import RateLimiter, acquire_client, fetch_with_retry
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.lead import RawLead

logger = get_logger(__name__)

_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.addressComponents",
        "places.primaryTypeDisplayName",
        "nextPageToken",
    ]
)


def extract_domain(url: str | None) -> str | None:
    """从 URL 提取裸域名（去掉协议、www、路径）。"""
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return None
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _extract_country(place: dict[str, Any]) -> str | None:
    for comp in place.get("addressComponents", []) or []:
        if "country" in comp.get("types", []):
            return comp.get("shortText") or comp.get("longText")
    return None


def _extract_industry(place: dict[str, Any]) -> str | None:
    ptype = place.get("primaryTypeDisplayName")
    if isinstance(ptype, dict):
        return ptype.get("text")
    return None


def parse_places_response(data: dict[str, Any], source: str = "google_places") -> list[RawLead]:
    """纯函数：把 Places API 返回体解析为 RawLead 列表（便于单测）。"""
    leads: list[RawLead] = []
    for place in data.get("places", []) or []:
        display = place.get("displayName") or {}
        name = display.get("text") if isinstance(display, dict) else None
        website = place.get("websiteUri")
        phone = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
        leads.append(
            RawLead(
                source=source,
                name=name,
                domain=extract_domain(website),
                website=website,
                phone=phone,
                country=_extract_country(place),
                industry=_extract_industry(place),
                address=place.get("formattedAddress"),
                raw=place,
            )
        )
    return leads


class GooglePlacesCollector(BaseCollector):
    source_name = "google_places"
    label = "Google Places"
    requires_key = "GOOGLE_PLACES_API_KEY"
    default_region = "KZ"
    supported_regions = ["KZ", "UZ", "KG", "TJ", "TM", "DE", "US", "GB", "AE", "TR"]

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.google_places_api_key
        self._limiter = RateLimiter(settings.crawler_requests_per_second)

    async def collect(self, query: dict[str, Any]) -> AsyncIterator[RawLead]:
        if not self._api_key:
            raise RuntimeError(
                "GOOGLE_PLACES_API_KEY 未配置，无法使用 google_places 采集器"
            )

        text_query = query.get("text_query")
        if not text_query:
            raise ValueError("google_places 采集需要 query['text_query']")

        max_items = int(query.get("max_items", 20))
        page_size = min(20, max_items)
        body: dict[str, Any] = {
            "textQuery": text_query,
            "pageSize": page_size,
            "languageCode": query.get("language", "en"),
        }
        if region := query.get("region"):
            body["regionCode"] = region

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": _FIELD_MASK,
        }

        yielded = 0
        page_token: str | None = None
        async with acquire_client() as client:
            while yielded < max_items:
                await self._limiter.wait()
                payload = dict(body)
                if page_token:
                    payload["pageToken"] = page_token

                resp = await fetch_with_retry(
                    client, "POST", _SEARCH_URL, headers=headers, json=payload
                )
                if resp.status_code != 200:
                    body = resp.text[:300]
                    if page_token is None:
                        raise RuntimeError(
                            f"Google Places 返回 HTTP {resp.status_code}: {body}"
                        )
                    logger.error(
                        "google_places HTTP %s: %s", resp.status_code, body
                    )
                    break

                data = resp.json()
                if isinstance(data, dict) and data.get("error") and page_token is None:
                    err = data["error"]
                    msg = err.get("message") if isinstance(err, dict) else str(err)
                    raise RuntimeError(f"Google Places 错误: {msg}")
                for lead in parse_places_response(data):
                    if yielded >= max_items:
                        break
                    yield lead
                    yielded += 1

                page_token = data.get("nextPageToken")
                if not page_token:
                    break
                # Places 分页 token 需要短暂延迟后生效
                await asyncio.sleep(2)
