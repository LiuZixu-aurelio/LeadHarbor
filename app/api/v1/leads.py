"""查询与编辑接口：公司列表/详情/状态更新，原始线索列表，统计。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_session
from app.models.company import Company
from app.models.lead_raw import LeadRaw
from app.schemas.company import CompanyDetail, CompanyOut, CompanyUpdate
from app.schemas.lead import LeadRawOut
from app.services import company_io
from app.services.company_enrichment import enrich_company_from_channels

router = APIRouter(tags=["leads"])


@router.get("/companies", response_model=list[CompanyOut])
async def list_companies(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    min_score: int | None = Query(default=None, ge=0, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[Company]:
    stmt = select(Company).order_by(Company.ai_score.desc().nullslast(), Company.id.desc())
    if min_score is not None:
        stmt = stmt.where(Company.ai_score >= min_score)
    stmt = stmt.limit(limit).offset(offset)
    result = await session.scalars(stmt)
    return list(result)


@router.get("/companies/export")
async def export_companies(
    session: AsyncSession = Depends(get_session),
) -> Response:
    """导出全部客户（含联系人邮箱/电话）为 CSV。"""
    csv_text = await company_io.export_companies_csv(session)
    return Response(
        content=csv_text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="leadharbor_companies.csv"'
        },
    )


@router.post("/companies/import")
async def import_companies(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """从 CSV 导入客户；按域名或（名称+国家）合并，返回统计。"""
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="replace")
    try:
        return await company_io.import_companies_csv(session, text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _load_company(session: AsyncSession, company_id: int) -> Company | None:
    stmt = (
        select(Company)
        .where(Company.id == company_id)
        .options(selectinload(Company.contacts))
    )
    return await session.scalar(stmt)


@router.get("/companies/{company_id}", response_model=CompanyDetail)
async def get_company(
    company_id: int,
    session: AsyncSession = Depends(get_session),
) -> Company:
    company = await _load_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="客户不存在")
    return company


@router.patch("/companies/{company_id}", response_model=CompanyDetail)
async def update_company(
    company_id: int,
    payload: CompanyUpdate,
    session: AsyncSession = Depends(get_session),
) -> Company:
    company = await _load_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="客户不存在")
    if payload.status is not None:
        company.status = payload.status
    session.add(company)
    await session.commit()
    # commit 后属性过期，重新带 contacts 加载以免异步懒加载
    refreshed = await _load_company(session, company_id)
    assert refreshed is not None
    return refreshed


@router.post("/companies/{company_id}/enrich")
async def enrich_company(
    company_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """访问官网、搜索和地图渠道，合并补全邮箱/电话/地址。"""
    company = await _load_company(session, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="客户不存在")
    try:
        result = await enrich_company_from_channels(session, company)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"联系方式补全失败：{exc}") from exc
    refreshed = await _load_company(session, company_id)
    assert refreshed is not None
    detail = CompanyDetail.model_validate(refreshed)
    return {
        "found": result["found"],
        "attempts": result["attempts"],
        "company": detail.model_dump(),
    }


@router.get("/leads", response_model=list[LeadRawOut])
async def list_leads(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[LeadRaw]:
    stmt = select(LeadRaw).order_by(LeadRaw.id.desc()).limit(limit).offset(offset)
    result = await session.scalars(stmt)
    return list(result)


@router.get("/stats")
async def stats(session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    companies = await session.scalar(select(func.count()).select_from(Company)) or 0
    leads = await session.scalar(select(func.count()).select_from(LeadRaw)) or 0
    return {"companies": companies, "raw_leads": leads}
