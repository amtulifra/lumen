"""Add notifications table

Revision ID: 002
Revises: 001
Create Date: 2026-04-29
"""

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type        TEXT NOT NULL,
            message     TEXT NOT NULL,
            payload     JSONB DEFAULT '{}',
            read        BOOLEAN DEFAULT FALSE,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications (read, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS notifications CASCADE")
