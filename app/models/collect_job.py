"""批量采集任务：记录一次「按国家批量采集」的进度与结果。"""

from __future__ import annotations

from sqlalchemy import BigInteger, Enum, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import CollectJobStatus


class CollectJob(Base, TimestampMixin):
    __tablename__ = "collect_job"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    source: Mapped[str] = mapped_column(String(64), nullable=False)
    text_query: Mapped[str] = mapped_column(String(512), nullable=False)
    # 目标国家列表，如 ["KZ", "UZ"]
    regions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    max_items_per_region: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    # 采集轮次：每轮向后翻页 skip，抓取更深的、不同的结果
    rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")

    status: Mapped[CollectJobStatus] = mapped_column(
        Enum(
            CollectJobStatus,
            name="collect_job_status",
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=CollectJobStatus.PENDING,
        nullable=False,
        index=True,
    )

    total_regions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_regions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_ingested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_duplicates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 每个国家的明细：[{region, fetched, ingested, duplicates, failed, error}]
    results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<CollectJob id={self.id} source={self.source!r} status={self.status}>"
