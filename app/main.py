"""FastAPI 入口。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.db import dispose_engine, get_session_factory
from app.core.logging import setup_logging
from app.services.settings_service import apply_overrides


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    try:
        async with get_session_factory()() as session:
            await apply_overrides(session)
    except Exception:  # noqa: BLE001 - 启动阶段 DB 未就绪不影响服务
        pass
    yield
    await dispose_engine()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(api_router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}
