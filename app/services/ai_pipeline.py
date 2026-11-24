"""AI 一键采集编排：Google 搜索发现候选页面 URL，再交给 ai_extractor 抽取入库。"""

from __future__ import annotations

from typing import Any

from app.collectors.registry import get_collector
from app.core.logging import get_logger

logger = get_logger(__name__)


async def discover_urls(
    keyword: str, region: str, max_urls: int, language: str = "en"
) -> list[str]:
    """用 Google 搜索按关键词找出候选网页 URL（去重、限量）。"""
    search = get_collector("google_search")
    urls: list[str] = []
    seen: set[str] = set()
    async for lead in search.collect(
        {
            "text_query": keyword,
            "region": region,
            "language": language,
            "max_items": max_urls,
        }
    ):
        url = lead.website or lead.domain
        if not url:
            continue
        if url not in seen:
            seen.add(url)
            urls.append(url)
        if len(urls) >= max_urls:
            break
    return urls


async def run_pipeline(
    session: Any,
    keyword: str,
    region: str,
    max_pages: int,
    max_items_per_page: int,
    language: str = "en",
) -> dict[str, Any]:
    """发现页面后逐页调用 ai_extractor，复用标准入库流程。"""
    from app.pipeline.enrich import WebsiteEmailEnricher
    from app.services.ingest_service import run_collection

    urls = await discover_urls(keyword, region, max_pages, language)
    totals = {"fetched": 0, "ingested": 0, "duplicates": 0, "failed": 0}
    processed = 0
    for url in urls:
        try:
            result = await run_collection(
                session=session,
                source="ai_extractor",
                query={"urls": [url], "max_items": max_items_per_page},
                max_items=max_items_per_page,
                enricher=WebsiteEmailEnricher(),
            )
            for key in totals:
                totals[key] += getattr(result, key)
            processed += 1
        except Exception as exc:  # noqa: BLE001 - 单页失败继续处理其他页面
            logger.warning("AI pipeline page failed url=%s: %s", url, exc)
            totals["failed"] += 1
    return {
        "keyword": keyword,
        "region": region,
        "pages_found": len(urls),
        "pages_processed": processed,
        "urls": urls,
        **totals,
    }
