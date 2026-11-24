"""v1 路由聚合。"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import collectors, leads, settings

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(collectors.router)
api_router.include_router(leads.router)
api_router.include_router(settings.router)
