from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge.graph import knowledge_graph
from knowledge.store import create_link


async def link_by_benchmark(paper_id: str, benchmarks: list[dict], db: AsyncSession) -> None:
    for bm in benchmarks:
        rows = await db.execute(
            text(
                "SELECT paper_id FROM benchmarks "
                "WHERE dataset = :dataset AND metric = :metric AND paper_id != :paper_id"
            ),
            {"dataset": bm["dataset"], "metric": bm["metric"], "paper_id": paper_id},
        )
        for row in rows.all():
            meta = {"dataset": bm["dataset"], "metric": bm["metric"]}
            await create_link(
                paper_id,
                row.paper_id,
                "BENCHMARKS_ON",
                strength=1.0,
                metadata=meta,
                db=db,
            )
            knowledge_graph.add_edge(
                paper_id, row.paper_id, "BENCHMARKS_ON", strength=1.0, metadata=meta
            )
