"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-29
"""

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")

    op.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id              TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            authors         JSONB,
            year            INT,
            arxiv_url       TEXT,
            pdf_url         TEXT,
            raw_text        TEXT,
            knowledge_obj   JSONB,
            title_embedding VECTOR(1536),
            ingested_at     TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            paper_id    TEXT REFERENCES papers(id) ON DELETE CASCADE,
            text        TEXT,
            confidence  FLOAT,
            evidence    TEXT,
            embedding   VECTOR(1536)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS methods (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            paper_id    TEXT REFERENCES papers(id) ON DELETE CASCADE,
            name        TEXT,
            description TEXT,
            is_novel    BOOLEAN,
            embedding   VECTOR(1536)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS benchmarks (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            paper_id    TEXT REFERENCES papers(id) ON DELETE CASCADE,
            dataset     TEXT,
            metric      TEXT,
            value       FLOAT,
            model       TEXT,
            split       TEXT
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS open_problems (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            paper_id    TEXT REFERENCES papers(id) ON DELETE CASCADE,
            text        TEXT,
            embedding   VECTOR(1536)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS paper_links (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id   TEXT REFERENCES papers(id) ON DELETE CASCADE,
            target_id   TEXT REFERENCES papers(id) ON DELETE CASCADE,
            link_type   TEXT,
            strength    FLOAT,
            metadata    JSONB,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (source_id, target_id, link_type)
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS researchers (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name                TEXT,
            institution         TEXT,
            semantic_scholar_id TEXT,
            github_username     TEXT,
            h_index             INT,
            citation_count      INT,
            research_themes     JSONB,
            paper_ids           JSONB,
            recent_repos        JSONB,
            refreshed_at        TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS hypotheses (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            text             TEXT,
            embedding        VECTOR(1536),
            status           TEXT DEFAULT 'open',
            evidence_for     JSONB DEFAULT '[]',
            evidence_against JSONB DEFAULT '[]',
            created_at       TIMESTAMPTZ DEFAULT NOW(),
            updated_at       TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS benchmark_drift (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            dataset     TEXT,
            metric      TEXT,
            model       TEXT,
            value       FLOAT,
            paper_id    TEXT REFERENCES papers(id) ON DELETE CASCADE,
            year        INT,
            recorded_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS idx_papers_title_embedding ON papers USING ivfflat (title_embedding vector_cosine_ops) WITH (lists = 100)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_claims_embedding ON claims USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_methods_embedding ON methods USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_hypotheses_embedding ON hypotheses USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_open_problems_embedding ON open_problems USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_benchmarks_dataset_metric ON benchmarks (dataset, metric)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_benchmark_drift ON benchmark_drift (dataset, metric, year)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_paper_links_source ON paper_links (source_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_paper_links_target ON paper_links (target_id)")


def downgrade() -> None:
    for table in [
        "benchmark_drift", "hypotheses", "researchers", "paper_links",
        "open_problems", "benchmarks", "methods", "claims", "papers",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
