from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from knowledge.graph import knowledge_graph  # retained for test compatibility
from knowledge.memory import record_event
from knowledge.store import create_link


async def detect_contradictions(paper_id: str, benchmarks: list[dict], db: AsyncSession) -> None:
    for bm in benchmarks:
        current_model = bm.get("model", "") or ""
        current_split = bm.get("split", "") or ""
        current_value = float(bm.get("value", 0.0))
        rows = await db.execute(
            text(
                "SELECT paper_id, value, model, split FROM benchmarks "
                "WHERE workspace_id = current_workspace_id() AND dataset = :dataset AND metric = :metric "
                "AND paper_id != :paper_id"
            ),
            {
                "dataset": bm["dataset"],
                "metric": bm["metric"],
                "paper_id": paper_id,
            },
        )
        for row in rows.all():
            other_model = row.model or ""
            other_split = row.split or ""
            delta = abs(current_value - float(row.value))
            if delta > settings.benchmark_contradiction_delta:
                paper_a_id, paper_b_id = sorted([paper_id, row.paper_id])
                context_mismatch = (current_model != other_model) or (current_split != other_split)
                severity = _severity_for_delta(delta, context_mismatch)
                reasoning = _build_reasoning(
                    delta=delta,
                    current_model=current_model,
                    other_model=other_model,
                    current_split=current_split,
                    other_split=other_split,
                    context_mismatch=context_mismatch,
                )
                meta = {
                    "dataset": bm["dataset"],
                    "metric": bm["metric"],
                    "model": current_model,
                    "split_a": current_split,
                    "split_b": other_split,
                    "value_a": current_value,
                    "value_b": row.value,
                    "delta": current_value - float(row.value),
                    "severity": severity,
                    "context_mismatch": context_mismatch,
                    "reasoning": reasoning,
                }
                await db.execute(
                    text(
                        "INSERT INTO benchmark_conflicts "
                        "(id, paper_a_id, paper_b_id, dataset, metric, model, split_a, split_b, value_a, value_b, delta, severity, context_mismatch, reasoning) "
                        "VALUES "
                        "(gen_random_uuid(), :paper_a_id, :paper_b_id, :dataset, :metric, :model, :split_a, :split_b, :value_a, :value_b, :delta, :severity, :context_mismatch, :reasoning) "
                        "ON CONFLICT (workspace_id, paper_a_id, paper_b_id, dataset, metric, model, split_a, split_b) "
                        "DO UPDATE SET "
                        "value_a = EXCLUDED.value_a, value_b = EXCLUDED.value_b, delta = EXCLUDED.delta, "
                        "severity = EXCLUDED.severity, context_mismatch = EXCLUDED.context_mismatch, reasoning = EXCLUDED.reasoning"
                    ),
                    {
                        "paper_a_id": paper_a_id,
                        "paper_b_id": paper_b_id,
                        "dataset": bm["dataset"],
                        "metric": bm["metric"],
                        "model": current_model,
                        "split_a": current_split,
                        "split_b": other_split,
                        "value_a": current_value,
                        "value_b": float(row.value),
                        "delta": current_value - float(row.value),
                        "severity": severity,
                        "context_mismatch": context_mismatch,
                        "reasoning": reasoning,
                    },
                )
                await create_link(
                    paper_id,
                    row.paper_id,
                    "CONTRADICTS",
                    strength=delta,
                    metadata=meta,
                    db=db,
                )
                await record_event(
                    event_type="contradiction_detected",
                    subject_id=f"{paper_id}↔{row.paper_id}",
                    subject_type="contradiction",
                    content=(
                        f"Contradiction detected on {bm['dataset']} / {bm['metric']} "
                        f"({current_model}): paper {paper_id} reports {current_value}, "
                        f"paper {row.paper_id} reports {row.value} "
                        f"(delta={delta:.2f}, severity={severity})"
                    ),
                    db=db,
                )


def _severity_for_delta(delta: float, context_mismatch: bool) -> str:
    if context_mismatch:
        return "possible"
    if delta >= settings.conflict_verified_delta:
        return "verified"
    if delta >= settings.conflict_strong_delta:
        return "strong"
    if delta >= settings.conflict_likely_delta:
        return "likely"
    return "possible"


def _build_reasoning(
    delta: float,
    current_model: str,
    other_model: str,
    current_split: str,
    other_split: str,
    context_mismatch: bool,
) -> str:
    if context_mismatch:
        return (
            "Values differ, but evaluation context differs "
            f"(model {current_model or 'n/a'} vs {other_model or 'n/a'}, "
            f"split {current_split or 'n/a'} vs {other_split or 'n/a'})."
        )
    if delta >= settings.conflict_verified_delta:
        return f"Large numeric gap ({delta:.2f}) under matching context."
    if delta >= settings.conflict_strong_delta:
        return f"Strong numeric gap ({delta:.2f}) under matching context."
    if delta >= settings.conflict_likely_delta:
        return f"Likely contradiction: meaningful gap ({delta:.2f}) under matching context."
    return f"Possible contradiction: small gap ({delta:.2f})."
