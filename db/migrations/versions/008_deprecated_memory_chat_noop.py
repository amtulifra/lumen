"""Compatibility no-op migration for removed memory chat revision.

Revision ID: 008
Revises: 007
Create Date: 2026-06-13
"""

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Intentionally no-op.
    # This revision preserves linear history compatibility for any DB
    # that was previously upgraded/stamped to revision 008.
    pass


def downgrade() -> None:
    # Intentionally no-op.
    pass
