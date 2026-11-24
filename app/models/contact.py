"""联系人实体：一个公司可对应多个决策人。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.outreach import Outreach


class Contact(Base, TimestampMixin):
    __tablename__ = "contact"
    __table_args__ = (
        UniqueConstraint("company_id", "email", name="uk_contact_company_email"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    company_id: Mapped[int] = mapped_column(
        ForeignKey("company.id", ondelete="CASCADE"), index=True, nullable=False
    )

    name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(64), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    do_not_contact: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    company: Mapped[Company] = relationship(back_populates="contacts")
    outreach: Mapped[list[Outreach]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Contact id={self.id} email={self.email} company_id={self.company_id}>"
