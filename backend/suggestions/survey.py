import json
import logging

import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from knowledge.embedder import embed_text

logger = logging.getLogger("lumen")

SURVEY_PROMPT = """You are generating a structured literature survey for an ML researcher.

Topic: {topic}
Papers surveyed (titles, years, claims, methods, benchmarks):
{paper_summaries}

Open problems aggregated from these papers:
{open_problems}

Unresolved contradictions detected:
{contradictions}

Generate a structured survey with exactly these sections. Return as JSON:
{{
  "title": "<survey title>",
  "key_methods": [
    {{
      "name": "<method name>",
      "description": "<one sentence>",
      "first_paper": "<paper title that introduced it>",
      "year": <year>,
      "novelty": "foundational | incremental | applied"
    }}
  ],
  "benchmark_progression": [
    {{
      "dataset": "<dataset>",
      "metric": "<metric>",
      "trajectory": "<one sentence describing SOTA progression>"
    }}
  ],
  "unresolved_problems": ["<one problem per item>"],
  "contradictions": [
    {{
      "description": "<what the contradiction is>",
      "papers_for": ["<paper title>"],
      "papers_against": ["<paper title>"]
    }}
  ],
  "research_gaps": ["<specific gap or unexplored direction>"],
  "recommended_reading_order": ["<paper title in order>"]
}}

Return ONLY the JSON object. No preamble, no markdown fences."""


async def generate_survey(topic: str, since_year: int, db: AsyncSession) -> dict:
    # Find relevant papers via embedding similarity + keyword search
    topic_embedding = await embed_text(topic)

    similar_papers = await db.execute(
        text(
            "SELECT id, title, year, knowledge_obj "
            "FROM papers "
            "WHERE workspace_id = current_workspace_id() AND (:year = 0 OR year >= :year) "
            "ORDER BY title_embedding <=> CAST(:emb AS vector) "
            "LIMIT 20"
        ),
        {"emb": json.dumps(topic_embedding), "year": since_year},
    )
    paper_rows = similar_papers.mappings().all()

    if not paper_rows:
        return {"error": "No papers found for this topic. Ingest relevant papers first."}

    paper_ids = [str(r["id"]) for r in paper_rows]

    # Gather open problems from these papers
    if paper_ids:
        placeholders = ", ".join([f":p{i}" for i in range(len(paper_ids))])
        params = {f"p{i}": pid for i, pid in enumerate(paper_ids)}
        open_problems_rows = await db.execute(
            text(f"SELECT text FROM open_problems WHERE workspace_id = current_workspace_id() AND paper_id IN ({placeholders}) LIMIT 30"),
            params,
        )
        open_problems = [r.text for r in open_problems_rows.all()]
    else:
        open_problems = []

    # Gather contradictions among these papers
    if len(paper_ids) > 1:
        placeholders = ", ".join([f":p{i}" for i in range(len(paper_ids))])
        params = {f"p{i}": pid for i, pid in enumerate(paper_ids)}
        contradiction_rows = await db.execute(
            text(
                f"SELECT pl.metadata, ps.title AS source_title, pt.title AS target_title "
                f"FROM paper_links pl "
                f"JOIN papers ps ON pl.source_id = ps.id "
                f"JOIN papers pt ON pl.target_id = pt.id "
                f"WHERE pl.workspace_id = current_workspace_id() "
                f"AND pl.link_type = 'CONTRADICTS' "
                f"AND pl.source_id IN ({placeholders})"
            ),
            params,
        )
        contradictions = [
            {
                "source": r.source_title,
                "target": r.target_title,
                "details": r.metadata,
            }
            for r in contradiction_rows.all()
        ]
    else:
        contradictions = []

    # Build paper summaries for the prompt
    paper_summaries = []
    for r in paper_rows:
        ko = r["knowledge_obj"] or {}
        claims = [c.get("text", "") for c in ko.get("claims", [])[:3]]
        methods = [m.get("name", "") for m in ko.get("methods", [])[:5]]
        benchmarks = [f"{b.get('dataset')}/{b.get('metric')}={b.get('value')}" for b in ko.get("benchmarks", [])[:3]]
        paper_summaries.append(
            f"- {r['title']} ({r['year']})\n"
            f"  Claims: {'; '.join(claims)}\n"
            f"  Methods: {', '.join(methods)}\n"
            f"  Benchmarks: {', '.join(benchmarks)}"
        )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    prompt = SURVEY_PROMPT.format(
        topic=topic,
        paper_summaries="\n".join(paper_summaries),
        open_problems="\n".join(f"- {p}" for p in open_problems[:20]),
        contradictions="\n".join(
            f"- {c['source']} vs {c['target']}: {json.dumps(c['details'])}"
            for c in contradictions[:10]
        ) or "None detected",
    )

    msg = await client.messages.create(
        model=settings.claude_model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text

    try:
        survey = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Survey JSON parse failed, returning raw")
        survey = {"raw": raw}

    survey["topic"] = topic
    survey["since_year"] = since_year
    survey["paper_count"] = len(paper_rows)
    survey["paper_ids"] = paper_ids
    return survey
