"""Add a singleton daily budget, deliberately uninitialized until verified import.

Revision ID: 6a81e4b39c20
Revises: 12fdf9646b5d
"""

import sqlalchemy as sa

from alembic import op

revision = "6a81e4b39c20"
down_revision = "12fdf9646b5d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_daily_usage",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("utc_day", sa.Date(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_ai_daily_usage_singleton")),
        sa.CheckConstraint(
            "attempts >= 0", name=op.f("ck_ai_daily_usage_attempts_nonnegative")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_daily_usage")),
    )


def downgrade():
    raise RuntimeError(
        "Daily usage cannot be safely discarded; use the documented paused-service rollback without dropping its ledger"
    )
