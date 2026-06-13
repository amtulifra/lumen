"""Add normalized hypothesis evidence and feedback tables.

Revision ID: 009
Revises: 007
Create Date: 2026-06-13
"""

from alembic import op

revision = "009"
down_revision = "008"
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
    op.execute("ALTER TABLE claims ADD COLUMN IF NOT EXISTS evidence_span TEXT")
    op.execute("ALTER TABLE claims ADD COLUMN IF NOT EXISTS section TEXT")
    op.execute("ALTER TABLE claims ADD COLUMN IF NOT EXISTS page_number INT")
    op.execute("UPDATE claims SET evidence_span = evidence WHERE evidence_span IS NULL")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hypothesis_evidence (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
            hypothesis_id UUID NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
            paper_id     TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            claim_text   TEXT NOT NULL,
            verdict      TEXT NOT NULL CHECK (verdict IN ('supports', 'refutes', 'mixed')),
            strength     FLOAT NOT NULL DEFAULT 0,
            cited_span   TEXT,
            section      TEXT,
            page_number  INT,
            reasoning    TEXT,
            created_at   TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS hypothesis_evidence_feedback (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
            evidence_id  UUID NOT NULL REFERENCES hypothesis_evidence(id) ON DELETE CASCADE,
            created_by   UUID REFERENCES users(id) ON DELETE SET NULL DEFAULT current_user_id(),
            feedback     TEXT NOT NULL CHECK (feedback IN ('agree', 'disagree')),
            note         TEXT DEFAULT '',
            created_at   TIMESTAMPTZ DEFAULT NOW(),
            updated_at   TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (workspace_id, evidence_id, created_by)
        )
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_hypothesis_evidence_workspace ON hypothesis_evidence (workspace_id, hypothesis_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hypothesis_evidence_hypothesis ON hypothesis_evidence (hypothesis_id, verdict)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hypothesis_evidence_paper ON hypothesis_evidence (paper_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hypothesis_evidence_feedback_workspace ON hypothesis_evidence_feedback (workspace_id, evidence_id)")

    for table in ("hypothesis_evidence", "hypothesis_evidence_feedback"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_delete ON {table}")
        _create_tenant_policies(table)


def downgrade() -> None:
    for table in ("hypothesis_evidence_feedback", "hypothesis_evidence"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_delete ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP TABLE IF EXISTS hypothesis_evidence_feedback CASCADE")
    op.execute("DROP TABLE IF EXISTS hypothesis_evidence CASCADE")
    op.execute("ALTER TABLE claims DROP COLUMN IF EXISTS evidence_span")
    op.execute("ALTER TABLE claims DROP COLUMN IF EXISTS section")
    op.execute("ALTER TABLE claims DROP COLUMN IF EXISTS page_number")
