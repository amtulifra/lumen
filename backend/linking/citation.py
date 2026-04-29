from Levenshtein import distance as levenshtein_distance
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge.graph import knowledge_graph
from knowledge.store import PaperRow, create_link

FUZZY_DISTANCE_THRESHOLD = 3


async def find_paper_by_title(title: str, db: AsyncSession) -> str | None:
    result = await db.execute(select(PaperRow.id).where(PaperRow.title == title))
    exact = result.scalar_one_or_none()
    if exact:
        return exact

    rows = await db.execute(select(PaperRow.id, PaperRow.title))
    for row in rows.all():
        if levenshtein_distance(title.lower(), row.title.lower()) <= FUZZY_DISTANCE_THRESHOLD:
            return row.id

    return None


async def link_by_citation(paper_id: str, related_titles: list[str], db: AsyncSession) -> None:
    for title in related_titles:
        target_id = await find_paper_by_title(title, db)
        if target_id and target_id != paper_id:
            await create_link(paper_id, target_id, "CITES", strength=1.0, metadata={}, db=db)
            knowledge_graph.add_edge(paper_id, target_id, "CITES", strength=1.0, metadata={})
