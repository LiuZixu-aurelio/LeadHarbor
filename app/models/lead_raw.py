"""原始线索池：任何采集器的输出先进这里，保留原始 payload 以便追溯与重跑。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import LeadStatus


class LeadRaw(Base):
    __tablename__ = "lead_raw"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # 数据来源标识，如 google_places / b2b_directory / web_scraper
    source: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # 采集时的查询条件（便于复现一次采集）
    query: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # 原始数据，字段千奇百怪，原样存储
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    status: Mapped[LeadStatus] = mapped_column(
        Enum(
            LeadStatus,
            name="lead_status",
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=LeadStatus.PENDING,
        nullable=False,
        index=True,
    )

    error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LeadRaw id={self.id} source={self.source} status={self.status}>"
