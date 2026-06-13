# Lumen

Lumen is a scientific memory system for ML research.

Core loop:

**Papers -> Claims/Benchmarks with provenance -> Conflicts/Evidence -> Hypothesis updates + notifications**

The v1 focus is narrow: help researchers track whether new papers support, refute, or qualify their hypotheses with cited evidence.

## Why it exists

Most research tools summarize papers once. Lumen is built for longitudinal belief tracking:

1. Write a hypothesis.
2. Ingest papers continuously.
3. See cited evidence/conflicts that impact that hypothesis.
4. Give feedback (`agree`/`disagree`) to improve trust.
5. Get notified when new evidence changes confidence.

## What is implemented (v1 core)

- Ingestion (`/ingest`, `/ingest/abstract`) with section-aware extraction foundation.
- Hypothesis ledger with normalized evidence and provenance (`cited_span`, `section`, `page_number`, reasoning).
- Benchmark conflicts with 4-level severity: `possible`, `likely`, `strong`, `verified`.
- Claim conflicts track with feedback.
- Feedback APIs for evidence and conflicts.
- Notification instrumentation events for the full loop.
- Light beige/cream UI with focused nav: `/`, `/hypotheses`, `/conflicts`.

For implementation details and current internal status, see `memory/project_lumen.md`.

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + SQLAlchemy async + asyncpg |
| Database | PostgreSQL + pgvector |
| LLM | Claude (Anthropic) |
| Embeddings | BAAI/bge-small-en-v1.5 via FastEmbed (384-dim) |
| Frontend | Next.js 14 + Tailwind + SWR |

## Quickstart

Prerequisites: Docker Desktop + Anthropic API key.

```bash
cp .env.example .env
# fill in ANTHROPIC_API_KEY (and optional email vars)
docker compose up
```

- Frontend: http://localhost:3000
- Backend API docs: http://localhost:8000/docs

## Environment variables

Required:

```bash
ANTHROPIC_API_KEY=
DATABASE_URL=postgresql+asyncpg://lumen:lumen@localhost:5432/lumen
```

Optional (email notifications):

```bash
EMAIL_PROVIDER=none            # none | resend | postmark
EMAIL_FROM="Lumen <noreply@lumen.local>"
RESEND_API_KEY=
POSTMARK_SERVER_TOKEN=
APP_BASE_URL=http://localhost:3000
```

Optional (auth/workspace):

```bash
AUTH_REQUIRED=false
CLERK_ISSUER=https://clerk.your-domain.com
CLERK_AUDIENCE=
CLERK_JWKS_URL=https://clerk.your-domain.com/.well-known/jwks.json
```

## Multi-tenant headers

- Workspace scoping uses `X-Workspace-Id`.
- In local/dev (`AUTH_REQUIRED=false`), you can also pass `X-User-Id` and `X-Role`.
- In production (`AUTH_REQUIRED=true`), send `Authorization: Bearer <clerk_jwt>` and `X-Workspace-Id`.

## Tests

```bash
cd backend
pytest tests/ -v
```

## Migration health check

Run before/after schema changes:

```bash
python db/migrations/check_health.py
```

It validates:
- revision/down_revision integrity
- single head
- no disconnected revisions
- migration-created tables reflected in `db/schema.sql`

## Key v1 endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/ingest` | Ingest paper by arXiv URL |
| POST | `/ingest/abstract` | Ingest title + abstract |
| GET | `/hypotheses` | List hypotheses with evidence |
| POST | `/hypotheses` | Create hypothesis |
| POST | `/hypotheses/evidence/{id}/feedback` | Evidence feedback |
| GET | `/conflicts` | Benchmark conflicts |
| POST | `/conflicts/{id}/feedback` | Benchmark conflict feedback |
| GET | `/conflicts/claims` | Claim conflicts |
| POST | `/conflicts/claims/{id}/feedback` | Claim conflict feedback |
| GET | `/notifications` | In-app notifications |
