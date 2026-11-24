"""Wikidata SPARQL 采集器：完全免费，按国家+行业查公司实体。

无 API key，依赖公共 Wikidata Query Service（WDQS），有使用限制（每秒并发不应超过 1）。
适合补充公司名称、官网、行业、成立日期等，作为高质量种子数据。

注意：公共端点不可靠；大规模使用建议自建 Wikidata Blob/镜像。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.collectors.base import BaseCollector
from app.collectors.http import RateLimiter, acquire_client, fetch_with_retry
from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.lead import RawLead

logger = get_logger(__name__)

_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

_COUNTRY_QID = {
    "KZ": "Q233",   # Kazakhstan
    "UZ": "Q244",   # Uzbekistan
    "KG": "Q817",   # Kyrgyzstan
    "TJ": "Q854",   # Tajikistan
    "TM": "Q878",   # Turkmenistan
    "RU": "Q159",   # Russia
}

_INDUSTRY_QID = {
    "电子": "Q11424",        # electronics industry
    "制造业": "Q8054",       # manufacturing
    "农业": "Q39792",        # agriculture
    "贸易": "Q190424",       # trade
    "软件": "Q9108",         # software
    "能源": "Q131507",       # energy industry
    "汽车": "Q2413",         # automotive industry
}


def parse_wikidata_bindings(bindings: list[dict[str, Any]], region: str | None) -> list[RawLead]:
    """纯函数：把 SPARQL JSON 结果解析为 RawLead。"""
    leads: list[RawLead] = []
    seen: set[str] = set()
    for row in bindings:
        name = (row.get("itemLabel") or {}).get("value")
        if not name or name in seen:
            continue
        seen.add(name)
        website = (row.get("website") or {}).get("value")
        industry = (row.get("industryLabel") or {}).get("value")
        inception = (row.get("inception") or {}).get("value")
        domain = None
        if website:
            from urllib.parse import urlparse

            try:
                host = urlparse(website if "://" in website else f"https://{website}").netloc.lower()
                domain = host.removeprefix("www.").split(":", 1)[0] or None
            except ValueError:
                domain = None
        leads.append(
            RawLead(
                source="wikidata",
                name=name,
                domain=domain,
                website=website,
                country=region,
                industry=industry,
                raw={"inception": inception},
            )
        )
    return leads


class WikidataCollector(BaseCollector):
    source_name = "wikidata"
    label = "Wikidata（免费）"
    requires_key = ""
    default_region = "KZ"
    supported_regions = ["KZ", "UZ", "KG", "TJ", "TM", "RU", "US", "GB", "DE"]

    def __init__(self) -> None:
        self._limiter = RateLimiter(0.5)  # WDQS 严格限速：1 req/s 建议 0.5 安全

    async def collect(self, query: dict[str, Any]) -> AsyncIterator[RawLead]:
        text_query = str(query.get("text_query") or query.get("q") or "").strip()
        region = str(query.get("region") or settings.default_region).upper()
        max_items = min(50, int(query.get("max_items", 20)))

        # 用关键词匹配公司名称、别名或标签；限定 country（P17）。
        country_qid = _COUNTRY_QID.get(region)
        if not country_qid:
            raise ValueError(f"wikidata 暂不支持区域 {region!r}")

        sparql = f"""SELECT ?item ?itemLabel ?website ?industryLabel ?inception WHERE {{
  ?item wdt:P31/wdt:P279* wd:Q4830453 .
  ?item wdt:P17 wd:{country_qid} .
  OPTIONAL {{ ?item wdt:P856 ?website . }}
  OPTIONAL {{ ?item wdt:P452 ?industry . }}
  OPTIONAL {{ ?item wdt:P571 ?inception . }}
  FILTER(CONTAINS(LCASE(?itemLabel), "{text_query.lower()}"))
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,ru". }}
}} LIMIT {max_items} OFFSET {max(0, int(query.get("skip", 0)))}"""

        params = {"query": sparql, "format": "json"}
        headers = {
            "Accept": "application/sparql-results+json",
            "User-Agent": settings.crawler_user_agent,
        }
        await self._limiter.wait()
        async with acquire_client() as client:
            resp = await fetch_with_retry(
                client, "GET", _SPARQL_ENDPOINT, params=params, headers=headers
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Wikidata SPARQL 返回 HTTP {resp.status_code}: {resp.text[:200]}"
                )
            data = resp.json()
        for lead in parse_wikidata_bindings(data.get("results", {}).get("bindings", []), region):
            yield lead
