"""运行时配置接口：前端查看/填写各数据源密钥，并做连接测试。"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.collectors.registry import available_sources, get_collector
from app.core.config import settings
from app.core.logging import get_logger
from app.services import settings_service

logger = get_logger(__name__)

router = APIRouter(tags=["settings"], prefix="/settings")

_TEST_TIMEOUT = 25.0


class SettingsUpdate(BaseModel):
    updates: dict[str, str]


class TestRequest(BaseModel):
    source: str
    query: dict[str, Any] | None = None


@router.get("/keys")
async def get_keys() -> list[dict[str, Any]]:
    """返回可配置项与当前状态（密钥打码）。"""
    return settings_service.status_list()


@router.put("/keys")
async def update_keys(
    payload: SettingsUpdate,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """保存密钥，立即在 API 进程内生效（Celery 任务开始时也会读取）。"""
    try:
        return await settings_service.save_updates(session, payload.updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _default_query(source: str) -> dict[str, Any]:
    region = settings.default_region
    if source in {"website", "ai_extractor"}:
        return {"urls": ["example.com"], "max_items": 1}
    return {"text_query": "coffee", "region": region, "max_items": 1}


@router.post("/test")
async def test_connection(payload: TestRequest) -> dict[str, Any]:
    """对某个渠道发一个最小请求，验证密钥/网络是否可用（不写库）。"""
    if payload.source not in available_sources():
        raise HTTPException(
            status_code=400,
            detail=f"未知采集器 {payload.source!r}，可用: {available_sources()}",
        )
    query = {**_default_query(payload.source), **(payload.query or {})}
    query["max_items"] = 1

    async def _run() -> dict[str, Any]:
        collector = get_collector(payload.source)
        async for lead in collector.collect(query):
            return {
                "ok": True,
                "message": "连接成功",
                "sample": {
                    "name": lead.name,
                    "website": lead.website,
                    "phone": lead.phone,
                    "country": lead.country,
                },
            }
        return {"ok": True, "message": "连接成功，但该关键词暂无结果（可换关键词或区域）"}

    try:
        return await asyncio.wait_for(_run(), timeout=_TEST_TIMEOUT)
    except TimeoutError:
        return {"ok": False, "message": f"连接超时（>{int(_TEST_TIMEOUT)}s），请检查网络或代理"}
    except (RuntimeError, ValueError) as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("test connection %s failed: %s", payload.source, exc)
        return {"ok": False, "message": f"连接失败：{exc}"}
