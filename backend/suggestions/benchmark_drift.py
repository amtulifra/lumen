from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_drift_series(dataset: str, metric: str, db: AsyncSession) -> list[dict]:
    rows = await db.execute(
        text(
            "SELECT bd.year, MAX(bd.value) AS sota_value, "
            "bd.model, bd.paper_id, p.title "
            "FROM benchmark_drift bd "
            "JOIN papers p ON bd.paper_id = p.id "
            "WHERE bd.workspace_id = current_workspace_id() "
            "AND bd.dataset = :dataset AND bd.metric = :metric "
            "GROUP BY bd.year, bd.model, bd.paper_id, p.title "
            "ORDER BY bd.year ASC"
        ),
        {"dataset": dataset, "metric": metric},
    )
    return [
        {
            "year": r.year,
            "sota_value": r.sota_value,
            "model": r.model,
            "paper_id": r.paper_id,
            "paper_title": r.title,
        }
        for r in rows.all()
    ]


async def list_tracked_datasets(db: AsyncSession) -> list[dict]:
    rows = await db.execute(
        text(
            "SELECT DISTINCT dataset, metric FROM benchmark_drift "
            "WHERE workspace_id = current_workspace_id() ORDER BY dataset, metric"
        )
    )
    return [{"dataset": r.dataset, "metric": r.metric} for r in rows.all()]


async def get_current_sota(dataset: str, metric: str, db: AsyncSession) -> dict | None:
    result = await db.execute(
        text(
            "SELECT bd.model, bd.value, p.title, p.id AS paper_id "
            "FROM benchmark_drift bd "
            "JOIN papers p ON bd.paper_id = p.id "
            "WHERE bd.workspace_id = current_workspace_id() "
            "AND bd.dataset = :dataset AND bd.metric = :metric "
            "ORDER BY bd.value DESC "
            "LIMIT 1"
        ),
        {"dataset": dataset, "metric": metric},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None
