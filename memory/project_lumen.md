---
name: Lumen project overview
description: Core facts about the Lumen codebase — stack, layout, known issues fixed, how to run
type: project
---

Lumen is a research intelligence layer for ML practitioners. Ingest an arxiv URL → get a structured KnowledgeObject (claims, methods, benchmarks, limitations) → auto-link to graph → contradiction detection, hypothesis ledger, frontier suggestions.

**Why:** Built to fill the gap between "just a paper summarizer" and a full knowledge accumulation system.

**Stack:**
- Backend: FastAPI + SQLAlchemy async + asyncpg + PostgreSQL + pgvector
- LLM: Claude (claude-sonnet-4-20250514) via Anthropic SDK
- Embeddings: text-embedding-3-small via OpenAI SDK (1536-dim)
- Graph: NetworkX in-memory DiGraph
- Frontend: Next.js 14 (App Router) + Tailwind + D3 + Recharts + Zustand + SWR

**How to run:**
- Requires Docker Desktop running: `docker compose up` from repo root
- Backend runs on port 8000, frontend on port 3000
- Needs .env file with ANTHROPIC_API_KEY, OPENAI_API_KEY, SEMANTIC_SCHOLAR_API_KEY, GITHUB_TOKEN
- Tests (no DB needed): `cd backend && pytest tests/ -v` — 107 tests, all pass

**Bugs fixed (2026-04-29):**
1. `frontend/next.config.ts` → renamed to `next.config.mjs` (Next.js 14 doesn't support .ts config)
2. `frontend/app/graph/page.tsx` — `useState` import was at bottom of file; moved to top; fixed `selectedEdge as GraphEdge` cast (needs `as unknown as GraphEdge`)
3. `frontend/components/KnowledgeGraph.tsx` — `d.source`/`d.target` casts needed `as unknown as GraphNode`
4. `frontend/app/globals.css` — `@import` for Google Fonts moved above `@tailwind` directives
5. `backend/ingestion/rss.py` — authors were extracted from RSS category tags instead of `entry.authors`
6. Next.js upgraded from 14.2.3 → 14.2.35 (security patches); full Next.js 15/16 upgrade still pending

**How to apply:** When making changes, run `cd backend && pytest tests/` and `cd frontend && node_modules/.bin/next build` to verify nothing broke.
