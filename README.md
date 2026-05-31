# Lumen

Turn ML papers into structured knowledge. Paste an arxiv URL, get back claims, methods, benchmarks, and limitations — automatically linked to every other paper you've read.

## What it does

- **Ingest** any arxiv URL → extracts structured knowledge (claims, methods, benchmarks, limitations, open problems) via Claude
- **Links papers automatically** — by citation, shared methods, shared benchmarks, and contradictions
- **Contradiction detection** — flags when two papers report different numbers for the same model/dataset/metric
- **Hypothesis ledger** — write a hypothesis, Lumen watches every new paper for evidence that supports or refutes it
- **Frontier suggestions** — describe what you're working on, get 5 concrete research directions backed by your graph
- **Researcher profiles** — auto-enriched from Semantic Scholar + GitHub
- **Benchmark drift** — SOTA leaderboard over time across all ingested papers
- **RSS watcher** — daily arxiv feed ingestion, only pulls papers relevant to your existing graph

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + SQLAlchemy async + asyncpg |
| Database | PostgreSQL + pgvector |
| LLM | Claude (claude-sonnet-4-20250514) |
| Embeddings | BAAI/bge-small-en-v1.5 via FastEmbed (384-dim) |
| Graph | PostgreSQL-backed graph traversal |
| Frontend | Next.js 14 + Tailwind + D3 + Recharts + Zustand |

## Setup

**Prerequisites:** Docker Desktop, an Anthropic API key.

```bash
cp .env.example .env
# fill in your keys
docker compose up
```

Frontend: http://localhost:3000  
Backend API: http://localhost:8000/docs

## Environment variables

```
ANTHROPIC_API_KEY=
OPENAI_API_KEY=              # optional, only needed if EMBEDDING_PROVIDER=openai
EMBEDDING_PROVIDER=fastembed # fastembed or openai
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384
SEMANTIC_SCHOLAR_API_KEY=   # optional, increases rate limits
GITHUB_TOKEN=               # optional, enables repo cross-linking
NOTION_API_KEY=             # optional, required for /export/notion
CORS_ORIGINS=http://localhost:3000
AUTH_REQUIRED=false         # set true to enforce Clerk JWT
CLERK_ISSUER=https://clerk.your-domain.com
CLERK_AUDIENCE=
CLERK_JWKS_URL=https://clerk.your-domain.com/.well-known/jwks.json
```

## Multi-tenant auth headers

- Every request is scoped to a workspace via `X-Workspace-Id`.
- In local/dev mode (`AUTH_REQUIRED=false`), you can also pass `X-User-Id` and `X-Role`.
- In production (`AUTH_REQUIRED=true`), send `Authorization: Bearer <clerk_jwt>` and `X-Workspace-Id`.

## Running tests

```bash
cd backend
pytest tests/ -v
```

107 tests, no database required.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ingest` | Ingest paper by arxiv URL |
| POST | `/ingest/abstract` | Ingest by title + abstract |
| GET | `/papers` | List all ingested papers |
| GET | `/papers/{id}` | Paper detail + knowledge object |
| GET | `/papers/{id}/links` | All graph edges for a paper |
| GET | `/graph/full` | Full graph (nodes + edges) |
| GET | `/graph/contradictions` | All contradiction edges |
| POST | `/suggestions` | Frontier suggestions from notes |
| POST | `/hypotheses` | Add a hypothesis |
| GET | `/hypotheses` | List all hypotheses |
| GET | `/benchmarks/drift` | SOTA over time for dataset+metric |
| GET | `/rss/status` | RSS watcher status |
| POST | `/rss/run` | Trigger manual feed run |
