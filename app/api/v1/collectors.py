"""采集相关接口：单次、同步批量、异步批量（Celery）与任务查询。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.collectors.registry import available_sources, describe_sources
from app.collectors.templates import COLLECT_TEMPLATES
from app.core.config import settings
from app.core.logging import get_logger
from app.models.collect_job import CollectJob
from app.models.enums import CollectJobStatus
from app.pipeline.enrich import WebsiteEmailEnricher
from app.schemas.ai_pipeline import AIPipelineRequest, AIPipelineResult
from app.schemas.collect import (
    BatchCollectRequest,
    BatchCollectResult,
    BatchRegionResult,
    CollectConfig,
    CollectRequest,
    CollectResult,
)
from app.schemas.job import CollectJobOut
from app.services.ai_pipeline import run_pipeline as run_ai_pipeline
from app.services.ingest_service import run_collection
from app.tasks.crawl import run_batch_job_task

logger = get_logger(__name__)

router = APIRouter(tags=["collect"])

MAX_BATCH_REGIONS = 12


def _normalize_regions(regions: list[str]) -> list[str]:
    cleaned = [r.strip().upper() for r in regions if r and r.strip()]
    if not cleaned:
        raise HTTPException(status_code=400, detail="regions 不能为空")
    if len(cleaned) > MAX_BATCH_REGIONS:
        raise HTTPException(
            status_code=400, detail=f"一次最多批量 {MAX_BATCH_REGIONS} 个国家"
        )
    return cleaned


@router.get("/collectors", response_model=list[str])
async def list_collectors() -> list[str]:
    return available_sources()


@router.get("/collect/config", response_model=CollectConfig)
async def collect_config() -> CollectConfig:
    """返回可用数据源、所需密钥、默认区域、目标市场与关键词模板。"""
    return CollectConfig(
        sources=describe_sources(),
        target_countries=settings.target_country_list,
        default_region=settings.default_region,
        templates=COLLECT_TEMPLATES,
    )


@router.post("/collect", response_model=CollectResult)
async def collect(
    payload: CollectRequest,
    session: AsyncSession = Depends(get_session),
) -> CollectResult:
    if payload.source not in available_sources():
        raise HTTPException(
            status_code=400,
            detail=f"未知采集器 {payload.source!r}，可用: {available_sources()}",
        )
    try:
        return await run_collection(
            session=session,
            source=payload.source,
            query=payload.query,
            max_items=payload.max_items,
            enricher=WebsiteEmailEnricher(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/collect/batch", response_model=BatchCollectResult)
async def collect_batch(
    payload: BatchCollectRequest,
    session: AsyncSession = Depends(get_session),
) -> BatchCollectResult:
    """同步按国家批量采集（适合少量国家、条数较小）。大批量请用 /collect/batch/async。"""
    if payload.source not in available_sources():
        raise HTTPException(
            status_code=400,
            detail=f"未知采集器 {payload.source!r}，可用: {available_sources()}",
        )
    regions = _normalize_regions(payload.regions)

    items: list[BatchRegionResult] = []
    totals = {"fetched": 0, "ingested": 0, "duplicates": 0, "failed": 0}

    for region in regions:
        region_total = {"fetched": 0, "ingested": 0, "duplicates": 0, "failed": 0}
        error: str | None = None
        for round_index in range(payload.rounds):
            query = {
                "text_query": payload.text_query,
                "region": region,
                "language": payload.language,
                "page": round_index + 1,
                "skip": round_index * payload.max_items_per_region,
            }
            try:
                result = await run_collection(
                    session=session,
                    source=payload.source,
                    query=query,
                    max_items=payload.max_items_per_region,
                    enricher=WebsiteEmailEnricher(),
                )
                for key in region_total:
                    region_total[key] += getattr(result, key)
            except Exception as exc:  # noqa: BLE001 - 单轮失败不影响其余
                region_error = f"{exc}"[:300]
                error = region_error
                region_error = f"{exc}"[:300]
                error = region_error
                region_error = f"{exc}"[:300]
        item_result = CollectResult(source=payload.source, **region_total)
        items.append(BatchRegionResult(region=region, result=item_result, error=error))
        for key in totals:
            totals[key] += region_total[key]

    return BatchCollectResult(
        source=payload.source,
        text_query=payload.text_query,
        regions_total=len(regions) * payload.rounds,
        total_fetched=totals["fetched"],
        total_ingested=totals["ingested"],
        total_duplicates=totals["duplicates"],
        total_failed=totals["failed"],
        items=items,
    )


@router.post("/collect/batch/async", response_model=CollectJobOut, status_code=202)
async def collect_batch_async(
    payload: BatchCollectRequest,
    session: AsyncSession = Depends(get_session),
) -> CollectJob:
    """异步按国家批量采集：创建任务并入队 Celery，立即返回任务用于轮询进度。"""
    if payload.source not in available_sources():
        raise HTTPException(
            status_code=400,
            detail=f"未知采集器 {payload.source!r}，可用: {available_sources()}",
        )
    regions = _normalize_regions(payload.regions)

    job = CollectJob(
        source=payload.source,
        text_query=payload.text_query,
        regions=regions,
        max_items_per_region=payload.max_items_per_region,
        rounds=payload.rounds,
        language=payload.language,
        status=CollectJobStatus.PENDING,
        total_regions=len(regions) * payload.rounds,
        processed_regions=0,
        total_fetched=0,
        total_ingested=0,
        total_duplicates=0,
        total_failed=0,
        results=[],
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    try:
        run_batch_job_task.delay(job.id)
    except Exception as exc:  # noqa: BLE001 - 入队失败（Redis/Celery 未就绪）
        logger.error("enqueue batch job failed: %s", exc)
        job.status = CollectJobStatus.FAILED
        job.error = f"任务入队失败: {exc}"[:512]
        await session.commit()
        raise HTTPException(
            status_code=503, detail="任务入队失败，请确认 Celery 与 Redis 正在运行"
        ) from exc

    return job


@router.get("/collect/jobs", response_model=list[CollectJobOut])
async def list_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[CollectJob]:
    stmt = select(CollectJob).order_by(CollectJob.id.desc()).limit(limit)
    return list(await session.scalars(stmt))


@router.get("/collect/jobs/{job_id}", response_model=CollectJobOut)
async def get_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
) -> CollectJob:
    job = await session.get(CollectJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job

@router.post("/collect/ai-pipeline", response_model=AIPipelineResult)
async def collect_ai_pipeline(
    payload: AIPipelineRequest,
    session: AsyncSession = Depends(get_session),
) -> AIPipelineResult:
    """Google 搜索发现页面 → AI 抽取 → 入库。"""
    if "google_search" not in available_sources():
        raise HTTPException(status_code=503, detail="Google 搜索采集器不可用")
    if "ai_extractor" not in available_sources():
        raise HTTPException(status_code=503, detail="AI 网页提取采集器不可用")
    try:
        result = await run_ai_pipeline(
            session=session,
            keyword=payload.keyword,
            region=payload.region.upper(),
            max_pages=payload.max_pages,
            max_items_per_page=payload.max_items_per_page,
            language=payload.language,
        )
        return AIPipelineResult.model_validate(result)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
