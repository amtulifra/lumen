"""Add memory_events table for Research Memory (Phase 11)

Revision ID: 004
Revises: 003
Create Date: 2026-05-31
"""

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS memory_events (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            type         TEXT NOT NULL,
            subject_id   TEXT,
            subject_type TEXT,
            content      TEXT NOT NULL,
            embedding    VECTOR(1536),
            occurred_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_memory_events_type    ON memory_events (type, occurred_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_memory_events_subject ON memory_events (subject_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_memory_events_embedding ON memory_events USING hnsw (embedding vector_cosine_ops)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS memory_events CASCADE")
