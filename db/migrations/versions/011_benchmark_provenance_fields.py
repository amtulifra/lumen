"""Add benchmark provenance/context fields.

Revision ID: 011
Revises: 010
Create Date: 2026-06-13
"""

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS prompt_method TEXT")
    op.execute("ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS benchmark_ver TEXT")
    op.execute("ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS eval_framework TEXT")
    op.execute("ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS notes TEXT")
    op.execute("ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS evidence_span TEXT")
    op.execute("ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS section TEXT")
    op.execute("ALTER TABLE benchmarks ADD COLUMN IF NOT EXISTS page_number INT")


def downgrade() -> None:
    op.execute("ALTER TABLE benchmarks DROP COLUMN IF EXISTS prompt_method")
    op.execute("ALTER TABLE benchmarks DROP COLUMN IF EXISTS benchmark_ver")
    op.execute("ALTER TABLE benchmarks DROP COLUMN IF EXISTS eval_framework")
    op.execute("ALTER TABLE benchmarks DROP COLUMN IF EXISTS notes")
    op.execute("ALTER TABLE benchmarks DROP COLUMN IF EXISTS evidence_span")
    op.execute("ALTER TABLE benchmarks DROP COLUMN IF EXISTS section")
    op.execute("ALTER TABLE benchmarks DROP COLUMN IF EXISTS page_number")
