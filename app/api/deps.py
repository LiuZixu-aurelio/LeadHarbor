"""API 依赖：数据库 session 等。"""

from __future__ import annotations

from app.core.db import get_session

__all__ = ["get_session"]
