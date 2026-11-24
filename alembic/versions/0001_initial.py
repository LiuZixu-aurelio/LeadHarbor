"""initial schema: lead_raw / company / contact / outreach

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.models.enums import (
    CompanyStatus,
    LeadStatus,
    OutreachChannel,
    OutreachStatus,
)

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _values(enum_cls: type) -> list[str]:
    return [m.value for m in enum_cls]


def upgrade() -> None:
    # pgvector 扩展（company.embedding 依赖）
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "lead_raw",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("query", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                *_values(LeadStatus),
                name="lead_status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("error", sa.String(length=512), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lead_raw")),
    )
    op.create_index(op.f("ix_lead_raw_source"), "lead_raw", ["source"])
    op.create_index(op.f("ix_lead_raw_status"), "lead_raw", ["status"])
    op.create_index(op.f("ix_lead_raw_fetched_at"), "lead_raw", ["fetched_at"])

    op.create_table(
        "company",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("domain", sa.String(length=256), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("size_band", sa.String(length=32), nullable=True),
        sa.Column("revenue_band", sa.String(length=32), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("ai_score", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                *_values(CompanyStatus),
                name="company_status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("embedding", Vector(settings.embedding_dim), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company")),
        sa.UniqueConstraint("domain", name=op.f("uq_company_domain")),
    )
    op.create_index(op.f("ix_company_name"), "company", ["name"])
    op.create_index(op.f("ix_company_country"), "company", ["country"])
    op.create_index(op.f("ix_company_industry"), "company", ["industry"])
    op.create_index(op.f("ix_company_ai_score"), "company", ["ai_score"])
    op.create_index(op.f("ix_company_status"), "company", ["status"])

    op.create_table(
        "contact",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=128), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("whatsapp", sa.String(length=64), nullable=True),
        sa.Column("linkedin_url", sa.String(length=512), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False),
        sa.Column("do_not_contact", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["company.id"],
            name=op.f("fk_contact_company_id_company"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact")),
        sa.UniqueConstraint(
            "company_id", "email", name=op.f("uk_contact_company_email")
        ),
    )
    op.create_index(op.f("ix_contact_company_id"), "contact", ["company_id"])
    op.create_index(op.f("ix_contact_email"), "contact", ["email"])
    op.create_index(op.f("ix_contact_do_not_contact"), "contact", ["do_not_contact"])

    op.create_table(
        "outreach",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "channel",
            sa.Enum(
                *_values(OutreachChannel),
                name="outreach_channel",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("template_id", sa.String(length=64), nullable=True),
        sa.Column("subject", sa.String(length=512), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                *_values(OutreachStatus),
                name="outreach_status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contact.id"],
            name=op.f("fk_outreach_contact_id_contact"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outreach")),
    )
    op.create_index(op.f("ix_outreach_contact_id"), "outreach", ["contact_id"])
    op.create_index(op.f("ix_outreach_status"), "outreach", ["status"])


def downgrade() -> None:
    op.drop_table("outreach")
    op.drop_table("contact")
    op.drop_table("company")
    op.drop_table("lead_raw")
