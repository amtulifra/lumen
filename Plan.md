# Lumen — Implementation Plan

> Turn ML papers into structured knowledge objects.
> Link them. Surface researcher profiles. Suggest what to build next.

**Name**: Lumen — light that reveals what's hidden. A paper goes in,
structure comes out. Your research, illuminated.

---

## What lumen is

A research intelligence layer for ML practitioners. You paste in an arxiv URL
or abstract. lumen extracts structured knowledge — claims, methods, benchmarks,
limitations — and links it to every other paper you've ingested. Over time it
builds a graph of the ML research landscape as *you* see it, enriched with
researcher profiles, contradiction detection, and frontier suggestions from
your own notes.

The goal: never lose track of what you've read, what it means, and what's
missing.

---

## What makes lumen different from "just a paper summarizer"

| Tool | What it does | What it misses |
|------|-------------|----------------|
| ChatPDF / ask-a-PDF | Q&A over one paper | No memory, no links, no graph |
| Semantic Scholar | Citation graph | No structured extraction, no your-notes integration |
| Zotero / Mendeley | Reference manager | No semantic understanding, no frontier suggestions |
| Kagi / Elicit | Paper search | No knowledge accumulation across sessions |
| **lumen** | All of the above, unified | — |

The key primitive that makes lumen different: the **knowledge object**. Every
paper becomes a structured dict — not a summary, not a chat — that can be
indexed, linked, diffed, and queried programmatically.

---

## Improvements Over Salma's Original lumen

| # | Type | What | Why |
|---|------|------|-----|
| 1 | New | Contradiction detection | Flag when paper B silently contradicts paper A's benchmark numbers |
| 2 | New | BenchmarkDrift tracking | Track SOTA leaderboard shifts over time across all ingested papers |
| 3 | New | Hypothesis ledger | Write down open questions — lumen watches for evidence that supports or refutes them |
| 4 | New | Author GitHub cross-linking | Match paper titles to actual repo names using Claude |
| 5 | New | Streaming ingestion | Ingest from arxiv RSS feeds automatically, not just manual paste |
| 6 | New | Method similarity linking | Embed method descriptions, link papers that share techniques even without explicit citations |
| 7 | New | Open-problem extraction | Explicitly extract what each paper says it leaves for future work |
| 8 | New | Claim confidence scoring | Score each extracted claim by how well-supported it is in the paper |

---

## Architecture Overview

```
lumen/
  backend/                        # FastAPI Python service
    ingestion/
      arxiv.py                    # Fetch paper metadata + PDF via arxiv API
      pdf.py                      # Extract full text via pdfplumber
      extractor.py                # Claude-powered structured extraction
      rss.py                      # [NEW] arxiv RSS feed watcher
    knowledge/
      schema.py                   # KnowledgeObject dataclass
      store.py                    # PostgreSQL + pgvector storage
      embedder.py                 # text-embedding-3-small via OpenAI API
      graph.py                    # NetworkX knowledge graph
    linking/
      citation.py                 # Exact citation match via title lookup
      method.py                   # [NEW] Method embedding similarity linking
      benchmark.py                # [NEW] Shared dataset detection + number comparison
      contradiction.py            # [NEW] Contradiction detection across benchmarks
    researchers/
      profiles.py                 # Author profile builder
      semantic_scholar.py         # Semantic Scholar API client
      github.py                   # [NEW] GitHub API cross-linker
    suggestions/
      frontier.py                 # RAG + Claude reasoning for suggestions
      hypotheses.py               # [NEW] Hypothesis ledger + evidence watcher
      benchmark_drift.py          # [NEW] SOTA leaderboard tracker
    api/
      routes.py                   # FastAPI endpoints
      models.py                   # Pydantic request/response models

  frontend/                       # Next.js app
    pages/
      index.tsx                   # Paper ingest box
      graph.tsx                   # Knowledge graph visualization (D3)
      paper/[id].tsx              # Per-paper knowledge object viewer
      researchers/[id].tsx        # Researcher profile card
      frontier.tsx                # Notes → suggestions panel
      hypotheses.tsx              # [NEW] Hypothesis ledger
      benchmarks.tsx              # [NEW] BenchmarkDrift leaderboard

  db/
    migrations/                   # Alembic migrations
    schema.sql                    # Full schema

  docs/
    DESIGN.md
    API.md

  docker-compose.yml
  pyproject.toml
  package.json
```

---

## The Knowledge Object

This is the atom of the whole system. Every ingested paper becomes one.

```python
@dataclass
class KnowledgeObject:
    # Identity
    paper_id:       str           # arxiv ID or hash of title
    title:          str
    authors:        list[str]
    year:           int
    arxiv_url:      str
    pdf_url:        str

    # Claude-extracted structure
    claims:         list[Claim]         # core contributions
    methods:        list[Method]        # techniques, architectures, algorithms
    benchmarks:     list[Benchmark]     # dataset + metric + reported number
    limitations:    list[str]           # what the authors admit doesn't work
    open_problems:  list[str]           # [NEW] explicit future work items
    related_work:   list[str]           # cited paper titles

    # Computed
    claim_embeddings:   np.ndarray      # for similarity search
    method_embeddings:  np.ndarray      # for method linking
    keywords:           list[str]       # for graph linking

    # Graph edges (populated after linking)
    cites:          list[str]           # paper_ids this paper cites
    cited_by:       list[str]           # paper_ids that cite this
    shares_method:  list[MethodLink]    # papers sharing similar methods
    benchmarks_on:  list[BenchLink]     # papers on same datasets
    contradicts:    list[ContradLink]   # [NEW] papers with conflicting numbers

@dataclass
class Claim:
    text:       str
    confidence: float       # [NEW] 0-1, how well-supported in paper body
    evidence:   str         # quote or paraphrase supporting this claim

@dataclass
class Benchmark:
    dataset:    str         # e.g. "ImageNet", "MMLU", "HumanEval"
    metric:     str         # e.g. "top-1 accuracy", "pass@1"
    value:      float       # e.g. 89.2
    model:      str         # e.g. "GPT-4o", "Llama-3-70B"
    split:      str         # e.g. "test", "validation"
```

---

## The Extraction Prompt

The quality of lumen lives or dies on this. The system prompt sent to Claude
for every ingested paper:

```
You are a structured ML paper extractor. Given a paper's full text, extract
a JSON object with EXACTLY these fields. Be precise and conservative.

{
  "claims": [
    {
      "text": "<one sentence, the core contribution>",
      "confidence": <0.0-1.0, how explicitly stated vs implied>,
      "evidence": "<direct quote or close paraphrase from paper>"
    }
  ],
  "methods": [
    {
      "name": "<method/technique/architecture name>",
      "description": "<one sentence>",
      "is_novel": <true if introduced in this paper, false if borrowed>
    }
  ],
  "benchmarks": [
    {
      "dataset": "<exact dataset name>",
      "metric": "<exact metric name>",
      "value": <number only, no % sign>,
      "model": "<model name being evaluated>",
      "split": "<test/val/train>"
    }
  ],
  "limitations": ["<one per item, stated by the authors>"],
  "open_problems": ["<explicit future work items stated in the paper>"],
  "related_work": ["<exact titles of papers they cite that matter most>"],
  "keywords": ["<5-10 technical terms that characterize this work>"]
}

Return ONLY the JSON object. No preamble, no explanation, no markdown fences.
```

---

## Database Schema

```sql
-- Papers and their knowledge objects
CREATE TABLE papers (
    id              TEXT PRIMARY KEY,       -- arxiv ID
    title           TEXT NOT NULL,
    authors         JSONB,                  -- list of author names
    year            INT,
    arxiv_url       TEXT,
    pdf_url         TEXT,
    raw_text        TEXT,                   -- full extracted PDF text
    knowledge_obj   JSONB,                  -- full KnowledgeObject as JSON
    title_embedding VECTOR(1536),           -- for similarity search
    ingested_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Individual claims with embeddings
CREATE TABLE claims (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id    TEXT REFERENCES papers(id),
    text        TEXT,
    confidence  FLOAT,
    evidence    TEXT,
    embedding   VECTOR(1536)
);

-- Individual methods with embeddings
CREATE TABLE methods (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id    TEXT REFERENCES papers(id),
    name        TEXT,
    description TEXT,
    is_novel    BOOLEAN,
    embedding   VECTOR(1536)
);

-- Benchmark results
CREATE TABLE benchmarks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id    TEXT REFERENCES papers(id),
    dataset     TEXT,
    metric      TEXT,
    value       FLOAT,
    model       TEXT,
    split       TEXT
);

-- Graph edges between papers
CREATE TABLE paper_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       TEXT REFERENCES papers(id),
    target_id       TEXT REFERENCES papers(id),
    link_type       TEXT,   -- CITES | SHARES_METHOD | BENCHMARKS_ON | CONTRADICTS
    strength        FLOAT,  -- cosine similarity for method links
    metadata        JSONB,  -- contradiction details, shared dataset name, etc.
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Researcher profiles
CREATE TABLE researchers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT,
    institution     TEXT,
    semantic_scholar_id TEXT,
    github_username TEXT,
    h_index         INT,
    citation_count  INT,
    research_themes JSONB,  -- Claude-extracted from body of work
    paper_ids       JSONB,  -- list of arxiv IDs
    refreshed_at    TIMESTAMPTZ
);

-- [NEW] Hypothesis ledger
CREATE TABLE hypotheses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text            TEXT,           -- the hypothesis as written by user
    embedding       VECTOR(1536),
    status          TEXT DEFAULT 'open',  -- open | supported | refuted | mixed
    evidence_for    JSONB,          -- list of {paper_id, claim_text, strength}
    evidence_against JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- [NEW] BenchmarkDrift: SOTA history per dataset+metric
CREATE TABLE benchmark_drift (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset     TEXT,
    metric      TEXT,
    model       TEXT,
    value       FLOAT,
    paper_id    TEXT REFERENCES papers(id),
    year        INT,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX ON papers USING ivfflat (title_embedding vector_cosine_ops);
CREATE INDEX ON claims USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON methods USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON hypotheses USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON benchmarks (dataset, metric);
CREATE INDEX ON benchmark_drift (dataset, metric, year);
```

---

## Phase 0 — Setup
**Timeline: Day 1**

### Tasks

- Initialize monorepo: `backend/` (FastAPI) + `frontend/` (Next.js)
- Set up PostgreSQL + pgvector with Docker Compose
- Set up Alembic for migrations, run initial schema
- Configure environment: Anthropic API key, OpenAI API key (embeddings),
  Semantic Scholar API key, GitHub token
- Confirm `POST /ingest` returns 200 with a stub response

### Deliverable
Running Docker Compose stack: Postgres + pgvector + FastAPI + Next.js shell.

---

## Phase 1 — Paper Ingestion + Extraction
**Timeline: Days 2–6**

The foundation. Everything else depends on extraction quality.

### Tasks

**arxiv fetcher (`ingestion/arxiv.py`)**

Accept either an arxiv URL (`https://arxiv.org/abs/2305.XXXXX`) or raw abstract
text. For arxiv URLs: call the arxiv API to get title, authors, year, abstract,
PDF URL. Parse the arxiv ID from the URL.

```python
import arxiv

def fetch_paper(url: str) -> dict:
    arxiv_id = url.split("/abs/")[-1].strip()
    paper = next(arxiv.Client().results(arxiv.Search(id_list=[arxiv_id])))
    return {
        "id": arxiv_id,
        "title": paper.title,
        "authors": [a.name for a in paper.authors],
        "year": paper.published.year,
        "abstract": paper.summary,
        "pdf_url": paper.pdf_url,
        "arxiv_url": url,
    }
```

**PDF extractor (`ingestion/pdf.py`)**

Download the PDF, extract full text with `pdfplumber`. Strip headers, footers,
figure captions, and reference lists — they confuse the extraction prompt.
Truncate to 12,000 tokens (Claude's context is large but costs money). Priority
order: abstract → introduction → methods → results → conclusion → limitations.

**Claude extractor (`ingestion/extractor.py`)**

Call Claude with the extraction prompt above. Parse the JSON response. Validate
all fields are present and correctly typed. On parse failure, retry once with
an explicit error message. Store the raw response alongside the parsed object
for debugging.

**Embedder (`knowledge/embedder.py`)**

After extraction, embed: the paper title (for paper-level similarity), each
claim text, each method description, and for hypothesis ledger, the open
problems list. Use `text-embedding-3-small` via the OpenAI API. Store all
embeddings in pgvector.

**API endpoint**

```
POST /ingest
Body: { "url": "https://arxiv.org/abs/..." }
   or { "abstract": "...", "title": "..." }

Response: { "paper_id": "...", "knowledge_object": {...} }
```

### Deliverable
- Paste any arxiv URL → get back a fully structured KnowledgeObject in < 30s
- All claims, methods, benchmarks, limitations, open problems extracted
- All embeddings stored in pgvector
- Unit tests: extraction on 10 known papers, manually verify output quality

---

## Phase 2 — Knowledge Graph + Linking
**Timeline: Days 7–12**

This is what separates lumen from "just a paper summarizer."

### Citation linking (`linking/citation.py`)

When a new paper is ingested, look up each title in `related_work` against the
`papers` table. Exact title match → create a `CITES` edge in `paper_links`.
Fuzzy match (Levenshtein distance < 3) → create a tentative edge, flag for
review. Store unmatched titles for future resolution when those papers are
ingested later.

### Method similarity linking (`linking/method.py`) — new

Embed each extracted method description. For each method in the new paper,
run a pgvector cosine search against all stored method embeddings. Threshold
at 0.85 similarity. Create a `SHARES_METHOD` edge with the similarity score
and the matched method names in metadata. This links papers that share
techniques even without explicit citations — the most powerful linker.

```python
def link_by_method(paper_id: str, methods: list[Method], db: Session):
    for method in methods:
        results = db.execute("""
            SELECT paper_id, name, 1 - (embedding <=> %s) AS similarity
            FROM methods
            WHERE paper_id != %s
            AND 1 - (embedding <=> %s) > 0.85
            ORDER BY similarity DESC
            LIMIT 5
        """, (method.embedding, paper_id, method.embedding))
        for row in results:
            create_link(paper_id, row.paper_id, "SHARES_METHOD",
                        strength=row.similarity,
                        metadata={"method_a": method.name, "method_b": row.name})
```

### Benchmark overlap linking (`linking/benchmark.py`) — new

Two papers that report results on the same dataset+metric are always linked.
Simple SQL: find all rows in `benchmarks` where `dataset` and `metric` match,
create a `BENCHMARKS_ON` edge with the dataset name in metadata.

### Contradiction detection (`linking/contradiction.py`) — new

For every `BENCHMARKS_ON` pair: compare the reported values. If paper A reports
X% and paper B reports Y% for the same `(dataset, metric, model)` tuple and
|X - Y| > 1.0 (more than 1 point difference), create a `CONTRADICTS` edge.
Store the discrepancy in metadata. Flag it in the UI.

This is the feature no one else has. Two papers claiming different numbers for
the same model on the same benchmark is extremely common and almost never
surfaced automatically.

```python
def detect_contradictions(paper_id: str, benchmarks: list[Benchmark], db):
    for bm in benchmarks:
        existing = db.execute("""
            SELECT b.paper_id, b.value
            FROM benchmarks b
            WHERE b.dataset = %s AND b.metric = %s AND b.model = %s
            AND b.paper_id != %s
        """, (bm.dataset, bm.metric, bm.model, paper_id))
        for row in existing:
            if abs(bm.value - row.value) > 1.0:
                create_link(paper_id, row.paper_id, "CONTRADICTS",
                    metadata={
                        "dataset": bm.dataset,
                        "metric": bm.metric,
                        "model": bm.model,
                        "value_a": bm.value,
                        "value_b": row.value,
                        "delta": bm.value - row.value
                    })
```

### NetworkX graph (`knowledge/graph.py`)

Maintain an in-memory NetworkX DiGraph that mirrors the `paper_links` table.
Rebuild from DB on startup. Update incrementally on each ingest. Expose:
- `neighbors(paper_id, link_type)` — papers linked by a specific edge type
- `shortest_path(a, b)` — how two papers are connected
- `subgraph(paper_id, depth=2)` — the local neighborhood for graph viz

### API endpoints

```
GET  /papers/{id}/links          — all edges for a paper
GET  /graph/subgraph/{id}        — D3-ready node/edge JSON for viz
GET  /graph/contradictions       — all CONTRADICTS edges in the graph
GET  /papers/{id}/neighbors      — papers linked to this one, by type
```

### Deliverable
- Ingest 20 papers in the same area → observe automatic linking
- At least one contradiction detected and flagged across the 20 papers
- Method similarity links appearing for papers that share architectures
  (e.g., two papers that both use LoRA should be linked)

---

## Phase 3 — Researcher Profiles
**Timeline: Days 13–16**

### Author enrichment (`researchers/`)

For each author extracted from an ingested paper:

**Semantic Scholar** (`researchers/semantic_scholar.py`)
Query the Semantic Scholar API by author name. Get: all papers, citation
counts, h-index, co-authors, institution. Match the right author (name
collisions are common) using institution + co-author overlap.

**GitHub cross-linking** (`researchers/github.py`) — new
Search GitHub for repos whose name or description contains the paper title
keywords. For each author, also search for `"{author_name}" "{institution}"`.
Rank candidates by: repo name matches paper title, repo created near paper
date, README mentions the paper. Use Claude to confirm the match:
`"Does this GitHub repo (README below) correspond to this paper (title/abstract below)?"`

**Research theme extraction**
Pass an author's last 10 paper titles to Claude:
`"Extract 5 research themes that characterize this researcher's body of work. Return as a JSON list of strings."`
Store as `research_themes` on the profile.

**Profile schema**

```python
@dataclass
class ResearcherProfile:
    name:               str
    institution:        str
    semantic_scholar_id: str
    github_username:    str | None
    h_index:            int
    citation_count:     int
    research_themes:    list[str]
    paper_ids:          list[str]       # arxiv IDs in our DB
    recent_papers:      list[str]       # last 3 paper titles
    recent_repos:       list[str]       # last 3 GitHub repos
    refreshed_at:       datetime
```

**Refresh cadence**: profiles refresh weekly via a cron job.
`POST /researchers/{id}/refresh` triggers a manual refresh.

### API endpoints

```
GET  /researchers/{id}           — full profile
GET  /papers/{id}/researchers    — all author profiles for a paper
POST /researchers/{id}/refresh   — trigger profile refresh
```

### Deliverable
- Ingest a paper → all authors get profiles automatically
- At least one author with a GitHub account gets their repos cross-linked
- Research themes generated and stored for each author

---

## Phase 4 — Frontier Suggestions
**Timeline: Days 17–21**

### Notes → suggestions (`suggestions/frontier.py`)

The user pastes their current research notes or hypotheses. lumen:

1. Embed the notes, retrieve the top-10 most similar papers already in the graph
2. Retrieve the top-10 most similar open problems from all ingested papers
3. Find methods from one subfield that haven't been applied to the problem
   area implied by the notes (method gap detection)
4. Pass everything to Claude:

```python
SUGGESTION_PROMPT = """
You are a research advisor helping an ML researcher find their next project.

Here is what they are currently working on / thinking about:
{user_notes}

Here are the most relevant papers they have already read:
{relevant_papers}

Here are open problems from papers in this area that haven't been solved:
{open_problems}

Here are methods from adjacent areas that haven't been applied here:
{method_gaps}

Suggest 5 specific, concrete frontier research directions. For each:
- State the direction in one sentence
- Explain why it's promising (what gap it fills)
- Name 2-3 papers the researcher should read first
- Estimate difficulty: [1-week project | 1-month project | PhD-level]

Return as a JSON array.
"""
```

### Hypothesis ledger (`suggestions/hypotheses.py`) — new

The user writes down an open hypothesis: *"I think sparse attention patterns
are sufficient for in-context learning, dense attention is redundant."*

lumen:
1. Embeds the hypothesis, stores it in the `hypotheses` table
2. On every new paper ingestion, runs a similarity search: does this paper's
   claims or findings relate to any stored hypothesis?
3. If similarity > 0.80, uses Claude to judge: does this paper support,
   refute, or give mixed evidence for the hypothesis?
4. Updates the hypothesis's `evidence_for` / `evidence_against` lists
5. Sends a notification (email or in-app badge) when a hypothesis gets new
   evidence

This is the feature that makes lumen feel like a research partner rather than
a search tool.

### BenchmarkDrift tracker (`suggestions/benchmark_drift.py`) — new

For every `(dataset, metric)` pair in the `benchmark_drift` table, compute
the SOTA over time: the highest reported value per year. Expose as a time
series. Surface: "GPT-4o held SOTA on MMLU pass@1 until paper X in 2025,
which improved it by 2.3 points." Flag when a paper in your graph gets
surpassed by a newly ingested paper.

### API endpoints

```
POST /suggestions
Body: { "notes": "..." }
Response: { "suggestions": [...], "relevant_papers": [...] }

POST /hypotheses
Body: { "text": "..." }

GET  /hypotheses
GET  /hypotheses/{id}

GET  /benchmarks/drift?dataset=MMLU&metric=pass@1
```

### Deliverable
- Write 3 research notes → get 5 concrete frontier suggestions with paper refs
- Write 2 hypotheses → ingest 5 related papers → see evidence accumulate
- BenchmarkDrift chart showing MMLU SOTA over time across ingested papers

---

## Phase 5 — arxiv RSS Watcher
**Timeline: Days 22–24**

### Streaming ingestion (`ingestion/rss.py`) — new

arxiv publishes daily RSS feeds per category. Subscribe to the feeds for
categories you care about (cs.LG, cs.CL, cs.CV, stat.ML). On each new paper:
1. Check if it's relevant to anything in your graph (embed abstract, check
   cosine similarity to existing papers — threshold 0.75)
2. If relevant: auto-ingest, run full extraction + linking + hypothesis check
3. If not: discard silently

Run as a background task via APScheduler, firing daily at 6am.

```python
RSS_FEEDS = {
    "cs.LG": "https://rss.arxiv.org/rss/cs.LG",
    "cs.CL": "https://rss.arxiv.org/rss/cs.CL",
    "cs.CV": "https://rss.arxiv.org/rss/cs.CV",
}

async def watch_feeds(db: Session):
    for category, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            if is_relevant(entry.summary, db):
                await ingest_paper(entry.link, db)
```

### API endpoints

```
GET  /rss/status             — last run time, papers ingested today
POST /rss/run                — trigger manual feed run
GET  /rss/subscriptions      — active category subscriptions
POST /rss/subscriptions      — add a category
```

### Deliverable
- RSS watcher running daily, auto-ingesting relevant papers
- Hypothesis ledger automatically updated when a new paper provides evidence

---

## Phase 6 — Frontend
**Timeline: Days 25–31**

Clean, minimal, terminal-adjacent aesthetic. Salma's projects feel like they
were built by someone who reads papers and hates clutter. Match that.

### Pages

**`/` — Ingest**
Large text area for arxiv URL or abstract. Sample paper buttons (Attention is
All You Need, LoRA, Mamba, RLHF). On submit: show extraction progress step by
step (`Fetching PDF...` → `Extracting knowledge...` → `Linking to graph...`).
Display the resulting KnowledgeObject inline — claims, methods, benchmarks,
limitations all expandable. Show auto-detected links immediately.

**`/graph` — Knowledge Graph**
D3 force-directed graph. Nodes = papers, sized by citation count. Edges colored
by type: gray (CITES), green (SHARES_METHOD), blue (BENCHMARKS_ON), red
(CONTRADICTS). Click a node → panel slides in with the paper's KnowledgeObject.
Click an edge → panel shows edge type + metadata (e.g., the contradiction
details). Filters: show only CONTRADICTS edges, show only papers from 2024+.

**`/paper/[id]` — Paper Detail**
Full KnowledgeObject displayed. Claims with confidence scores. Methods tagged
novel vs borrowed. Benchmarks in a table, with a sparkline showing how this
paper's numbers compare to others on the same dataset. Linked papers by type.
Author cards with GitHub links.

**`/researchers/[id]` — Researcher Profile**
Photo (from GitHub), institution, h-index, citation count, research themes as
tags. Timeline of their papers. GitHub repos cross-linked to papers. Co-author
network (small D3 graph).

**`/frontier` — Frontier Suggestions**
Large textarea: "What are you thinking about?" Submit → suggestions rendered
as cards with difficulty tag, why-it's-promising, and paper recommendations.

**`/hypotheses` — Hypothesis Ledger**
List of open hypotheses with status badges (open / supported / refuted /
mixed). Click one → evidence timeline: each paper that weighed in, its verdict,
its claim. Add new hypothesis via text field at the top.

**`/benchmarks` — BenchmarkDrift**
Dataset selector + metric selector → line chart of SOTA over time. Hover any
point → paper title, authors, arxiv link. Red dot = a contradiction exists
for this data point.

### Tech stack

```
Framework:      Next.js 14 (App Router)
Styling:        Tailwind CSS
Graph viz:      D3.js (force-directed, custom)
Charts:         Recharts (line charts, sparklines)
Font:           Geist Mono (monospace, matches the aesthetic)
State:          Zustand
Data fetching:  SWR
```

### Deliverable
- All 7 pages working end-to-end
- Knowledge graph rendering 50+ papers without performance issues
- Contradiction edges visible and clickable in the graph

---

## Tech Stack

| Component | Choice | Reason |
|-----------|--------|--------|
| Backend | FastAPI (Python) | Async, easy to prototype, great for ML tooling |
| LLM extraction | Claude claude-sonnet-4-20250514 | Best structured extraction quality |
| Embeddings | text-embedding-3-small | Fast, cheap, 1536-dim |
| Database | PostgreSQL + pgvector | Vectors + relational in one, no extra infra |
| Graph | NetworkX (in-memory) | Simple, fast for < 10k nodes |
| PDF parsing | pdfplumber | Most reliable text extraction |
| External APIs | arxiv, Semantic Scholar, GitHub | Paper metadata + author enrichment |
| RSS | feedparser + APScheduler | Daily arxiv feed ingestion |
| Frontend | Next.js 14 + D3 + Recharts | Graph viz + clean UI |
| Containerization | Docker Compose | One-command local setup |

---

## What to Read Before Building

| Resource | What it teaches |
|----------|----------------|
| arxiv API docs | How to fetch papers, metadata, PDFs |
| Semantic Scholar API docs | Author lookup, citation data |
| pgvector README | How to store + query vectors in Postgres |
| D3 force simulation docs | How to build the knowledge graph viz |
| Elicit.com (use it) | What a good paper AI tool feels like from the user side |

---

## Where to Start

**Minimum lovable version — end of week 1:**

1. Day 1: Docker Compose stack running (Postgres + pgvector + FastAPI)
2. Days 2–3: `POST /ingest` working — paste arxiv URL, get KnowledgeObject back
3. Days 4–5: Benchmark linking + contradiction detection working
4. Day 6: Basic Next.js page showing the KnowledgeObject
5. Day 7: Ingest 10 papers in one area, find the first contradiction

The first time you ingest two papers that contradict each other and lumen
catches it automatically — that's the moment the project becomes real.

---

## Milestones

| Milestone | What | When |
|-----------|------|------|
| M0 | Docker stack running, DB schema migrated | Day 1 |
| M1 | Full extraction pipeline: arxiv URL → KnowledgeObject | Day 6 |
| M2 | Citation + method + benchmark linking working | Day 12 |
| M3 | Contradiction detection catching real conflicts | Day 12 |
| M4 | Researcher profiles with GitHub cross-linking | Day 16 |
| M5 | Frontier suggestions from research notes | Day 21 |
| M6 | Hypothesis ledger with evidence accumulation | Day 21 |
| M7 | BenchmarkDrift SOTA tracker | Day 21 |
| M8 | arxiv RSS watcher running daily | Day 24 |
| M9 | Full frontend — all 7 pages working | Day 31 |

---

## References

- arxiv API: https://info.arxiv.org/help/api/index.html
- Semantic Scholar API: https://api.semanticscholar.org/api-docs/
- pgvector: https://github.com/pgvector/pgvector
- D3 force simulation: https://d3js.org/d3-force
- pdfplumber: https://github.com/jsvine/pdfplumber
- ANN Benchmarks (for understanding embedding search): https://ann-benchmarks.com