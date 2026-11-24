"""add phone/address to company

Revision ID: 0004_company_contact_info
Revises: 0003_app_setting
Create Date: 2026-11-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_company_contact_info"
down_revision: str | Sequence[str] | None = "0003_app_setting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("company", sa.Column("phone", sa.String(length=64), nullable=True))
    op.add_column("company", sa.Column("address", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("company", "address")
    op.drop_column("company", "phone")
