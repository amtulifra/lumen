import json
import uuid
from datetime import datetime, timezone

import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from knowledge.embedder import embed_text
from knowledge.memory import record_event
from notifications import create_notification


async def create_hypothesis(hypothesis_text: str, db: AsyncSession) -> str:
    hypothesis_id = str(uuid.uuid4())
    embedding = await embed_text(hypothesis_text)
    now = datetime.now(timezone.utc)

    await db.execute(
        text(
            "INSERT INTO hypotheses (id, text, embedding, status, evidence_for, evidence_against, created_at, updated_at) "
            "VALUES (:id, :text, CAST(:embedding AS vector), 'open', '[]', '[]', :now, :now)"
        ),
        {
            "id": hypothesis_id,
            "text": hypothesis_text,
            "embedding": json.dumps(embedding),
            "now": now,
        },
    )
    await db.commit()

    await record_event(
        event_type="hypothesis_created",
        subject_id=hypothesis_id,
        subject_type="hypothesis",
        content=f"New hypothesis created: {hypothesis_text}",
        db=db,
    )
    return hypothesis_id


async def list_hypotheses(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        text("SELECT id, text, status, evidence_for, evidence_against, created_at, updated_at FROM hypotheses WHERE workspace_id = current_workspace_id() ORDER BY created_at DESC")
    )
    return [dict(row) for row in result.mappings().all()]


async def get_hypothesis(hypothesis_id: str, db: AsyncSession) -> dict | None:
    result = await db.execute(
        text(
            "SELECT id, text, status, evidence_for, evidence_against, created_at, updated_at "
            "FROM hypotheses WHERE workspace_id = current_workspace_id() AND id = :id"
        ),
        {"id": hypothesis_id},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def judge_evidence(hypothesis_text: str, claim_text: str, paper_title: str) -> str:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    prompt = (
        f"Hypothesis: {hypothesis_text}\n\n"
        f"Paper: {paper_title}\n"
        f"Relevant finding: {claim_text}\n\n"
        "Does this finding support, refute, or give mixed evidence for the hypothesis? "
        "Answer with exactly one word: supports, refutes, or mixed."
    )
    message = await client.messages.create(
        model=settings.claude_model,
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    verdict = message.content[0].text.strip().lower()
    if verdict not in ("supports", "refutes", "mixed"):
        return "mixed"
    return verdict


async def check_hypotheses_for_paper(paper_id: str, extracted: dict, db: AsyncSession) -> None:
    paper_result = await db.execute(
        text("SELECT title FROM papers WHERE workspace_id = current_workspace_id() AND id = :id"),
        {"id": paper_id},
    )
    paper_row = paper_result.mappings().one_or_none()
    paper_title = paper_row["title"] if paper_row else paper_id

    claims = extracted.get("claims", [])
    for claim in claims:
        claim_text = claim.get("text", "")
        if not claim_text:
            continue

        claim_embedding = await embed_text(claim_text)

        rows = await db.execute(
            text(
                "SELECT id, text, status, evidence_for, evidence_against, "
                "1 - (embedding <=> CAST(:emb AS vector)) AS similarity "
                "FROM hypotheses "
                "WHERE workspace_id = current_workspace_id() "
                "AND 1 - (embedding <=> CAST(:emb AS vector)) > :threshold"
            ),
            {
                "emb": json.dumps(claim_embedding),
                "threshold": settings.hypothesis_similarity_threshold,
            },
        )

        for row in rows.all():
            verdict = await judge_evidence(row.text, claim_text, paper_title)
            evidence_entry = {
                "paper_id": paper_id,
                "claim_text": claim_text,
                "strength": row.similarity,
            }

            evidence_for = row.evidence_for or []
            evidence_against = row.evidence_against or []

            if verdict == "supports":
                evidence_for.append(evidence_entry)
            elif verdict == "refutes":
                evidence_against.append(evidence_entry)
            else:
                evidence_for.append(evidence_entry)
                evidence_against.append(evidence_entry)

            new_status = compute_status(evidence_for, evidence_against)

            await db.execute(
                text(
                    "UPDATE hypotheses SET evidence_for=:ef, evidence_against=:ea, "
                    "status=:status, updated_at=:now WHERE workspace_id = current_workspace_id() AND id=:id"
                ),
                {
                    "ef": json.dumps(evidence_for),
                    "ea": json.dumps(evidence_against),
                    "status": new_status,
                    "now": datetime.now(timezone.utc),
                    "id": row.id,
                },
            )

            label = "supports" if verdict == "supports" else "contradicts" if verdict == "refutes" else "relates to"
            short_hyp = row.text[:80] + ("…" if len(row.text) > 80 else "")
            await create_notification(
                type="hypothesis_evidence",
                message=f'New paper {label} your hypothesis: "{short_hyp}"',
                payload={"hypothesis_id": row.id, "paper_id": paper_id, "verdict": verdict},
                db=db,
            )

            await record_event(
                event_type="evidence_found",
                subject_id=str(row.id),
                subject_type="hypothesis",
                content=(
                    f'Paper (id={paper_id}) {label} hypothesis: "{short_hyp}" '
                    f'— claim: "{claim_text[:120]}"'
                ),
                db=db,
            )

            if new_status != row.status:
                await record_event(
                    event_type="belief_changed",
                    subject_id=str(row.id),
                    subject_type="hypothesis",
                    content=(
                        f'Hypothesis status changed from "{row.status}" to "{new_status}": '
                        f'"{short_hyp}"'
                    ),
                    db=db,
                )

    await db.commit()


def compute_status(evidence_for: list, evidence_against: list) -> str:
    if not evidence_for and not evidence_against:
        return "open"
    if evidence_for and not evidence_against:
        return "supported"
    if evidence_against and not evidence_for:
        return "refuted"
    return "mixed"
