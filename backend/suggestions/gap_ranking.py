import logging
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("lumen")


async def rank_research_gaps(db: AsyncSession, limit: int = 20) -> list[dict]:
    """
    Rank research topics by gap score:
      gap_score = open_problems_count + paper_growth_rate - solution_density

    Higher score = more open questions relative to claimed solutions.
    """
    # Gather all open problems and their keywords (from parent papers)
    open_problems = await db.execute(
        text(
            "SELECT op.text, p.year, p.knowledge_obj->'keywords' AS keywords "
            "FROM open_problems op "
            "JOIN papers p ON op.paper_id = p.id "
            "ORDER BY p.year DESC NULLS LAST"
        )
    )
    problem_rows = open_problems.all()

    # Gather keywords per paper to estimate topic density
    papers = await db.execute(
        text(
            "SELECT id, year, knowledge_obj->'keywords' AS keywords, "
            "knowledge_obj->'claims' AS claims "
            "FROM papers "
            "ORDER BY year DESC NULLS LAST"
        )
    )
    paper_rows = papers.all()

    # Build keyword → {paper_count, problem_count, claim_count, years} map
    topic_stats: dict[str, dict] = defaultdict(
        lambda: {"paper_count": 0, "problem_count": 0, "claim_count": 0, "years": []}
    )

    for row in paper_rows:
        kws = row.keywords or []
        if isinstance(kws, str):
            import json
            kws = json.loads(kws)
        year = row.year or 0
        claims = row.claims or []
        if isinstance(claims, str):
            import json
            claims = json.loads(claims)
        for kw in kws:
            kw = kw.lower().strip()
            if not kw:
                continue
            topic_stats[kw]["paper_count"] += 1
            topic_stats[kw]["claim_count"] += len(claims)
            if year:
                topic_stats[kw]["years"].append(year)

    for row in problem_rows:
        kws = row.keywords or []
        if isinstance(kws, str):
            import json
            kws = json.loads(kws)
        for kw in kws:
            kw = kw.lower().strip()
            if kw:
                topic_stats[kw]["problem_count"] += 1

    # Compute gap score
    results = []
    for topic, stats in topic_stats.items():
        if stats["paper_count"] < 2:
            continue

        years = sorted(stats["years"])
        if len(years) >= 2:
            # Simple growth rate: papers per year range
            span = max(years[-1] - years[0], 1)
            growth_rate = stats["paper_count"] / span
        else:
            growth_rate = 1.0

        solution_density = stats["claim_count"] / max(stats["paper_count"], 1)
        problem_density = stats["problem_count"] / max(stats["paper_count"], 1)

        gap_score = (problem_density * 3) + growth_rate - (solution_density * 0.5)

        results.append({
            "topic": topic,
            "gap_score": round(gap_score, 3),
            "paper_count": stats["paper_count"],
            "open_problem_count": stats["problem_count"],
            "claim_count": stats["claim_count"],
            "growth_rate": round(growth_rate, 2),
            "year_range": f"{years[0]}–{years[-1]}" if years else "unknown",
        })

    results.sort(key=lambda x: x["gap_score"], reverse=True)
    return results[:limit]


async def get_benchmark_contamination(db: AsyncSession) -> list[dict]:
    """Return all benchmarks with known quality issues, enriched with usage counts."""
    flagged = await db.execute(
        text(
            "SELECT bm.dataset, bm.known_issues, bm.first_year, bm.common_criticism, "
            "COUNT(b.id) AS usage_count "
            "FROM benchmark_metadata bm "
            "LEFT JOIN benchmarks b ON b.dataset = bm.dataset "
            "GROUP BY bm.dataset, bm.known_issues, bm.first_year, bm.common_criticism "
            "ORDER BY usage_count DESC"
        )
    )
    return [
        {
            "dataset": r.dataset,
            "known_issues": r.known_issues or [],
            "first_year": r.first_year,
            "common_criticism": r.common_criticism,
            "usage_count": r.usage_count,
        }
        for r in flagged.all()
    ]


async def get_paper_contamination_warnings(paper_id: str, db: AsyncSession) -> list[dict]:
    """Return contamination warnings for benchmarks used by a specific paper."""
    warnings = await db.execute(
        text(
            "SELECT b.dataset, b.metric, b.value, "
            "bm.known_issues, bm.common_criticism "
            "FROM benchmarks b "
            "JOIN benchmark_metadata bm ON b.dataset = bm.dataset "
            "WHERE b.paper_id = :pid "
            "AND jsonb_array_length(bm.known_issues) > 0"
        ),
        {"pid": paper_id},
    )
    return [
        {
            "dataset": r.dataset,
            "metric": r.metric,
            "value": r.value,
            "issues": r.known_issues or [],
            "criticism": r.common_criticism,
        }
        for r in warnings.all()
    ]
