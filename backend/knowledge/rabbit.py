import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("lumen")


async def get_rabbit_hole(paper_id: str, db: AsyncSession) -> dict | None:
    """
    Return an explorable map of the paper's intellectual neighborhood:
    ancestors, descendants, concurrent work, contradictions, and method siblings.
    """
    paper_row = await db.execute(
        text("SELECT year FROM papers WHERE workspace_id = current_workspace_id() AND id = :id"),
        {"id": paper_id},
    )
    row = paper_row.mappings().one_or_none()
    if not row:
        return None
    year = row["year"] or 0

    # Papers this paper cites or shares methods with (backward links)
    ancestors = await db.execute(
        text(
            "SELECT DISTINCT p.id, p.title, p.year, p.arxiv_url, pl.link_type "
            "FROM paper_links pl "
            "JOIN papers p ON p.id = pl.target_id "
            "WHERE pl.workspace_id = current_workspace_id() "
            "AND pl.source_id = :id AND pl.link_type IN ('CITES', 'SHARES_METHOD') "
            "ORDER BY p.year ASC NULLS LAST"
        ),
        {"id": paper_id},
    )

    # Papers that cite this paper (forward links)
    descendants = await db.execute(
        text(
            "SELECT DISTINCT p.id, p.title, p.year, p.arxiv_url "
            "FROM paper_links pl "
            "JOIN papers p ON p.id = pl.source_id "
            "WHERE pl.workspace_id = current_workspace_id() "
            "AND pl.target_id = :id AND pl.link_type = 'CITES' "
            "ORDER BY p.year ASC NULLS LAST"
        ),
        {"id": paper_id},
    )

    # Papers sharing methods published within ±1 year (concurrent work)
    concurrent = await db.execute(
        text(
            "SELECT DISTINCT p.id, p.title, p.year, p.arxiv_url, pl.metadata "
            "FROM paper_links pl "
            "JOIN papers p ON (p.id = CASE WHEN pl.source_id = :id THEN pl.target_id ELSE pl.source_id END) "
            "WHERE pl.workspace_id = current_workspace_id() "
            "AND (pl.source_id = :id OR pl.target_id = :id) "
            "AND pl.link_type = 'SHARES_METHOD' "
            "AND p.id != :id "
            "AND (p.year IS NULL OR (p.year BETWEEN :y1 AND :y2)) "
            "ORDER BY p.year ASC NULLS LAST"
        ),
        {"id": paper_id, "y1": year - 1, "y2": year + 1},
    )

    # Papers with CONTRADICTS edges
    contradictions = await db.execute(
        text(
            "SELECT DISTINCT p.id, p.title, p.year, p.arxiv_url, pl.metadata "
            "FROM paper_links pl "
            "JOIN papers p ON (p.id = CASE WHEN pl.source_id = :id THEN pl.target_id ELSE pl.source_id END) "
            "WHERE pl.workspace_id = current_workspace_id() "
            "AND (pl.source_id = :id OR pl.target_id = :id) "
            "AND pl.link_type = 'CONTRADICTS' "
            "AND p.id != :id"
        ),
        {"id": paper_id},
    )

    # Papers sharing methods regardless of era (method siblings), excluding concurrent
    method_siblings = await db.execute(
        text(
            "SELECT DISTINCT p.id, p.title, p.year, p.arxiv_url, pl.metadata "
            "FROM paper_links pl "
            "JOIN papers p ON (p.id = CASE WHEN pl.source_id = :id THEN pl.target_id ELSE pl.source_id END) "
            "WHERE pl.workspace_id = current_workspace_id() "
            "AND (pl.source_id = :id OR pl.target_id = :id) "
            "AND pl.link_type = 'SHARES_METHOD' "
            "AND p.id != :id "
            "AND (p.year IS NULL OR p.year NOT BETWEEN :y1 AND :y2) "
            "ORDER BY p.year ASC NULLS LAST"
        ),
        {"id": paper_id, "y1": year - 1, "y2": year + 1},
    )

    return {
        "paper_id": paper_id,
        "ancestors": [dict(r) for r in ancestors.mappings().all()],
        "descendants": [dict(r) for r in descendants.mappings().all()],
        "concurrent": [dict(r) for r in concurrent.mappings().all()],
        "contradictions": [dict(r) for r in contradictions.mappings().all()],
        "method_siblings": [dict(r) for r in method_siblings.mappings().all()],
    }


async def get_missing_experiments(paper_id: str, db: AsyncSession) -> dict:
    """
    Compare this paper's benchmarks against competing papers that share methods or benchmarks.
    Surface dataset+metric pairs that competitors run but this paper does not.
    """
    my_benchmarks = await db.execute(
        text(
            "SELECT DISTINCT dataset, metric FROM benchmarks "
            "WHERE workspace_id = current_workspace_id() AND paper_id = :id"
        ),
        {"id": paper_id},
    )
    my_set = {(r.dataset, r.metric) for r in my_benchmarks.all()}

    # Competing papers: those linked via SHARES_METHOD or BENCHMARKS_ON
    competing = await db.execute(
        text(
            "SELECT DISTINCT "
            "CASE WHEN pl.source_id = :id THEN pl.target_id ELSE pl.source_id END AS comp_id "
            "FROM paper_links pl "
            "WHERE pl.workspace_id = current_workspace_id() "
            "AND (pl.source_id = :id OR pl.target_id = :id) "
            "AND pl.link_type IN ('SHARES_METHOD', 'BENCHMARKS_ON')"
        ),
        {"id": paper_id},
    )
    competing_ids = [r.comp_id for r in competing.all()]

    if not competing_ids:
        return {"paper_id": paper_id, "missing_benchmarks": [], "competing_paper_count": 0}

    # Build parameterized IN clause safely
    placeholders = ", ".join([f":c{i}" for i in range(len(competing_ids))])
    params = {f"c{i}": cid for i, cid in enumerate(competing_ids)}

    comp_benchmarks = await db.execute(
        text(
            f"SELECT DISTINCT b.dataset, b.metric, p.title AS paper_title, p.id AS paper_id "
            f"FROM benchmarks b "
            f"JOIN papers p ON b.paper_id = p.id "
            f"WHERE b.workspace_id = current_workspace_id() AND b.paper_id IN ({placeholders})"
        ),
        params,
    )

    # Group by (dataset, metric) and collect which papers run them
    by_benchmark: dict[tuple, list[str]] = {}
    for r in comp_benchmarks.all():
        key = (r.dataset, r.metric)
        by_benchmark.setdefault(key, []).append(r.paper_title)

    missing = [
        {
            "dataset": dataset,
            "metric": metric,
            "run_by": titles,
        }
        for (dataset, metric), titles in sorted(by_benchmark.items())
        if (dataset, metric) not in my_set
    ]

    return {
        "paper_id": paper_id,
        "missing_benchmarks": missing,
        "competing_paper_count": len(competing_ids),
    }
