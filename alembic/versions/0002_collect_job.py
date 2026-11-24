"""add collect_job table for async batch collection

Revision ID: 0002_collect_job
Revises: 0001_initial
Create Date: 2026-11-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.models.enums import CollectJobStatus

revision: str = "0002_collect_job"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _values(enum_cls: type) -> list[str]:
    return [m.value for m in enum_cls]


def upgrade() -> None:
    op.create_table(
        "collect_job",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("text_query", sa.String(length=512), nullable=False),
        sa.Column("regions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("max_items_per_region", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                *_values(CollectJobStatus),
                name="collect_job_status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("total_regions", sa.Integer(), nullable=False),
        sa.Column("processed_regions", sa.Integer(), nullable=False),
        sa.Column("total_fetched", sa.Integer(), nullable=False),
        sa.Column("total_ingested", sa.Integer(), nullable=False),
        sa.Column("total_duplicates", sa.Integer(), nullable=False),
        sa.Column("total_failed", sa.Integer(), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.String(length=512), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collect_job")),
    )
    op.create_index(op.f("ix_collect_job_status"), "collect_job", ["status"])


def downgrade() -> None:
    op.drop_table("collect_job")
