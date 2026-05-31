from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge.graph import knowledge_graph  # retained for test compatibility
from knowledge.store import PaperRow, create_link

FUZZY_DISTANCE_THRESHOLD = 3


async def find_paper_by_title(title: str, db: AsyncSession) -> str | None:
    # Exact match first
    result = await db.execute(select(PaperRow.id).where(PaperRow.title == title).where(text("papers.workspace_id = current_workspace_id()")))
    exact = result.scalar_one_or_none()
    if exact:
        return exact

    # Trigram similarity via pg_trgm — avoids full table scan
    rows = await db.execute(
        text(
            "SELECT id FROM papers "
            "WHERE workspace_id = current_workspace_id() AND similarity(title, :title) > 0.6 "
            "ORDER BY similarity(title, :title) DESC "
            "LIMIT 1"
        ),
        {"title": title},
    )
    row = rows.one_or_none()
    return row.id if row else None


async def link_by_citation(paper_id: str, related_titles: list[str], db: AsyncSession) -> None:
    for title in related_titles:
        target_id = await find_paper_by_title(title, db)
        if target_id and target_id != paper_id:
            await create_link(paper_id, target_id, "CITES", strength=1.0, metadata={}, db=db)
