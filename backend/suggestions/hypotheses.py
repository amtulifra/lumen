import json
import uuid
from datetime import datetime, timezone

import anthropic
from fastapi import HTTPException
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
        text(
            "SELECT id, text, status, created_at, updated_at "
            "FROM hypotheses "
            "WHERE workspace_id = current_workspace_id() "
            "ORDER BY created_at DESC"
        )
    )
    return await hydrate_hypotheses_with_evidence([dict(row) for row in result.mappings().all()], db)


async def get_hypothesis(hypothesis_id: str, db: AsyncSession) -> dict | None:
    result = await db.execute(
        text(
            "SELECT id, text, status, created_at, updated_at "
            "FROM hypotheses WHERE workspace_id = current_workspace_id() AND id = :id"
        ),
        {"id": hypothesis_id},
    )
    row = result.mappings().one_or_none()
    if not row:
        return None
    hydrated = await hydrate_hypotheses_with_evidence([dict(row)], db)
    return hydrated[0] if hydrated else None


async def judge_evidence(hypothesis_text: str, claim_text: str, paper_title: str) -> dict:
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    prompt = (
        f"Hypothesis: {hypothesis_text}\n\n"
        f"Paper: {paper_title}\n"
        f"Relevant finding: {claim_text}\n\n"
        "Decide if this finding supports, refutes, or gives mixed evidence for the hypothesis.\n"
        "Return strict JSON only in this format:\n"
        '{"verdict":"supports|refutes|mixed","reasoning":"short rationale grounded in the finding"}'
    )
    message = await client.messages.create(
        model=settings.claude_model,
        max_tokens=160,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    verdict = "mixed"
    reasoning = "Model output could not be parsed; defaulted to mixed."
    try:
        parsed = json.loads(raw)
        verdict = str(parsed.get("verdict", "")).strip().lower()
        reasoning = str(parsed.get("reasoning", "")).strip() or reasoning
    except json.JSONDecodeError:
        verdict = raw.lower().strip()
    if verdict not in ("supports", "refutes", "mixed"):
        verdict = "mixed"
    return {"verdict": verdict, "reasoning": reasoning}


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
            judgment = await judge_evidence(row.text, claim_text, paper_title)
            verdict = judgment["verdict"]
            reasoning = judgment["reasoning"]
            now = datetime.now(timezone.utc)

            await db.execute(
                text(
                    "INSERT INTO hypothesis_evidence "
                    "(id, hypothesis_id, paper_id, claim_text, verdict, strength, cited_span, section, page_number, reasoning, created_at) "
                    "VALUES "
                    "(:id, :hypothesis_id, :paper_id, :claim_text, :verdict, :strength, :cited_span, :section, :page_number, :reasoning, :created_at)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "hypothesis_id": row.id,
                    "paper_id": paper_id,
                    "claim_text": claim_text,
                    "verdict": verdict,
                    "strength": row.similarity,
                    "cited_span": claim.get("evidence_span", claim.get("evidence", "")),
                    "section": claim.get("section", ""),
                    "page_number": claim.get("page_number"),
                    "reasoning": reasoning,
                    "created_at": now,
                },
            )
            new_status = await recompute_hypothesis_status(str(row.id), db)
            await db.execute(
                text(
                    "UPDATE hypotheses "
                    "SET status = :status, updated_at = :updated_at "
                    "WHERE workspace_id = current_workspace_id() AND id = :id"
                ),
                {
                    "status": new_status,
                    "updated_at": now,
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
                event_type="evidence_matched",
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
                    event_type="hypothesis_status_updated",
                    subject_id=str(row.id),
                    subject_type="hypothesis",
                    content=(
                        f'Hypothesis status changed from "{row.status}" to "{new_status}": '
                        f'"{short_hyp}"'
                    ),
                    db=db,
                )

    await db.commit()


async def recompute_hypothesis_status(hypothesis_id: str, db: AsyncSession) -> str:
    counts = await db.execute(
        text(
            "SELECT "
            "SUM(CASE WHEN verdict IN ('supports', 'mixed') THEN 1 ELSE 0 END) AS support_count, "
            "SUM(CASE WHEN verdict IN ('refutes', 'mixed') THEN 1 ELSE 0 END) AS refute_count "
            "FROM hypothesis_evidence "
            "WHERE workspace_id = current_workspace_id() AND hypothesis_id = :id"
        ),
        {"id": hypothesis_id},
    )
    row = counts.mappings().one()
    support_count = int(row["support_count"] or 0)
    refute_count = int(row["refute_count"] or 0)
    if support_count == 0 and refute_count == 0:
        return "open"
    if support_count > 0 and refute_count == 0:
        return "supported"
    if refute_count > 0 and support_count == 0:
        return "refuted"
    return "mixed"


async def hydrate_hypotheses_with_evidence(hypotheses: list[dict], db: AsyncSession) -> list[dict]:
    if not hypotheses:
        return []

    enriched: list[dict] = []
    for h in hypotheses:
        rows = await db.execute(
            text(
                "SELECT "
                "he.id, he.paper_id, he.claim_text, he.verdict, he.strength, "
                "he.cited_span, he.section, he.page_number, he.reasoning, he.created_at, "
                "(SELECT hef.feedback FROM hypothesis_evidence_feedback hef "
                " WHERE hef.workspace_id = current_workspace_id() AND hef.evidence_id = he.id "
                "   AND hef.created_by = current_user_id() "
                " ORDER BY hef.updated_at DESC LIMIT 1) AS user_feedback, "
                "(SELECT hef.note FROM hypothesis_evidence_feedback hef "
                " WHERE hef.workspace_id = current_workspace_id() AND hef.evidence_id = he.id "
                "   AND hef.created_by = current_user_id() "
                " ORDER BY hef.updated_at DESC LIMIT 1) AS user_note "
                "FROM hypothesis_evidence he "
                "WHERE he.workspace_id = current_workspace_id() AND he.hypothesis_id = :hypothesis_id "
                "ORDER BY he.created_at DESC"
            ),
            {"hypothesis_id": h["id"]},
        )
        bucket = {"evidence_for": [], "evidence_against": []}
        for r in rows.mappings().all():
            item = {
                "id": str(r["id"]),
                "paper_id": r["paper_id"],
                "claim_text": r["claim_text"],
                "strength": float(r["strength"] or 0.0),
                "cited_span": r["cited_span"] or "",
                "section": r["section"] or "",
                "page_number": r["page_number"],
                "reasoning": r["reasoning"] or "",
                "verdict": r["verdict"],
                "created_at": str(r["created_at"]),
                "user_feedback": r["user_feedback"],
                "user_note": r["user_note"] or "",
            }
            if r["verdict"] in ("supports", "mixed"):
                bucket["evidence_for"].append(item)
            if r["verdict"] in ("refutes", "mixed"):
                bucket["evidence_against"].append(item)
        enriched.append({**h, **bucket})
    return enriched


async def submit_evidence_feedback(
    evidence_id: str,
    feedback: str,
    note: str,
    db: AsyncSession,
) -> dict:
    cleaned_feedback = feedback.strip().lower()
    if cleaned_feedback not in {"agree", "disagree"}:
        raise HTTPException(status_code=400, detail="Feedback must be 'agree' or 'disagree'")

    evidence_result = await db.execute(
        text(
            "SELECT id, hypothesis_id, claim_text FROM hypothesis_evidence "
            "WHERE workspace_id = current_workspace_id() AND id = :id"
        ),
        {"id": evidence_id},
    )
    evidence = evidence_result.mappings().one_or_none()
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence item not found")

    feedback_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await db.execute(
        text(
            "INSERT INTO hypothesis_evidence_feedback "
            "(id, evidence_id, feedback, note, created_by, created_at, updated_at) "
            "VALUES (:id, :evidence_id, :feedback, :note, current_user_id(), :created_at, :updated_at) "
            "ON CONFLICT (workspace_id, evidence_id, created_by) "
            "DO UPDATE SET feedback = EXCLUDED.feedback, note = EXCLUDED.note, updated_at = EXCLUDED.updated_at"
        ),
        {
            "id": feedback_id,
            "evidence_id": evidence_id,
            "feedback": cleaned_feedback,
            "note": note.strip(),
            "created_at": now,
            "updated_at": now,
        },
    )
    await db.commit()

    await record_event(
        event_type="evidence_feedback_given",
        subject_id=str(evidence["hypothesis_id"]),
        subject_type="hypothesis",
        content=f'Feedback {cleaned_feedback} on evidence: "{str(evidence["claim_text"])[:120]}"',
        db=db,
    )

    return {"status": "ok", "feedback": cleaned_feedback}


async def log_paper_open_from_evidence(evidence_id: str, db: AsyncSession) -> dict:
    row = await db.execute(
        text(
            "SELECT id, hypothesis_id, paper_id, claim_text "
            "FROM hypothesis_evidence "
            "WHERE workspace_id = current_workspace_id() AND id = :id"
        ),
        {"id": evidence_id},
    )
    evidence = row.mappings().one_or_none()
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence item not found")

    await record_event(
        event_type="paper_opened_from_evidence",
        subject_id=str(evidence["hypothesis_id"]),
        subject_type="hypothesis",
        content=(
            f'Paper opened from evidence (paper_id={evidence["paper_id"]}) '
            f'for claim "{str(evidence["claim_text"])[:120]}"'
        ),
        db=db,
    )
    return {"paper_id": evidence["paper_id"]}
