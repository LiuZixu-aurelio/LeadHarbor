"""客户库导入/导出（CSV）。导出含联系人邮箱/电话；导入按域名或名称去重合并。"""

from __future__ import annotations

import csv
import io
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.company import Company
from app.models.contact import Contact
from app.models.enums import CompanyStatus
from app.pipeline.normalize import normalize_country, normalize_domain, normalize_email

logger = get_logger(__name__)

EXPORT_HEADERS = [
    "name",
    "domain",
    "website",
    "country",
    "industry",
    "phone",
    "address",
    "source",
    "ai_score",
    "status",
    "emails",
    "phones",
]

_VALID_STATUS = {s.value for s in CompanyStatus}


def _split(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.replace("|", ";").split(";") if part.strip()]


async def export_companies_csv(session: AsyncSession) -> str:
    """导出全部客户为 CSV 文本（含 BOM，Excel 友好）。"""
    stmt = select(Company).options(selectinload(Company.contacts)).order_by(Company.id)
    companies = (await session.scalars(stmt)).all()

    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_HEADERS)
    for company in companies:
        emails = sorted({c.email for c in company.contacts if c.email})
        phones = [c.phone for c in company.contacts if c.phone]
        if company.phone:
            phones.insert(0, company.phone)
        # 去重保序
        seen: set[str] = set()
        uniq_phones = [p for p in phones if not (p in seen or seen.add(p))]
        writer.writerow(
            [
                company.name,
                company.domain or "",
                company.website or "",
                company.country or "",
                company.industry or "",
                company.phone or "",
                company.address or "",
                company.source or "",
                company.ai_score if company.ai_score is not None else "",
                company.status.value if hasattr(company.status, "value") else company.status,
                ";".join(emails),
                ";".join(uniq_phones),
            ]
        )
    return buffer.getvalue()


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


async def _find_existing(
    session: AsyncSession, domain: str | None, name: str, country: str | None
) -> Company | None:
    if domain:
        return await session.scalar(select(Company).where(Company.domain == domain))
    return await session.scalar(
        select(Company).where(Company.name == name, Company.country == country)
    )


async def import_companies_csv(session: AsyncSession, text: str) -> dict[str, Any]:
    """导入 CSV 文本，返回统计。无法解析的行计入 skipped。"""
    text = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV 缺少表头")

    created = updated = skipped = 0
    for row in reader:
        norm = {(k or "").strip().lower(): (v or "") for k, v in row.items()}
        name = _clean(norm.get("name"))
        if not name:
            skipped += 1
            continue
        domain = normalize_domain(_clean(norm.get("domain")) or _clean(norm.get("website")))
        country = normalize_country(_clean(norm.get("country")))
        industry = _clean(norm.get("industry"))
        phone = _clean(norm.get("phone"))
        address = _clean(norm.get("address"))
        website = _clean(norm.get("website"))
        source = _clean(norm.get("source")) or "import"
        raw_score = _clean(norm.get("ai_score"))
        ai_score = int(raw_score) if raw_score and raw_score.lstrip("-").isdigit() else None
        status_raw = (_clean(norm.get("status")) or "lead").lower()
        status = CompanyStatus(status_raw) if status_raw in _VALID_STATUS else CompanyStatus.LEAD
        emails = [e for e in (normalize_email(x) for x in _split(norm.get("emails"))) if e]
        phones = _split(norm.get("phones"))

        try:
            company = await _find_existing(session, domain, name, country)
            if company is None:
                company = Company(
                    name=name,
                    domain=domain,
                    website=website,
                    country=country,
                    industry=industry,
                    phone=phone or (phones[0] if phones else None),
                    address=address,
                    source=source,
                    ai_score=ai_score,
                    status=status,
                )
                session.add(company)
                await session.flush()
                created += 1
            else:
                company.name = company.name or name
                company.website = company.website or website
                company.industry = company.industry or industry
                company.phone = company.phone or phone or (phones[0] if phones else None)
                company.address = company.address or address
                company.country = company.country or country
                if ai_score is not None and company.ai_score is None:
                    company.ai_score = ai_score
                updated += 1

            for email in emails:
                exists = await session.scalar(
                    select(Contact).where(
                        Contact.company_id == company.id, Contact.email == email
                    )
                )
                if exists is None:
                    session.add(
                        Contact(
                            company_id=company.id,
                            name=company.name,
                            email=email,
                            source="import",
                        )
                    )
            if not emails and phones:
                for p in phones[:1]:
                    dup = await session.scalar(
                        select(Contact).where(
                            Contact.company_id == company.id, Contact.phone == p
                        )
                    )
                    if dup is None:
                        session.add(
                            Contact(
                                company_id=company.id,
                                name=company.name,
                                phone=p,
                                source="import",
                            )
                        )
            await session.commit()
        except Exception as exc:  # noqa: BLE001 - 单行失败不影响其余
            await session.rollback()
            skipped += 1
            logger.warning("import row failed (%s): %s", name, exc)

    return {"created": created, "updated": updated, "skipped": skipped}
