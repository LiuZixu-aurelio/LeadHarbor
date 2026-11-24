"""OpenCorporates 公司注册数据采集器：全球公司登记信息，中亚覆盖较好。

免费额度需注册获取 API Token（https://api.opencorporates.com）。
查询公司注册信息：名称、注册号、注册地址、成立日期、行业、公司类型、注册链接。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlencode, urlparse

from app.collectors.base import BaseCollector
from app.collectors.http import RateLimiter, acquire_client, fetch_with_retry
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.lead import RawLead

logger = get_logger(__name__)

_SEARCH_URL = "https://api.opencorporates.com/v0.4/companies/search"
_JURISDICTION_CODES = {
    "KZ": "kz",
    "UZ": "uz",
    "KG": "kg",
    "TJ": "tj",
    "TM": "tm",
    "RU": "ru",
    "US": "us",
    "GB": "gb",
    "DE": "de",
}


def parse_opencorporates_response(
    data: dict[str, Any], source: str = "opencorporates"
) -> list[RawLead]:
    """纯函数：把 OpenCorporates 返回体解析为 RawLead（便于单测）。"""
    leads: list[RawLead] = []
    companies = ((data.get("results") or {}).get("companies") or [])
    for item in companies:
        company = item.get("company") or {}
        name = company.get("name")
        if not name:
            continue
        oc = company.get("opencorporates_url") or company.get("uri")
        website = company.get("website_url") or company.get("homepage_url")
        address = company.get("registered_address")
        incorporated = company.get("incorporation_date")
        industry = None
        codes = company.get("industry_codes") or []
        if codes and isinstance(codes, list):
            first = codes[0]
            if isinstance(first, dict):
                industry = first.get("name") or first.get("code")
        raw: dict[str, Any] = {
            "opencorporates_url": oc,
            "company_number": company.get("company_number"),
            "company_type": company.get("company_type"),
            "incorporation_date": incorporated,
            "registered_address": address,
            "jurisdiction_code": company.get("jurisdiction_code"),
        }
        domain = None
        if website:
            parsed = urlparse(website if "://" in website else f"https://{website}")
            domain = parsed.netloc.lower().removeprefix("www.").split(":", 1)[0] or None
        jurisdiction = company.get("jurisdiction_code")
        country = jurisdiction.split("_", 1)[0].upper() if jurisdiction else None
        raw_address = company.get("registered_address")
        if isinstance(raw_address, dict):
            address_text = ", ".join(
                str(v) for v in raw_address.values() if v
            ) or None
        else:
            address_text = str(raw_address) if raw_address else None
        leads.append(
            RawLead(
                source=source,
                name=name,
                domain=domain,
                website=website,
                phone=None,
                email=None,
                country=country,
                industry=industry,
                address=address_text,
                raw=raw,
            )
        )
    return leads


class OpenCorporatesCollector(BaseCollector):
    source_name = "opencorporates"
    label = "OpenCorporates"
    requires_key = "OPENCORPORATES_API_TOKEN"
    default_region = "KZ"
    supported_regions = ["KZ", "UZ", "KG", "TJ", "TM", "RU", "US", "GB", "DE"]

    def __init__(self, api_token: str | None = None) -> None:
        self._api_token = api_token or settings.opencorporates_api_token
        self._limiter = RateLimiter(settings.crawler_requests_per_second)

    async def collect(self, query: dict[str, Any]) -> AsyncIterator[RawLead]:
        if not self._api_token:
            raise RuntimeError(
                "OPENCORPORATES_API_TOKEN 未配置，无法使用 opencorporates 采集器"
            )

        text_query = str(query.get("text_query") or query.get("q") or "").strip()
        if not text_query:
            raise ValueError("opencorporates 采集需要 query['text_query']")

        max_items = min(100, int(query.get("max_items", 20)))
        region = str(query.get("region") or settings.default_region).upper()
        jurisdiction = _JURISDICTION_CODES.get(region)
        if not jurisdiction:
            raise ValueError(f"opencorporates 暂不支持区域 {region!r}")

        params: dict[str, Any] = {
            "q": text_query,
            "jurisdiction_code": jurisdiction,
            "per_page": max_items,
            "api_token": self._api_token,
        }

        await self._limiter.wait()
        url = f"{_SEARCH_URL}?{urlencode(params)}"
        async with acquire_client() as client:
            resp = await fetch_with_retry(client, "GET", url)
            if resp.status_code != 200:
                logger.error(
                    "opencorporates HTTP %s: %s", resp.status_code, resp.text[:300]
                )
                raise RuntimeError(
                    f"OpenCorporates 返回 HTTP {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json()
            for lead in parse_opencorporates_response(data):
                yield lead
