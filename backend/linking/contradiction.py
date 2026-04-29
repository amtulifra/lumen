from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from knowledge.graph import knowledge_graph
from knowledge.store import create_link


async def detect_contradictions(paper_id: str, benchmarks: list[dict], db: AsyncSession) -> None:
    for bm in benchmarks:
        rows = await db.execute(
            text(
                "SELECT paper_id, value FROM benchmarks "
                "WHERE dataset = :dataset AND metric = :metric AND model = :model "
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
                knowledge_graph.add_edge(
                    paper_id, row.paper_id, "CONTRADICTS", strength=delta, metadata=meta
                )
