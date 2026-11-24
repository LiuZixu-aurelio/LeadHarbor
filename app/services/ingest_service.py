"""采集编排：collector → lead_raw → normalize → dedupe → enrich → score → company/contact。

单条线索独立提交，失败不污染整批：
- 处理成功/重复/失败都会在 lead_raw 留痕。
- 出现 DB 异常时先 rollback，再单独补写失败记录。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.registry import get_collector
from app.core.logging import get_logger
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import CompanyStatus, LeadStatus
from app.models.lead_raw import LeadRaw
from app.pipeline.dedupe import DedupeSet
from app.pipeline.enrich import Enricher
from app.pipeline.normalize import normalize_lead
from app.pipeline.score import HeuristicScorer, ScoreProfile
from app.schemas.collect import CollectResult
from app.schemas.lead import RawLead

logger = get_logger(__name__)

QUALIFIED_THRESHOLD = 60


def _record_raw(
    session: AsyncSession,
    source: str,
    query: dict[str, Any],
    raw: RawLead,
    status: LeadStatus,
    error: str | None = None,
) -> None:
    session.add(
        LeadRaw(
            source=source,
            query=query,
            payload=raw.model_dump(),
            status=status,
            error=error,
        )
    )


async def _domain_exists(session: AsyncSession, domain: str) -> bool:
    result = await session.scalar(select(Company.id).where(Company.domain == domain))
    return result is not None


async def _upsert_company(session: AsyncSession, lead: RawLead, score: int) -> Company:
    existing = None
    if lead.domain:
        existing = await session.scalar(
            select(Company).where(Company.domain == lead.domain)
        )
    if existing is not None:
        # 已有公司：补齐缺失的联系电话/地址
        if not existing.phone and lead.phone:
            existing.phone = lead.phone
        if not existing.address and lead.address:
            existing.address = lead.address
        return existing

    company = Company(
        name=lead.name or lead.domain or "Unknown",
        domain=lead.domain,
        website=lead.website,
        country=lead.country,
        industry=lead.industry,
        phone=lead.phone,
        address=lead.address,
        source=lead.source,
        ai_score=score,
        status=(
            CompanyStatus.QUALIFIED if score >= QUALIFIED_THRESHOLD else CompanyStatus.LEAD
        ),
    )
    session.add(company)
    await session.flush()
    return company


async def _upsert_contact(
    session: AsyncSession, company: Company, lead: RawLead
) -> Contact | None:
    if not lead.email and not lead.phone:
        return None
    existing = None
    if lead.email:
        existing = await session.scalar(
            select(Contact).where(
                Contact.company_id == company.id, Contact.email == lead.email
            )
        )
    elif lead.phone:
        existing = await session.scalar(
            select(Contact).where(
                Contact.company_id == company.id, Contact.phone == lead.phone
            )
        )
    if existing is not None:
        return existing
    contact = Contact(
        company_id=company.id,
        name=lead.name,
        title=lead.title,
        email=lead.email,
        phone=lead.phone,
        source=lead.source,
    )
    session.add(contact)
    return contact


async def run_collection(
    session: AsyncSession,
    source: str,
    query: dict[str, Any],
    max_items: int = 20,
    profile: ScoreProfile | None = None,
    enricher: Enricher | None = None,
) -> CollectResult:
    """执行一次采集并入库。"""
    collector = get_collector(source)
    collector_query = {**query, "max_items": max_items}
    seen = DedupeSet()
    scorer = HeuristicScorer(profile or ScoreProfile())

    fetched = ingested = duplicates = failed = 0

    async for raw in collector.collect(collector_query):
        fetched += 1
        try:
            lead = normalize_lead(raw)

            if not seen.add(lead) or (
                lead.domain and await _domain_exists(session, lead.domain)
            ):
                _record_raw(session, source, collector_query, raw, LeadStatus.DUPLICATE)
                await session.commit()
                duplicates += 1
                continue

            if enricher is not None:
                lead = await enricher.enrich(lead)

            score = scorer.score(lead)
            company = await _upsert_company(session, lead, score)
            await _upsert_contact(session, company, lead)
            _record_raw(session, source, collector_query, raw, LeadStatus.PROCESSED)
            await session.commit()
            ingested += 1
        except Exception as exc:  # noqa: BLE001 - 单条失败不影响其余
            logger.warning("ingest failed (%s): %s", source, exc)
            failed += 1
            await session.rollback()
            try:
                _record_raw(
                    session,
                    source,
                    collector_query,
                    raw,
                    LeadStatus.FAILED,
                    str(exc)[:500],
                )
                await session.commit()
            except Exception:  # noqa: BLE001
                await session.rollback()

    logger.info(
        "collection done source=%s fetched=%d ingested=%d dup=%d failed=%d",
        source,
        fetched,
        ingested,
        duplicates,
        failed,
    )
    return CollectResult(
        source=source,
        fetched=fetched,
        ingested=ingested,
        duplicates=duplicates,
        failed=failed,
    )
