"""触达记录：每次外联（邮件/WhatsApp/LinkedIn）一条。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import OutreachChannel, OutreachStatus

if TYPE_CHECKING:
    from app.models.contact import Contact


class Outreach(Base, TimestampMixin):
    __tablename__ = "outreach"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contact.id", ondelete="CASCADE"), index=True, nullable=False
    )

    channel: Mapped[OutreachChannel] = mapped_column(
        Enum(
            OutreachChannel,
            name="outreach_channel",
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[OutreachStatus] = mapped_column(
        Enum(
            OutreachStatus,
            name="outreach_status",
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=OutreachStatus.QUEUED,
        nullable=False,
        index=True,
    )

    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    contact: Mapped[Contact] = relationship(back_populates="outreach")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Outreach id={self.id} channel={self.channel} status={self.status}>"
