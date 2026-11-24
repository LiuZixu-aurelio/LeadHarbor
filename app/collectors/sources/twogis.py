"""2GIS（双GIS）采集器：中亚市场首选的地图/商家数据源。

2GIS 在哈萨克斯坦、乌兹别克斯坦、吉尔吉斯斯坦、塔吉克斯坦等地覆盖优于
Google Maps。使用官方 Catalog API（https://catalog.api.2gis.com/3.0/items），
需要 TWOGIS_API_KEY。
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

_SEARCH_URL = "https://catalog.api.2gis.com/3.0/items"
_FIELDS = ",".join(
    [
        "items.name",
        "items.address_name",
        "items.country_code",
        "items.contact_groups",
        "items.external_content",
        "items.rubrics",
        "items.description",
    ]
)

# 各区域搜索中心点（lon, lat），用 point + radius 定位，避免依赖易错的 region_id
REGION_POINTS: dict[str, tuple[float, float]] = {
    "KZ": (76.8897, 43.2389),  # Almaty
    "UZ": (69.2401, 41.2995),  # Tashkent
    "KG": (74.5698, 42.8746),  # Bishkek
    "TJ": (68.7870, 38.5598),  # Dushanbe
    "TM": (58.3261, 37.9601),  # Ashgabat
    "RU": (37.6173, 55.7558),  # Moscow
}
_DEFAULT_RADIUS_M = 50000


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


def _extract_contacts(item: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """从 2GIS contact_groups / external_content 里取官网、邮箱、电话。"""
    website = email = phone = None
    for group in item.get("contact_groups", []) or []:
        for contact in group.get("contacts", []) or []:
            ctype = contact.get("type")
            value = contact.get("value")
            if ctype == "website" and not website:
                website = value
            elif ctype == "email" and not email:
                email = value
            elif ctype in {"phone", "phone_fax"} and not phone:
                phone = value
    # external_content 常见结构：[{"type": "website"/"email", "url": ...}]
    for extra in item.get("external_content", []) or []:
        etype = (extra.get("type") or "").lower()
        url = extra.get("url") or extra.get("value")
        if not url:
            continue
        if etype == "website" and not website:
            website = url
        elif etype == "email" and not email:
            email = url
    return website, email, phone


def _extract_industry(item: dict[str, Any]) -> str | None:
    rubrics = item.get("rubrics") or []
    if rubrics and isinstance(rubrics, list):
        name = rubrics[0].get("name")
        if name:
            return name
    return None


def check_twogis_meta(data: dict[str, Any]) -> None:
    """2GIS 在鉴权/参数错误时仍返回 HTTP 200，错误放在 meta 里，需要显式抛出。"""
    meta = data.get("meta") or {}
    code = meta.get("code")
    error = meta.get("error")
    if error or (code is not None and int(code) != 200):
        message = ""
        if isinstance(error, dict):
            message = error.get("message") or error.get("type") or ""
        elif error:
            message = str(error)
        raise RuntimeError(f"2GIS API 错误 code={code}: {message or '未知错误'}")


def parse_twogis_response(data: dict[str, Any], source: str = "2gis") -> list[RawLead]:
    """纯函数：把 2GIS Catalog API 返回体解析为 RawLead 列表（便于单测）。"""
    leads: list[RawLead] = []
    items = (data.get("result") or {}).get("items", []) or []
    for item in items:
        website, email, phone = _extract_contacts(item)
        leads.append(
            RawLead(
                source=source,
                name=item.get("name"),
                domain=_extract_domain(website),
                website=website,
                email=email,
                phone=phone,
                country=item.get("country_code"),
                address=item.get("address_name"),
                industry=_extract_industry(item),
                raw=item,
            )
        )
    return leads


class TwoGisCollector(BaseCollector):
    source_name = "2gis"
    label = "2GIS"
    requires_key = "TWOGIS_API_KEY"
    default_region = "KZ"
    supported_regions = ["KZ", "UZ", "KG", "TJ", "TM", "RU"]

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.twogis_api_key
        self._limiter = RateLimiter(settings.crawler_requests_per_second)

    async def collect(self, query: dict[str, Any]) -> AsyncIterator[RawLead]:
        if not self._api_key:
            raise RuntimeError("TWOGIS_API_KEY 未配置，无法使用 2gis 采集器")

        text_query = query.get("text_query") or query.get("q")
        if not text_query:
            raise ValueError("2gis 采集需要 query['text_query']")

        max_items = int(query.get("max_items", 20))
        region = str(query.get("region") or settings.default_region).upper()

        params: dict[str, Any] = {
            "q": text_query,
            "fields": _FIELDS,
            "page_size": min(50, max_items),
            "key": self._api_key,
        }
        # 显式 region_id 优先；否则用坐标 + 半径定位，避免写死错误的 region_id
        explicit_region_id = query.get("region_id")
        point = REGION_POINTS.get(region)
        if explicit_region_id:
            params["region_id"] = str(explicit_region_id)
        elif point is not None:
            params["point"] = f"{point[0]},{point[1]}"
            params["radius"] = int(query.get("radius", _DEFAULT_RADIUS_M))

        yielded = 0
        page = max(1, int(query.get("page", 1)))
        async with acquire_client() as client:
            while yielded < max_items:
                await self._limiter.wait()
                req = dict(params)
                req["page"] = page
                resp = await fetch_with_retry(client, "GET", _SEARCH_URL, params=req)
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"2GIS 返回 HTTP {resp.status_code}: {resp.text[:200]}"
                    )

                data = resp.json()
                check_twogis_meta(data)
                batch = parse_twogis_response(data)
                if not batch:
                    break
                for lead in batch:
                    if yielded >= max_items:
                        break
                    yield lead
                    yielded += 1

                total = (data.get("result") or {}).get("total")
                if total is not None and yielded >= int(total):
                    break
                page += 1
