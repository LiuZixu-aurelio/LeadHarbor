"""公司实体：清洗后的客户主表，domain 为去重硬键。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Enum, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.models.base import Base, TimestampMixin
from app.models.enums import CompanyStatus

if TYPE_CHECKING:
    from app.models.contact import Contact


class Company(Base, TimestampMixin):
    __tablename__ = "company"
    __table_args__ = (UniqueConstraint("domain", name="uq_company_domain"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    # 去重硬键：域名唯一（UniqueConstraint 自带唯一索引）
    domain: Mapped[str | None] = mapped_column(String(256), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), index=True, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    size_band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    revenue_band: Mapped[str | None] = mapped_column(String(32), nullable=True)

    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # AI 匹配度 0-100
    ai_score: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    status: Mapped[CompanyStatus] = mapped_column(
        Enum(
            CompanyStatus,
            name="company_status",
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=CompanyStatus.LEAD,
        nullable=False,
        index=True,
    )

    # 客户画像向量（用于相似客户推荐），可为空
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim), nullable=True
    )

    contacts: Mapped[list[Contact]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def contact_count(self) -> int:
        return len(self.contacts)

    @property
    def has_email(self) -> bool:
        return any(c.email for c in self.contacts)

    @property
    def has_phone(self) -> bool:
        return bool(self.phone) or any(c.phone for c in self.contacts)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Company id={self.id} name={self.name!r} domain={self.domain}>"
