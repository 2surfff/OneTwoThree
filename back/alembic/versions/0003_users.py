"""Add users and meeting owners.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("cognito_sub", sa.String(128), nullable=False, unique=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("name", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # Existing meetings keep a null owner: they were created before accounts and stay hidden.
    op.add_column(
        "meetings",
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_meetings_owner_id", "meetings", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_meetings_owner_id", table_name="meetings")
    op.drop_column("meetings", "owner_id")
    op.drop_table("users")
