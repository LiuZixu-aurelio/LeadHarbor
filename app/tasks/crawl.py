"""采集相关 Celery 任务。长采集从 API 移到队列执行。"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.models.collect_job import CollectJob
from app.models.enums import CollectJobStatus
from app.pipeline.enrich import WebsiteEmailEnricher
from app.services.ingest_service import run_collection
from app.services.settings_service import apply_overrides
from app.tasks.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="crawl.run_collection")
def run_collection_task(
    source: str,
    query: dict[str, Any],
    max_items: int = 20,
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        factory = get_session_factory()
        async with factory() as session:
            await apply_overrides(session)
            result = await run_collection(
                session, source, query, max_items, enricher=WebsiteEmailEnricher()
            )
            return result.model_dump()

    return asyncio.run(_run())


@celery_app.task(name="crawl.run_batch_job")
def run_batch_job_task(job_id: int) -> dict[str, Any]:
    """执行一次「按国家批量采集」任务，边跑边更新进度到 collect_job。"""

    return asyncio.run(_run_batch_job(job_id))


async def _run_batch_job(job_id: int) -> dict[str, Any]:
    factory = get_session_factory()
    async with factory() as session:
        await apply_overrides(session)
        job = await session.get(CollectJob, job_id)
        if job is None:
            logger.warning("batch job %s not found", job_id)
            return {"error": "job not found"}

        source = job.source
        text_query = job.text_query
        regions = list(job.regions or [])
        max_items = job.max_items_per_region
        rounds = max(1, job.rounds or 1)
        language = job.language
        total_steps = len(regions) * rounds

        job.status = CollectJobStatus.RUNNING
        job.processed_regions = 0
        job.results = []
        job.error = None
        await session.commit()

        region_accum: dict[str, dict[str, int]] = {
            r: {"fetched": 0, "ingested": 0, "duplicates": 0, "failed": 0}
            for r in regions
        }
        region_error: dict[str, str | None] = {r: None for r in regions}

        for region_index, region in enumerate(regions):
            for round_index in range(rounds):
                query = {
                    "text_query": text_query,
                    "region": region,
                    "language": language,
                    "page": round_index + 1,
                    "skip": round_index * max_items,
                }
                try:
                    res = await run_collection(
                        session=session,
                        source=source,
                        query=query,
                        max_items=max_items,
                        enricher=WebsiteEmailEnricher(),
                    )
                    for key in region_accum[region]:
                        region_accum[region][key] += getattr(res, key)
                except Exception as exc:  # noqa: BLE001 - 单轮失败不影响其余
                    region_error[region] = f"{exc}"[:300]
                    logger.warning(
                        "batch job %s region=%s round=%d failed: %s",
                        job_id, region, round_index + 1, region_error[region],
                    )

                totals = {
                    "fetched": sum(a["fetched"] for a in region_accum.values()),
                    "ingested": sum(a["ingested"] for a in region_accum.values()),
                    "duplicates": sum(a["duplicates"] for a in region_accum.values()),
                    "failed": sum(a["failed"] for a in region_accum.values()),
                }
                job.processed_regions = min(
                    total_steps, region_index * rounds + round_index + 1
                )
                job.results = [
                    {
                        "region": r,
                        **region_accum[r],
                        "round": round_index + 1 if r == region else None,
                        "error": region_error[r],
                    }
                    for r in regions
                    if r == region or region_accum[r]["fetched"] > 0
                ]
                job.total_fetched = totals["fetched"]
                job.total_ingested = totals["ingested"]
                job.total_duplicates = totals["duplicates"]
                job.total_failed = totals["failed"]
                await session.commit()

                # 本轮没有抓到任何东西，说明该区域已无更多结果，提前结束剩余轮次
                if region_accum[region]["fetched"] == 0 and round_index > 0:
                    break

        final_results = [
            {"region": r, **region_accum[r], "error": region_error[r]} for r in regions
        ]
        errored = [x for x in final_results if x.get("error")]
        if not final_results or len(errored) == len(final_results):
            job.status = CollectJobStatus.FAILED
            if errored:
                job.error = errored[0]["error"]
        elif errored:
            job.status = CollectJobStatus.PARTIAL
        else:
            job.status = CollectJobStatus.SUCCESS
        job.processed_regions = total_steps
        job.results = final_results
        job.total_fetched = sum(a["fetched"] for a in region_accum.values())
        job.total_ingested = sum(a["ingested"] for a in region_accum.values())
        job.total_duplicates = sum(a["duplicates"] for a in region_accum.values())
        job.total_failed = sum(a["failed"] for a in region_accum.values())
        await session.commit()

        logger.info(
            "batch job %s done status=%s ingested=%d",
            job_id, job.status, job.total_ingested,
        )
        return {
            "job_id": job_id,
            "status": str(job.status),
            "ingested": job.total_ingested,
        }
