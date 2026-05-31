"""Switch vector dimensions to 384 for BGE embeddings.

Revision ID: 005
Revises: 004
Create Date: 2026-05-31
"""

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_papers_title_embedding")
    op.execute("DROP INDEX IF EXISTS idx_claims_embedding")
    op.execute("DROP INDEX IF EXISTS idx_methods_embedding")
    op.execute("DROP INDEX IF EXISTS idx_hypotheses_embedding")
    op.execute("DROP INDEX IF EXISTS idx_open_problems_embedding")
    op.execute("DROP INDEX IF EXISTS idx_memory_events_embedding")

    # Existing vectors cannot be resized safely; reset to NULL and re-embed at 384 dimensions.
    op.execute(
        "ALTER TABLE papers ALTER COLUMN title_embedding TYPE VECTOR(384) USING NULL::VECTOR(384)"
    )
    op.execute(
        "ALTER TABLE claims ALTER COLUMN embedding TYPE VECTOR(384) USING NULL::VECTOR(384)"
    )
    op.execute(
        "ALTER TABLE methods ALTER COLUMN embedding TYPE VECTOR(384) USING NULL::VECTOR(384)"
    )
    op.execute(
        "ALTER TABLE open_problems ALTER COLUMN embedding TYPE VECTOR(384) USING NULL::VECTOR(384)"
    )
    op.execute(
        "ALTER TABLE hypotheses ALTER COLUMN embedding TYPE VECTOR(384) USING NULL::VECTOR(384)"
    )
    op.execute(
        "ALTER TABLE memory_events ALTER COLUMN embedding TYPE VECTOR(384) USING NULL::VECTOR(384)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_papers_title_embedding ON papers USING hnsw (title_embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_claims_embedding ON claims USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_methods_embedding ON methods USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_hypotheses_embedding ON hypotheses USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_open_problems_embedding ON open_problems USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_events_embedding ON memory_events USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_papers_title_embedding")
    op.execute("DROP INDEX IF EXISTS idx_claims_embedding")
    op.execute("DROP INDEX IF EXISTS idx_methods_embedding")
    op.execute("DROP INDEX IF EXISTS idx_hypotheses_embedding")
    op.execute("DROP INDEX IF EXISTS idx_open_problems_embedding")
    op.execute("DROP INDEX IF EXISTS idx_memory_events_embedding")

    op.execute(
        "ALTER TABLE papers ALTER COLUMN title_embedding TYPE VECTOR(1536) USING NULL::VECTOR(1536)"
    )
    op.execute(
        "ALTER TABLE claims ALTER COLUMN embedding TYPE VECTOR(1536) USING NULL::VECTOR(1536)"
    )
    op.execute(
        "ALTER TABLE methods ALTER COLUMN embedding TYPE VECTOR(1536) USING NULL::VECTOR(1536)"
    )
    op.execute(
        "ALTER TABLE open_problems ALTER COLUMN embedding TYPE VECTOR(1536) USING NULL::VECTOR(1536)"
    )
    op.execute(
        "ALTER TABLE hypotheses ALTER COLUMN embedding TYPE VECTOR(1536) USING NULL::VECTOR(1536)"
    )
    op.execute(
        "ALTER TABLE memory_events ALTER COLUMN embedding TYPE VECTOR(1536) USING NULL::VECTOR(1536)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_papers_title_embedding ON papers USING hnsw (title_embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_claims_embedding ON claims USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_methods_embedding ON methods USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_hypotheses_embedding ON hypotheses USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_open_problems_embedding ON open_problems USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_memory_events_embedding ON memory_events USING hnsw (embedding vector_cosine_ops)"
    )
