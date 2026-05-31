CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION current_workspace_id() RETURNS UUID
LANGUAGE SQL STABLE AS $$
    SELECT NULLIF(current_setting('app.current_workspace_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION current_user_id() RETURNS UUID
LANGUAGE SQL STABLE AS $$
    SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION current_role() RETURNS TEXT
LANGUAGE SQL STABLE AS $$
    SELECT NULLIF(current_setting('app.current_role', true), '')
$$;

CREATE TABLE IF NOT EXISTS users (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_subject TEXT UNIQUE NOT NULL,
    email            TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspaces (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workspace_memberships (
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role         TEXT NOT NULL CHECK (role IN ('viewer', 'editor', 'admin', 'owner')),
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE IF NOT EXISTS papers (
    id              TEXT PRIMARY KEY,
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
    title           TEXT NOT NULL,
    authors         JSONB,
    year            INT,
    arxiv_url       TEXT,
    pdf_url         TEXT,
    raw_text        TEXT,
    knowledge_obj   JSONB,
    title_embedding VECTOR(384),
    ingested_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS claims (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
    paper_id     TEXT REFERENCES papers(id) ON DELETE CASCADE,
    text         TEXT,
    confidence   FLOAT,
    evidence     TEXT,
    embedding    VECTOR(384)
);

CREATE TABLE IF NOT EXISTS methods (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
    paper_id     TEXT REFERENCES papers(id) ON DELETE CASCADE,
    name         TEXT,
    description  TEXT,
    is_novel     BOOLEAN,
    embedding    VECTOR(384)
);

CREATE TABLE IF NOT EXISTS benchmarks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
    paper_id     TEXT REFERENCES papers(id) ON DELETE CASCADE,
    dataset      TEXT,
    metric       TEXT,
    value        FLOAT,
    model        TEXT,
    split        TEXT
);

CREATE TABLE IF NOT EXISTS open_problems (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
    paper_id     TEXT REFERENCES papers(id) ON DELETE CASCADE,
    text         TEXT,
    embedding    VECTOR(384)
);

CREATE TABLE IF NOT EXISTS paper_links (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
    source_id    TEXT REFERENCES papers(id) ON DELETE CASCADE,
    target_id    TEXT REFERENCES papers(id) ON DELETE CASCADE,
    link_type    TEXT,
    strength     FLOAT,
    metadata     JSONB,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (workspace_id, source_id, target_id, link_type)
);

CREATE TABLE IF NOT EXISTS researchers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
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
);

CREATE TABLE IF NOT EXISTS hypotheses (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id     UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
    text             TEXT,
    embedding        VECTOR(384),
    status           TEXT DEFAULT 'open',
    evidence_for     JSONB DEFAULT '[]',
    evidence_against JSONB DEFAULT '[]',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS benchmark_drift (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
    dataset      TEXT,
    metric       TEXT,
    model        TEXT,
    value        FLOAT,
    paper_id     TEXT REFERENCES papers(id) ON DELETE CASCADE,
    year         INT,
    recorded_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notifications (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
    type         TEXT NOT NULL,
    message      TEXT NOT NULL,
    payload      JSONB DEFAULT '{}',
    read         BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS claim_lineage (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
    parent_claim_id UUID REFERENCES claims(id) ON DELETE CASCADE,
    child_claim_id  UUID REFERENCES claims(id) ON DELETE CASCADE,
    relation        TEXT,
    confidence      FLOAT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (workspace_id, parent_claim_id, child_claim_id)
);

-- Global reference table by design (unscoped)
CREATE TABLE IF NOT EXISTS benchmark_metadata (
    dataset          TEXT PRIMARY KEY,
    known_issues     JSONB DEFAULT '[]',
    first_year       INT,
    common_criticism TEXT
);

CREATE TABLE IF NOT EXISTS memory_events (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE DEFAULT current_workspace_id(),
    type         TEXT NOT NULL,
    subject_id   TEXT,
    subject_type TEXT,
    content      TEXT NOT NULL,
    embedding    VECTOR(384),
    occurred_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workspace_memberships_user ON workspace_memberships (user_id);
CREATE INDEX IF NOT EXISTS idx_papers_workspace ON papers (workspace_id);
CREATE INDEX IF NOT EXISTS idx_claims_workspace ON claims (workspace_id);
CREATE INDEX IF NOT EXISTS idx_methods_workspace ON methods (workspace_id);
CREATE INDEX IF NOT EXISTS idx_benchmarks_workspace ON benchmarks (workspace_id);
CREATE INDEX IF NOT EXISTS idx_open_problems_workspace ON open_problems (workspace_id);
CREATE INDEX IF NOT EXISTS idx_paper_links_workspace ON paper_links (workspace_id);
CREATE INDEX IF NOT EXISTS idx_researchers_workspace ON researchers (workspace_id);
CREATE INDEX IF NOT EXISTS idx_hypotheses_workspace ON hypotheses (workspace_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_drift_workspace ON benchmark_drift (workspace_id);
CREATE INDEX IF NOT EXISTS idx_notifications_workspace ON notifications (workspace_id);
CREATE INDEX IF NOT EXISTS idx_claim_lineage_workspace ON claim_lineage (workspace_id);
CREATE INDEX IF NOT EXISTS idx_memory_events_workspace ON memory_events (workspace_id);

CREATE INDEX IF NOT EXISTS idx_papers_title_embedding ON papers USING hnsw (title_embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_claims_embedding ON claims USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_methods_embedding ON methods USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_hypotheses_embedding ON hypotheses USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_open_problems_embedding ON open_problems USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_memory_events_embedding ON memory_events USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_papers_title_trgm ON papers USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_benchmarks_dataset_metric ON benchmarks (dataset, metric);
CREATE INDEX IF NOT EXISTS idx_benchmark_drift_dataset_metric_year ON benchmark_drift (dataset, metric, year);
CREATE INDEX IF NOT EXISTS idx_paper_links_source ON paper_links (source_id);
CREATE INDEX IF NOT EXISTS idx_paper_links_target ON paper_links (target_id);
CREATE INDEX IF NOT EXISTS idx_claim_lineage_parent ON claim_lineage (parent_claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_lineage_child ON claim_lineage (child_claim_id);
CREATE INDEX IF NOT EXISTS idx_memory_events_type ON memory_events (type, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_events_subject ON memory_events (subject_id);
