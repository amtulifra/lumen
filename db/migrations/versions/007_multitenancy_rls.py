"""Enable RLS policies for tenant-scoped tables.

Revision ID: 007
Revises: 006
Create Date: 2026-05-31
"""

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

TENANT_TABLES = (
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
)


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_delete ON {table}")

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

    # Global reference tables stay unscoped
    op.execute("ALTER TABLE benchmark_metadata DISABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_select ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_update ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_delete ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
