from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def list_benchmark_conflicts(
    db: AsyncSession,
    severity: str | None = None,
    dataset: str | None = None,
    limit: int = 100,
) -> list[dict]:
    query = (
        "SELECT "
        "bc.id, bc.paper_a_id, bc.paper_b_id, bc.dataset, bc.metric, bc.model, "
        "bc.split_a, bc.split_b, bc.value_a, bc.value_b, bc.delta, bc.severity, "
        "bc.context_mismatch, bc.reasoning, bc.created_at, "
        "pa.title AS paper_a_title, pb.title AS paper_b_title, "
        "pa.year AS paper_a_year, pb.year AS paper_b_year, "
        "(SELECT bcf.feedback FROM benchmark_conflict_feedback bcf "
        " WHERE bcf.workspace_id = current_workspace_id() AND bcf.conflict_id = bc.id "
        "   AND bcf.created_by = current_user_id() "
        " ORDER BY bcf.updated_at DESC LIMIT 1) AS user_feedback, "
        "(SELECT bcf.note FROM benchmark_conflict_feedback bcf "
        " WHERE bcf.workspace_id = current_workspace_id() AND bcf.conflict_id = bc.id "
        "   AND bcf.created_by = current_user_id() "
        " ORDER BY bcf.updated_at DESC LIMIT 1) AS user_note "
        "FROM benchmark_conflicts bc "
        "JOIN papers pa ON pa.workspace_id = current_workspace_id() AND pa.id = bc.paper_a_id "
        "JOIN papers pb ON pb.workspace_id = current_workspace_id() AND pb.id = bc.paper_b_id "
        "WHERE bc.workspace_id = current_workspace_id() "
    )
    params: dict[str, object] = {"limit": limit}
    if severity:
        query += "AND bc.severity = :severity "
        params["severity"] = severity
    if dataset:
        query += "AND bc.dataset = :dataset "
        params["dataset"] = dataset

    query += "ORDER BY bc.created_at DESC LIMIT :limit"
    rows = await db.execute(text(query), params)
    return [dict(r) for r in rows.mappings().all()]


async def submit_conflict_feedback(
    conflict_id: str,
    feedback: str,
    note: str,
    db: AsyncSession,
) -> dict:
    cleaned_feedback = feedback.strip().lower()
    if cleaned_feedback not in {"agree", "disagree"}:
        raise HTTPException(status_code=400, detail="Feedback must be 'agree' or 'disagree'")

    row = await db.execute(
        text(
            "SELECT id FROM benchmark_conflicts "
            "WHERE workspace_id = current_workspace_id() AND id = :id"
        ),
        {"id": conflict_id},
    )
    conflict = row.mappings().one_or_none()
    if conflict is None:
        raise HTTPException(status_code=404, detail="Conflict not found")

    await db.execute(
        text(
            "INSERT INTO benchmark_conflict_feedback "
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
