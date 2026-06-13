"""Add dedicated claim conflicts and feedback tables.

Revision ID: 012
Revises: 011
Create Date: 2026-06-13
"""

from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def _create_tenant_policies(table: str) -> None:
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_select ON {table}
        FOR SELECT USING (
            workspace_id = current_workspace_id()
            AND current_workspace_id() IS NOT NULL
        )
        """
    )
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_insert ON {table}
        FOR INSERT WITH CHECK (
            workspace_id = current_workspace_id()
            AND current_workspace_id() IS NOT NULL
            AND current_role() IN ('owner', 'admin', 'editor')
        )
        """
    )
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_update ON {table}
        FOR UPDATE USING (
            workspace_id = current_workspace_id()
            AND current_workspace_id() IS NOT NULL
            AND current_role() IN ('owner', 'admin', 'editor')
        )
        WITH CHECK (
            workspace_id = current_workspace_id()
            AND current_workspace_id() IS NOT NULL
            AND current_role() IN ('owner', 'admin', 'editor')
        )
        """
    )
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_delete ON {table}
        FOR DELETE USING (
            workspace_id = current_workspace_id()
            AND current_workspace_id() IS NOT NULL
            AND current_role() IN ('owner', 'admin')
        )
        """
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS claim_conflicts (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id     UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
            parent_claim_id  UUID NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
            child_claim_id   UUID NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
            parent_paper_id  TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            child_paper_id   TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            relation         TEXT NOT NULL CHECK (relation IN ('challenges', 'refines')),
            severity         TEXT NOT NULL CHECK (severity IN ('possible', 'likely', 'strong', 'verified')),
            confidence       FLOAT NOT NULL DEFAULT 0,
            reasoning        TEXT NOT NULL DEFAULT '',
            created_at       TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (workspace_id, parent_claim_id, child_claim_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS claim_conflict_feedback (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
            conflict_id   UUID NOT NULL REFERENCES claim_conflicts(id) ON DELETE CASCADE,
            created_by    UUID REFERENCES users(id) ON DELETE SET NULL DEFAULT current_user_id(),
            feedback      TEXT NOT NULL CHECK (feedback IN ('agree', 'disagree')),
            note          TEXT DEFAULT '',
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            updated_at    TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (workspace_id, conflict_id, created_by)
        )
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_claim_conflicts_workspace ON claim_conflicts (workspace_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_claim_conflicts_severity ON claim_conflicts (workspace_id, severity)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_claim_conflicts_relation ON claim_conflicts (workspace_id, relation)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_claim_conflicts_parent_child ON claim_conflicts (workspace_id, parent_claim_id, child_claim_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_claim_conflict_feedback_workspace ON claim_conflict_feedback (workspace_id, conflict_id)")

    for table in ("claim_conflicts", "claim_conflict_feedback"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_delete ON {table}")
        _create_tenant_policies(table)


def downgrade() -> None:
    for table in ("claim_conflict_feedback", "claim_conflicts"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_delete ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP TABLE IF EXISTS claim_conflict_feedback CASCADE")
    op.execute("DROP TABLE IF EXISTS claim_conflicts CASCADE")
