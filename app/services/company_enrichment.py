"""客户详情多渠道联系方式补全。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.registry import get_collector
from app.collectors.sources.website import WebsiteCollector
from app.core.logging import get_logger
from app.models.company import Company
from app.models.contact import Contact
from app.schemas.lead import RawLead

logger = get_logger(__name__)

_SEARCH_SOURCES = ("google_search", "google_places", "2gis", "yandex_maps", "openstreetmap")


def _text(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _relevant(company: Company, lead: RawLead) -> bool:
    """避免把同名搜索结果旁边的其它公司联系方式合并进来。"""
    if company.domain and lead.domain:
        company_domain = company.domain.lower()
        lead_domain = lead.domain.lower()
        return company_domain in lead_domain or lead_domain in company_domain
    company_words = {w for w in company.name.lower().split() if len(w) >= 3}
    lead_words = set((lead.name or "").lower().split())
    return not company_words or bool(company_words & lead_words)


async def _merge_lead(session: AsyncSession, company: Company, lead: RawLead) -> dict[str, bool]:
    """只补空字段，不覆盖已有数据。"""
    found = {"email": bool(lead.email), "phone": bool(lead.phone), "address": bool(lead.address)}
    if not company.website and lead.website:
        company.website = lead.website
    if not company.domain and lead.domain:
        company.domain = lead.domain
    if not company.phone and lead.phone:
        company.phone = lead.phone
    if not company.address and lead.address:
        company.address = lead.address
    if not company.industry and lead.industry:
        company.industry = lead.industry
    session.add(company)

    if lead.email or lead.phone:
        duplicate = None
        if lead.email:
            duplicate = await session.scalar(
                select(Contact).where(Contact.company_id == company.id, Contact.email == lead.email)
            )
        if duplicate is None and lead.phone:
            duplicate = await session.scalar(
                select(Contact).where(Contact.company_id == company.id, Contact.phone == lead.phone)
            )
        if duplicate is None:
            session.add(
                Contact(
                    company_id=company.id,
                    name=company.name,
                    email=lead.email,
                    phone=lead.phone,
                    source=lead.source,
                )
            )
    return found


async def enrich_company_from_channels(session: AsyncSession, company: Company) -> dict[str, Any]:
    """依次访问官网和已配置的搜索/地图渠道，合并所有新联系方式。"""
    attempts: list[dict[str, Any]] = []
    totals = {"email": 0, "phone": 0, "address": 0}

    # 官网优先：沿着 contact/about/support 等链接深度抓取，最多 8 页。
    website_url = company.website or company.domain
    if website_url:
        try:
            website_results = 0
            async for website_lead in WebsiteCollector().collect(
                {"urls": [website_url], "max_pages_per_site": 20}
            ):
                result = await _merge_lead(session, company, website_lead)
                website_results += 1
                for key in totals:
                    totals[key] += int(result.get(key, False))
            attempts.append(
                {"source": "website", "status": "ok", "pages": 20, "results": website_results}
            )
        except Exception as exc:  # noqa: BLE001 - 官网失败后继续其它渠道
            logger.warning("deep website enrichment failed: %s", exc)
            attempts.append({"source": "website", "status": "failed", "message": str(exc)[:180]})
    else:
        attempts.append({"source": "website", "status": "skipped", "message": "没有官网或域名"})

    query = {"text_query": company.name, "region": company.country or "KZ", "max_items": 5}
    for source in _SEARCH_SOURCES:
        try:
            collector = get_collector(source)
            found_count = 0
            async for lead in collector.collect(query):
                if not _relevant(company, lead):
                    continue
                found = await _merge_lead(session, company, lead)
                found_count += 1
                for key in totals:
                    totals[key] += int(found.get(key, False))
            attempts.append({"source": source, "status": "ok", "results": found_count})
        except (RuntimeError, ValueError) as exc:
            attempts.append({"source": source, "status": "skipped", "message": str(exc)[:180]})
        except Exception as exc:  # noqa: BLE001 - 单渠道故障不阻塞其它渠道
            logger.warning("company enrichment source=%s failed: %s", source, exc)
            attempts.append({"source": source, "status": "failed", "message": str(exc)[:180]})

    await session.commit()
    return {"found": totals, "attempts": attempts}
