"""Add benchmark conflicts with severity and feedback.

Revision ID: 010
Revises: 009
Create Date: 2026-06-13
"""

from alembic import op

revision = "010"
down_revision = "009"
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
        CREATE TABLE IF NOT EXISTS benchmark_conflicts (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id      UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
            paper_a_id        TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            paper_b_id        TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            dataset           TEXT NOT NULL,
            metric            TEXT NOT NULL,
            model             TEXT,
            split_a           TEXT,
            split_b           TEXT,
            value_a           FLOAT NOT NULL,
            value_b           FLOAT NOT NULL,
            delta             FLOAT NOT NULL,
            severity          TEXT NOT NULL CHECK (severity IN ('possible', 'likely', 'strong', 'verified')),
            context_mismatch  BOOLEAN NOT NULL DEFAULT FALSE,
            reasoning         TEXT NOT NULL DEFAULT '',
            created_at        TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (workspace_id, paper_a_id, paper_b_id, dataset, metric, model, split_a, split_b)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_conflict_feedback (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
            conflict_id   UUID NOT NULL REFERENCES benchmark_conflicts(id) ON DELETE CASCADE,
            created_by    UUID REFERENCES users(id) ON DELETE SET NULL DEFAULT current_user_id(),
            feedback      TEXT NOT NULL CHECK (feedback IN ('agree', 'disagree')),
            note          TEXT DEFAULT '',
            created_at    TIMESTAMPTZ DEFAULT NOW(),
            updated_at    TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (workspace_id, conflict_id, created_by)
        )
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_benchmark_conflicts_workspace ON benchmark_conflicts (workspace_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_benchmark_conflicts_severity ON benchmark_conflicts (workspace_id, severity)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_benchmark_conflicts_dataset_metric ON benchmark_conflicts (workspace_id, dataset, metric)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_benchmark_conflicts_papers ON benchmark_conflicts (workspace_id, paper_a_id, paper_b_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_benchmark_conflict_feedback_workspace ON benchmark_conflict_feedback (workspace_id, conflict_id)")

    for table in ("benchmark_conflicts", "benchmark_conflict_feedback"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_delete ON {table}")
        _create_tenant_policies(table)


def downgrade() -> None:
    for table in ("benchmark_conflict_feedback", "benchmark_conflicts"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_delete ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP TABLE IF EXISTS benchmark_conflict_feedback CASCADE")
    op.execute("DROP TABLE IF EXISTS benchmark_conflicts CASCADE")
