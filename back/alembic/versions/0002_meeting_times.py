"""Add starts_at and ends_at to meetings.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("meetings", sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("meetings", sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True))
    # Existing meetings had no time: place them at their creation time, one hour long.
    op.execute("UPDATE meetings SET starts_at = created_at, ends_at = created_at + interval '1 hour'")
    op.alter_column("meetings", "starts_at", nullable=False)
    op.alter_column("meetings", "ends_at", nullable=False)
    op.create_index("ix_meetings_starts_at", "meetings", ["starts_at"])


def downgrade() -> None:
    op.drop_index("ix_meetings_starts_at", table_name="meetings")
    op.drop_column("meetings", "ends_at")
    op.drop_column("meetings", "starts_at")
