"""Add workspace identity schema and workspace scoping columns.

Revision ID: 006
Revises: 005
Create Date: 2026-05-31
"""

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION current_workspace_id() RETURNS UUID
        LANGUAGE SQL STABLE AS $$
            SELECT NULLIF(current_setting('app.current_workspace_id', true), '')::uuid
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION current_user_id() RETURNS UUID
        LANGUAGE SQL STABLE AS $$
            SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION current_role() RETURNS TEXT
        LANGUAGE SQL STABLE AS $$
            SELECT NULLIF(current_setting('app.current_role', true), '')
        $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            external_subject TEXT UNIQUE NOT NULL,
            email            TEXT,
            created_at       TIMESTAMPTZ DEFAULT NOW(),
            updated_at       TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug        TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at  TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_memberships (
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role         TEXT NOT NULL CHECK (role IN ('viewer', 'editor', 'admin', 'owner')),
            created_at   TIMESTAMPTZ DEFAULT NOW(),
            PRIMARY KEY (workspace_id, user_id)
        )
        """
    )

    for table in (
        "papers",
        "claims",
        "methods",
        "benchmarks",
        "open_problems",
        "paper_links",
        "researchers",
        "hypotheses",
        "benchmark_drift",
        "notifications",
        "claim_lineage",
        "memory_events",
    ):
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS workspace_id UUID"
        )

    op.execute(
        "INSERT INTO users (id, external_subject, email) "
        f"VALUES ('{DEFAULT_USER_ID}'::uuid, 'bootstrap-system', 'bootstrap@local') "
        "ON CONFLICT (external_subject) DO NOTHING"
    )
    op.execute(
        "INSERT INTO workspaces (id, slug, name, created_by) "
        f"VALUES ('{DEFAULT_WORKSPACE_ID}'::uuid, 'default', 'Default Workspace', '{DEFAULT_USER_ID}'::uuid) "
        "ON CONFLICT (slug) DO NOTHING"
    )
    op.execute(
        "INSERT INTO workspace_memberships (workspace_id, user_id, role) "
        f"VALUES ('{DEFAULT_WORKSPACE_ID}'::uuid, '{DEFAULT_USER_ID}'::uuid, 'owner') "
        "ON CONFLICT (workspace_id, user_id) DO NOTHING"
    )

    op.execute(
        f"UPDATE papers SET workspace_id = '{DEFAULT_WORKSPACE_ID}'::uuid WHERE workspace_id IS NULL"
    )
    op.execute(
        "UPDATE claims c SET workspace_id = p.workspace_id FROM papers p "
        "WHERE c.paper_id = p.id AND c.workspace_id IS NULL"
    )
    op.execute(
        "UPDATE methods m SET workspace_id = p.workspace_id FROM papers p "
        "WHERE m.paper_id = p.id AND m.workspace_id IS NULL"
    )
    op.execute(
        "UPDATE benchmarks b SET workspace_id = p.workspace_id FROM papers p "
        "WHERE b.paper_id = p.id AND b.workspace_id IS NULL"
    )
    op.execute(
        "UPDATE open_problems opm SET workspace_id = p.workspace_id FROM papers p "
        "WHERE opm.paper_id = p.id AND opm.workspace_id IS NULL"
    )
    op.execute(
        "UPDATE benchmark_drift bd SET workspace_id = p.workspace_id FROM papers p "
        "WHERE bd.paper_id = p.id AND bd.workspace_id IS NULL"
    )
    op.execute(
        "UPDATE paper_links pl SET workspace_id = p.workspace_id FROM papers p "
        "WHERE pl.source_id = p.id AND pl.workspace_id IS NULL"
    )
    op.execute(
        "UPDATE claim_lineage cl SET workspace_id = c.workspace_id FROM claims c "
        "WHERE cl.parent_claim_id = c.id AND cl.workspace_id IS NULL"
    )
    op.execute(
        f"UPDATE researchers SET workspace_id = '{DEFAULT_WORKSPACE_ID}'::uuid WHERE workspace_id IS NULL"
    )
    op.execute(
        f"UPDATE hypotheses SET workspace_id = '{DEFAULT_WORKSPACE_ID}'::uuid WHERE workspace_id IS NULL"
    )
    op.execute(
        f"UPDATE notifications SET workspace_id = '{DEFAULT_WORKSPACE_ID}'::uuid WHERE workspace_id IS NULL"
    )
    op.execute(
        f"UPDATE memory_events SET workspace_id = '{DEFAULT_WORKSPACE_ID}'::uuid WHERE workspace_id IS NULL"
    )

    for table in (
        "papers",
        "claims",
        "methods",
        "benchmarks",
        "open_problems",
        "paper_links",
        "researchers",
        "hypotheses",
        "benchmark_drift",
        "notifications",
        "claim_lineage",
        "memory_events",
    ):
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN workspace_id SET NOT NULL"
        )
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN workspace_id SET DEFAULT current_workspace_id()"
        )
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk_{table}_workspace"
        )
        op.execute(
            f"ALTER TABLE {table} "
            f"ADD CONSTRAINT fk_{table}_workspace FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE"
        )
        op.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_workspace ON {table} (workspace_id)"
        )

    op.execute("ALTER TABLE paper_links DROP CONSTRAINT IF EXISTS paper_links_source_id_target_id_link_type_key")
    op.execute("ALTER TABLE paper_links DROP CONSTRAINT IF EXISTS paper_links_workspace_source_target_type_key")
    op.execute(
        "ALTER TABLE paper_links ADD CONSTRAINT "
        "paper_links_workspace_source_target_type_key UNIQUE (workspace_id, source_id, target_id, link_type)"
    )
    op.execute("ALTER TABLE claim_lineage DROP CONSTRAINT IF EXISTS claim_lineage_parent_claim_id_child_claim_id_key")
    op.execute("ALTER TABLE claim_lineage DROP CONSTRAINT IF EXISTS claim_lineage_workspace_parent_child_key")
    op.execute(
        "ALTER TABLE claim_lineage ADD CONSTRAINT "
        "claim_lineage_workspace_parent_child_key UNIQUE (workspace_id, parent_claim_id, child_claim_id)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE paper_links DROP CONSTRAINT IF EXISTS paper_links_workspace_source_target_type_key")
    op.execute(
        "ALTER TABLE paper_links ADD CONSTRAINT paper_links_source_id_target_id_link_type_key UNIQUE (source_id, target_id, link_type)"
    )
    op.execute("ALTER TABLE claim_lineage DROP CONSTRAINT IF EXISTS claim_lineage_workspace_parent_child_key")
    op.execute(
        "ALTER TABLE claim_lineage ADD CONSTRAINT claim_lineage_parent_claim_id_child_claim_id_key UNIQUE (parent_claim_id, child_claim_id)"
    )

    for table in (
        "papers",
        "claims",
        "methods",
        "benchmarks",
        "open_problems",
        "paper_links",
        "researchers",
        "hypotheses",
        "benchmark_drift",
        "notifications",
        "claim_lineage",
        "memory_events",
    ):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk_{table}_workspace")
        op.execute(f"DROP INDEX IF EXISTS idx_{table}_workspace")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS workspace_id")

    op.execute("DROP TABLE IF EXISTS workspace_memberships")
    op.execute("DROP TABLE IF EXISTS workspaces")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP FUNCTION IF EXISTS current_role()")
    op.execute("DROP FUNCTION IF EXISTS current_user_id()")
    op.execute("DROP FUNCTION IF EXISTS current_workspace_id()")
