from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from knowledge.graph import knowledge_graph  # retained for test compatibility
from knowledge.memory import record_event
from knowledge.store import create_link


async def detect_contradictions(paper_id: str, benchmarks: list[dict], db: AsyncSession) -> None:
    for bm in benchmarks:
        rows = await db.execute(
            text(
                "SELECT paper_id, value FROM benchmarks "
                "WHERE workspace_id = current_workspace_id() AND dataset = :dataset AND metric = :metric AND model = :model "
                "AND paper_id != :paper_id"
            ),
            {
                "dataset": bm["dataset"],
                "metric": bm["metric"],
                "model": bm.get("model", ""),
                "paper_id": paper_id,
            },
        )
        for row in rows.all():
            delta = abs(bm["value"] - row.value)
            if delta > settings.benchmark_contradiction_delta:
                meta = {
                    "dataset": bm["dataset"],
                    "metric": bm["metric"],
                    "model": bm.get("model", ""),
                    "value_a": bm["value"],
                    "value_b": row.value,
                    "delta": bm["value"] - row.value,
                }
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
                        f"({bm.get('model', '')}): paper {paper_id} reports {bm['value']}, "
                        f"paper {row.paper_id} reports {row.value} (delta={delta:.2f})"
                    ),
                    db=db,
                )
