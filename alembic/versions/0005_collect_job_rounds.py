"""add rounds to collect_job

Revision ID: 0005_collect_job_rounds
Revises: 0004_company_contact_info
Create Date: 2026-11-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_collect_job_rounds"
down_revision: str | Sequence[str] | None = "0004_company_contact_info"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "collect_job",
        sa.Column("rounds", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("collect_job", "rounds")
