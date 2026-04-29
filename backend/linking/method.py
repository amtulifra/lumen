import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from knowledge.graph import knowledge_graph
from knowledge.store import create_link


async def link_by_method(
    paper_id: str,
    methods: list[dict],
    method_embeddings: list[list[float]],
    db: AsyncSession,
) -> None:
    for method, embedding in zip(methods, method_embeddings):
        rows = await db.execute(
            text(
                "SELECT paper_id, name, 1 - (embedding <=> CAST(:emb AS vector)) AS similarity "
                "FROM methods "
                "WHERE paper_id != :paper_id "
                "AND 1 - (embedding <=> CAST(:emb AS vector)) > :threshold "
                "ORDER BY embedding <=> CAST(:emb AS vector) "
                "LIMIT 5"
            ),
            {
                "emb": json.dumps(embedding),
                "paper_id": paper_id,
                "threshold": settings.method_similarity_threshold,
            },
        )
        for row in rows.all():
            meta = {"method_a": method["name"], "method_b": row.name}
            await create_link(
                paper_id,
                row.paper_id,
                "SHARES_METHOD",
                strength=row.similarity,
                metadata=meta,
                db=db,
            )
            knowledge_graph.add_edge(
                paper_id, row.paper_id, "SHARES_METHOD", strength=row.similarity, metadata=meta
            )
