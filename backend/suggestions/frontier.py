import json

import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from knowledge.embedder import embed_text

SUGGESTION_PROMPT = """\
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

Return as a JSON array of objects with keys: direction, rationale, papers, difficulty."""


async def fetch_relevant_papers(embedding: list[float], db: AsyncSession) -> list[dict]:
    rows = await db.execute(
        text(
            "SELECT id, title, knowledge_obj "
            "FROM papers "
            "WHERE workspace_id = current_workspace_id() "
            "ORDER BY title_embedding <=> CAST(:emb AS vector) "
            "LIMIT 10"
        ),
        {"emb": json.dumps(embedding)},
    )
    return [{"id": r.id, "title": r.title, "knowledge_obj": r.knowledge_obj} for r in rows.all()]


async def fetch_relevant_open_problems(embedding: list[float], db: AsyncSession) -> list[str]:
    rows = await db.execute(
        text(
            "SELECT text FROM open_problems "
            "WHERE workspace_id = current_workspace_id() "
            "ORDER BY embedding <=> CAST(:emb AS vector) "
            "LIMIT 10"
        ),
        {"emb": json.dumps(embedding)},
    )
    return [r.text for r in rows.all()]


async def fetch_method_gaps(
    relevant_paper_ids: list[str], embedding: list[float], db: AsyncSession
) -> list[str]:
    if not relevant_paper_ids:
        return []

    rows = await db.execute(
        text(
            "SELECT name, description FROM methods "
            "WHERE workspace_id = current_workspace_id() "
            "AND paper_id != ALL(:ids) "
            "ORDER BY embedding <=> CAST(:emb AS vector) "
            "LIMIT 10"
        ),
        {"ids": relevant_paper_ids, "emb": json.dumps(embedding)},
    )
    return [f"{r.name}: {r.description}" for r in rows.all()]


async def generate_suggestions(user_notes: str, db: AsyncSession) -> dict:
    notes_embedding = await embed_text(user_notes)

    relevant_papers = await fetch_relevant_papers(notes_embedding, db)
    open_problems = await fetch_relevant_open_problems(notes_embedding, db)
    paper_ids = [p["id"] for p in relevant_papers]
    method_gaps = await fetch_method_gaps(paper_ids, notes_embedding, db)

    papers_block = "\n".join(f"- {p['title']}" for p in relevant_papers)
    problems_block = "\n".join(f"- {p}" for p in open_problems)
    gaps_block = "\n".join(f"- {m}" for m in method_gaps)

    prompt = SUGGESTION_PROMPT.format(
        user_notes=user_notes,
        relevant_papers=papers_block or "None yet.",
        open_problems=problems_block or "None yet.",
        method_gaps=gaps_block or "None yet.",
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model=settings.claude_model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    try:
        suggestions = json.loads(raw)
    except json.JSONDecodeError:
        suggestions = []

    return {"suggestions": suggestions, "relevant_papers": relevant_papers}
