"""Add claim_lineage and benchmark_metadata tables

Revision ID: 003
Revises: 002
Create Date: 2026-05-31
"""

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS claim_lineage (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            parent_claim_id UUID REFERENCES claims(id) ON DELETE CASCADE,
            child_claim_id  UUID REFERENCES claims(id) ON DELETE CASCADE,
            relation        TEXT,
            confidence      FLOAT,
            created_at      TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (parent_claim_id, child_claim_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_claim_lineage_parent ON claim_lineage (parent_claim_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_claim_lineage_child  ON claim_lineage (child_claim_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS benchmark_metadata (
            dataset          TEXT PRIMARY KEY,
            known_issues     JSONB DEFAULT '[]',
            first_year       INT,
            common_criticism TEXT
        )
    """)

    # Seed known contaminated/problematic benchmarks
    op.execute("""
        INSERT INTO benchmark_metadata (dataset, known_issues, first_year, common_criticism)
        VALUES
            ('MMLU', '["contamination", "saturation"]', 2020,
             'Widespread contamination in LLM pretraining data; approaching saturation with GPT-4-level models'),
            ('GSM8K', '["contamination", "memorization"]', 2021,
             'Strong memorization risk; many models may have seen training solutions'),
            ('HumanEval', '["narrow", "contamination"]', 2021,
             'Only 164 problems; narrow coverage of Python programming tasks; solutions leaked into training data'),
            ('BIG-Bench', '["saturation"]', 2022,
             'Several tasks now saturated by frontier models'),
            ('HellaSwag', '["saturation", "contamination"]', 2019,
             'Near-human or above-human performance reached; high contamination risk'),
            ('TruthfulQA', '["narrow"]', 2021,
             'Only 817 questions; may not generalize to broader truthfulness evaluation'),
            ('MATH', '["contamination"]', 2021,
             'High contamination risk in recent frontier model training data'),
            ('MBPP', '["narrow", "contamination"]', 2021,
             'Crowdsourced problems with variable quality; contamination risk similar to HumanEval')
        ON CONFLICT (dataset) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS claim_lineage CASCADE")
    op.execute("DROP TABLE IF EXISTS benchmark_metadata CASCADE")
