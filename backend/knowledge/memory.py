import json
import logging
import uuid
from datetime import datetime, timezone

import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from knowledge.embedder import embed_text

logger = logging.getLogger("lumen")

EVENT_TYPES = {
    "hypothesis_created",
    "evidence_found",
    "belief_changed",
    "contradiction_detected",
    "paper_ingested",
}

MEMORY_QUERY_PROMPT = """You are a research memory assistant. A researcher is querying their intellectual history.

Question: {question}

Below are the most relevant events from their research timeline (newest first):

{events}

Synthesize these events into a clear, specific narrative that answers the question.
- Cite paper titles, hypothesis texts, and approximate dates
- Explain causal links: what evidence caused what belief change
- Be direct and factual; 2-4 paragraphs
- If the events don't contain enough information to fully answer the question, say so clearly

Return only the narrative — no preamble, no meta-commentary."""


async def record_event(
    event_type: str,
    subject_id: str,
    subject_type: str,
    content: str,
    db: AsyncSession,
) -> None:
    """Write a memory event. Non-fatal on failure — memory should never block core operations."""
    if event_type not in EVENT_TYPES:
        logger.warning("Unknown memory event type: %s", event_type)
        return
    try:
        embedding = await embed_text(content)
        await db.execute(
            text(
                "INSERT INTO memory_events "
                "(id, type, subject_id, subject_type, content, embedding, occurred_at) "
                "VALUES (:id, :type, :subject_id, :subject_type, :content, CAST(:emb AS vector), :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "type": event_type,
                "subject_id": subject_id,
                "subject_type": subject_type,
                "content": content,
                "emb": json.dumps(embedding),
                "now": datetime.now(timezone.utc),
            },
        )
        await db.commit()
    except Exception:
        logger.exception("Failed to record memory event (type=%s, subject=%s)", event_type, subject_id)


async def query_memory(question: str, db: AsyncSession) -> dict:
    """Embed the question, find relevant events, narrate the answer with Claude."""
    question_embedding = await embed_text(question)

    rows = await db.execute(
        text(
            "SELECT id, type, subject_id, subject_type, content, occurred_at, "
            "1 - (embedding <=> CAST(:emb AS vector)) AS relevance "
            "FROM memory_events "
            "WHERE workspace_id = current_workspace_id() AND embedding IS NOT NULL "
            "ORDER BY embedding <=> CAST(:emb AS vector) "
            "LIMIT 20"
        ),
        {"emb": json.dumps(question_embedding)},
    )
    events = [dict(r) for r in rows.mappings().all()]

    if not events:
        return {
            "answer": "No memory events recorded yet. Ingest papers and create hypotheses to build your research memory.",
            "events": [],
        }

    # Sort by time for the narrative
    events_sorted = sorted(events, key=lambda e: e["occurred_at"], reverse=True)

    event_lines = []
    for e in events_sorted[:15]:
        ts = e["occurred_at"]
        date_str = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
        event_lines.append(f"[{date_str}] {e['type'].upper()} — {e['content']}")

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    prompt = MEMORY_QUERY_PROMPT.format(
        question=question,
        events="\n".join(event_lines),
    )
    msg = await client.messages.create(
        model=settings.claude_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = msg.content[0].text.strip()

    return {
        "answer": answer,
        "events": [
            {
                "id": str(e["id"]),
                "type": e["type"],
                "subject_id": e["subject_id"],
                "subject_type": e["subject_type"],
                "content": e["content"],
                "occurred_at": str(e["occurred_at"]),
                "relevance": round(float(e["relevance"]), 3),
            }
            for e in events_sorted[:15]
        ],
    }


async def list_events(
    db: AsyncSession,
    limit: int = 50,
    event_type: str | None = None,
) -> list[dict]:
    """Return the chronological event timeline."""
    if event_type:
        rows = await db.execute(
            text(
                "SELECT id, type, subject_id, subject_type, content, occurred_at "
                "FROM memory_events "
                "WHERE workspace_id = current_workspace_id() AND type = :type "
                "ORDER BY occurred_at DESC "
                "LIMIT :limit"
            ),
            {"type": event_type, "limit": limit},
        )
    else:
        rows = await db.execute(
            text(
                "SELECT id, type, subject_id, subject_type, content, occurred_at "
                "FROM memory_events "
                "WHERE workspace_id = current_workspace_id() "
                "ORDER BY occurred_at DESC "
                "LIMIT :limit"
            ),
            {"limit": limit},
        )
    return [
        {
            "id": str(r["id"]),
            "type": r["type"],
            "subject_id": r["subject_id"],
            "subject_type": r["subject_type"],
            "content": r["content"],
            "occurred_at": str(r["occurred_at"]),
        }
        for r in rows.mappings().all()
    ]
