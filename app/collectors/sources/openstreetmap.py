"""OpenStreetMap Overpass 采集器：免费开放地图数据中的商家/公司信息。

无需 API key。适合补充中亚本地企业、批发市场、商店和工业设施。
公共 Overpass 实例有使用限制，请控制频率与 max_items；生产环境建议自建实例。
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

_OVERPASS_FALLBACKS = (
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

_COUNTRY_NAMES = {
    "KZ": "Kazakhstan",
    "UZ": "Uzbekistan",
    "KG": "Kyrgyzstan",
    "TJ": "Tajikistan",
    "TM": "Turkmenistan",
    "RU": "Russia",
}


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    except ValueError:
        return None
    return host.removeprefix("www.").split(":", 1)[0] or None


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _first(tags: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = tags.get(key)
        if value:
            return str(value).strip()
    return None


def _osm_address(tags: dict[str, Any]) -> str | None:
    full = tags.get("addr:full")
    if full:
        return str(full).strip()
    parts = [
        tags.get("addr:street"),
        tags.get("addr:housenumber"),
        tags.get("addr:city"),
    ]
    joined = ", ".join(str(p).strip() for p in parts if p)
    return joined or None


def parse_overpass_response(
    data: dict[str, Any], country: str | None = None, source: str = "openstreetmap"
) -> list[RawLead]:
    """纯函数：解析 Overpass elements。"""
    leads: list[RawLead] = []
    for element in data.get("elements", []) or []:
        tags = element.get("tags") or {}
        name = _first(tags, "name", "name:en", "name:ru")
        website = _first(tags, "contact:website", "website", "url")
        email = _first(tags, "contact:email", "email")
        phone = _first(tags, "contact:phone", "phone", "contact:mobile")
        industry = _first(tags, "shop", "craft", "office", "industrial", "amenity")
        if not name and not website:
            continue
        leads.append(
            RawLead(
                source=source,
                name=name,
                domain=_domain(website),
                website=website,
                email=email,
                phone=phone,
                country=country,
                industry=industry,
                address=_osm_address(tags),
                raw=element,
            )
        )
    return leads


class OpenStreetMapCollector(BaseCollector):
    source_name = "openstreetmap"
    label = "OpenStreetMap（免费）"
    requires_key = ""
    default_region = "KZ"
    supported_regions = ["KZ", "UZ", "KG", "TJ", "TM", "RU", "DE", "US", "GB"]

    def __init__(self) -> None:
        self._limiter = RateLimiter(settings.crawler_requests_per_second)

    async def collect(self, query: dict[str, Any]) -> AsyncIterator[RawLead]:
        text_query = str(query.get("text_query") or query.get("q") or "").strip()
        if not text_query:
            raise ValueError("openstreetmap 采集需要 query['text_query']")
        region = str(query.get("region") or settings.default_region).upper()
        country_name = _COUNTRY_NAMES.get(region)
        if not country_name:
            raise ValueError(f"openstreetmap 暂不支持区域 {region!r}")

        max_items = min(200, int(query.get("max_items", 20)))
        # 同时查询 name/shop/office/industrial，避免只命中单一标签。
        needle = _escape(text_query)
        area_name = _escape(country_name)
        overpass = f"""[out:json][timeout:30];
area[\"ISO3166-1\"=\"{region}\"][boundary=\"administrative\"]->.searchArea;
(
  nwr[\"name\"~\"{needle}\",i](area.searchArea);
  nwr[\"shop\"~\"{needle}\",i](area.searchArea);
  nwr[\"office\"~\"{needle}\",i](area.searchArea);
  nwr[\"industrial\"~\"{needle}\",i](area.searchArea);
);
out tags center {max_items};"""
        # area_name 保留在变量中用于可读性，同时 region ISO 是主筛选条件。
        del area_name

        endpoints = [settings.overpass_url]
        endpoints.extend(url for url in _OVERPASS_FALLBACKS if url not in endpoints)
        last_error = ""
        async with acquire_client(
            {"Accept": "application/json", "Referer": "http://localhost"}
        ) as client:
            for endpoint_index, endpoint in enumerate(endpoints):
                await self._limiter.wait()
                # 大多数 Overpass 实例接受 POST 表单；部分 nginx 实例会对其返回 406，
                # 此时切换到 GET 查询参数，并继续尝试备用公共实例。
                resp = await fetch_with_retry(
                    client,
                    "POST",
                    endpoint,
                    data={"data": overpass},
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    },
                    retries=1,
                    timeout=15.0,
                )
                if resp.status_code in {405, 406, 415}:
                    await self._limiter.wait()
                    resp = await fetch_with_retry(
                        client,
                        "GET",
                        endpoint,
                        params={"data": overpass},
                        headers={"Accept": "application/json"},
                        retries=1,
                        timeout=15.0,
                    )
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except ValueError as exc:
                        last_error = f"{endpoint}: 返回非 JSON"
                        logger.warning("overpass invalid JSON from %s: %s", endpoint, exc)
                        continue
                    for lead in parse_overpass_response(data, region):
                        yield lead
                    return
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning(
                    "overpass endpoint %d/%d failed (%s): %s",
                    endpoint_index + 1,
                    len(endpoints),
                    endpoint,
                    last_error,
                )

        raise RuntimeError(f"OpenStreetMap Overpass 请求失败: {last_error}")
