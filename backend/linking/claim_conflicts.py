from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def sync_claim_conflicts_for_paper(paper_id: str, db: AsyncSession) -> None:
    rows = await db.execute(
        text(
            "SELECT "
            "cl.parent_claim_id, cl.child_claim_id, cl.relation, cl.confidence, "
            "pc.paper_id AS parent_paper_id, cc.paper_id AS child_paper_id, "
            "pc.text AS parent_claim_text, cc.text AS child_claim_text "
            "FROM claim_lineage cl "
            "JOIN claims pc ON pc.id = cl.parent_claim_id "
            "JOIN claims cc ON cc.id = cl.child_claim_id "
            "WHERE cl.workspace_id = current_workspace_id() "
            "AND cc.paper_id = :paper_id "
            "AND cl.relation IN ('challenges', 'refines')"
        ),
        {"paper_id": paper_id},
    )
    for row in rows.mappings().all():
        severity, reasoning = _severity_and_reasoning(row["relation"], float(row["confidence"] or 0))
        await db.execute(
            text(
                "INSERT INTO claim_conflicts "
                "(id, parent_claim_id, child_claim_id, parent_paper_id, child_paper_id, relation, severity, confidence, reasoning, created_at) "
                "VALUES (gen_random_uuid(), :parent_claim_id, :child_claim_id, :parent_paper_id, :child_paper_id, :relation, :severity, :confidence, :reasoning, NOW()) "
                "ON CONFLICT (workspace_id, parent_claim_id, child_claim_id) "
                "DO UPDATE SET relation = EXCLUDED.relation, severity = EXCLUDED.severity, confidence = EXCLUDED.confidence, reasoning = EXCLUDED.reasoning"
            ),
            {
                "parent_claim_id": str(row["parent_claim_id"]),
                "child_claim_id": str(row["child_claim_id"]),
                "parent_paper_id": row["parent_paper_id"],
                "child_paper_id": row["child_paper_id"],
                "relation": row["relation"],
                "severity": severity,
                "confidence": float(row["confidence"] or 0),
                "reasoning": reasoning,
            },
        )
    await db.commit()


def _severity_and_reasoning(relation: str, confidence: float) -> tuple[str, str]:
    if relation == "challenges":
        if confidence >= 0.92:
            return "verified", f"High-confidence challenge relation ({confidence:.2f})."
        if confidence >= 0.86:
            return "strong", f"Strong challenge relation ({confidence:.2f})."
        return "likely", f"Likely challenge relation ({confidence:.2f})."
    return "possible", f"Claim refines prior claim ({confidence:.2f}); possible scoped conflict."


async def list_claim_conflicts(
    db: AsyncSession,
    severity: str | None = None,
    relation: str | None = None,
    limit: int = 100,
) -> list[dict]:
    query = (
        "SELECT "
        "cc.id, cc.parent_claim_id, cc.child_claim_id, cc.parent_paper_id, cc.child_paper_id, "
        "cc.relation, cc.severity, cc.confidence, cc.reasoning, cc.created_at, "
        "pc.text AS parent_claim_text, ch.text AS child_claim_text, "
        "pp.title AS parent_paper_title, cp.title AS child_paper_title, "
        "(SELECT ccf.feedback FROM claim_conflict_feedback ccf "
        " WHERE ccf.workspace_id = current_workspace_id() AND ccf.conflict_id = cc.id "
        "   AND ccf.created_by = current_user_id() "
        " ORDER BY ccf.updated_at DESC LIMIT 1) AS user_feedback, "
        "(SELECT ccf.note FROM claim_conflict_feedback ccf "
        " WHERE ccf.workspace_id = current_workspace_id() AND ccf.conflict_id = cc.id "
        "   AND ccf.created_by = current_user_id() "
        " ORDER BY ccf.updated_at DESC LIMIT 1) AS user_note "
        "FROM claim_conflicts cc "
        "JOIN claims pc ON pc.workspace_id = current_workspace_id() AND pc.id = cc.parent_claim_id "
        "JOIN claims ch ON ch.workspace_id = current_workspace_id() AND ch.id = cc.child_claim_id "
        "JOIN papers pp ON pp.workspace_id = current_workspace_id() AND pp.id = cc.parent_paper_id "
        "JOIN papers cp ON cp.workspace_id = current_workspace_id() AND cp.id = cc.child_paper_id "
        "WHERE cc.workspace_id = current_workspace_id() "
    )
    params: dict[str, object] = {"limit": limit}
    if severity:
        query += "AND cc.severity = :severity "
        params["severity"] = severity
    if relation:
        query += "AND cc.relation = :relation "
        params["relation"] = relation
    query += "ORDER BY cc.created_at DESC LIMIT :limit"
    rows = await db.execute(text(query), params)
    return [dict(r) for r in rows.mappings().all()]


async def submit_claim_conflict_feedback(
    conflict_id: str,
    feedback: str,
    note: str,
    db: AsyncSession,
) -> dict:
    cleaned_feedback = feedback.strip().lower()
    if cleaned_feedback not in {"agree", "disagree"}:
        raise HTTPException(status_code=400, detail="Feedback must be 'agree' or 'disagree'")

    row = await db.execute(
        text("SELECT id FROM claim_conflicts WHERE workspace_id = current_workspace_id() AND id = :id"),
        {"id": conflict_id},
    )
    conflict = row.mappings().one_or_none()
    if conflict is None:
        raise HTTPException(status_code=404, detail="Claim conflict not found")

    await db.execute(
        text(
            "INSERT INTO claim_conflict_feedback "
            "(id, conflict_id, feedback, note, created_by, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :conflict_id, :feedback, :note, current_user_id(), NOW(), NOW()) "
            "ON CONFLICT (workspace_id, conflict_id, created_by) "
            "DO UPDATE SET feedback = EXCLUDED.feedback, note = EXCLUDED.note, updated_at = NOW()"
        ),
        {
            "conflict_id": conflict_id,
            "feedback": cleaned_feedback,
            "note": note.strip(),
        },
    )
    await db.commit()
    return {"status": "ok", "feedback": cleaned_feedback}
