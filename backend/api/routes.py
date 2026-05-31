import logging
import inspect

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin, require_editor, require_viewer
from api.models import (
    GraphSubgraphOut,
    HypothesisCreateRequest,
    HypothesisOut,
    IngestAbstractRequest,
    IngestResponse,
    IngestURLRequest,
    RSSStatusOut,
    RSSSubscriptionRequest,
    SuggestRequest,
)
from database import SessionLocal, get_db, set_db_request_context
from ingestion.arxiv import fetch_paper
from ingestion.extractor import extract_knowledge
from ingestion.pdf import extract_paper_text
from ingestion.rss import (
    add_subscription,
    get_rss_status,
    get_subscriptions,
    remove_subscription,
    watch_feeds,
)
from knowledge.embedder import embed_knowledge_object
from knowledge.graph import knowledge_graph
from knowledge.store import (
    create_link,
    delete_paper,
    get_paper,
    get_paper_links,
    list_papers,
    paper_exists,
    save_paper,
    search_papers,
)
from linking.benchmark import link_by_benchmark
from linking.citation import link_by_citation
from linking.contradiction import detect_contradictions
from linking.method import link_by_method
from notifications import list_notifications, mark_all_read, mark_read
from researchers.profiles import (
    build_author_profile,
    get_paper_researchers,
    get_profile,
    refresh_profile,
)
from knowledge.claim_intelligence import (
    build_claim_lineage,
    get_claim_lineage,
    get_claim_score,
    get_paper_claim_scores,
)
from knowledge.memory import list_events, query_memory, record_event
from knowledge.rabbit import get_missing_experiments, get_rabbit_hole
from suggestions.benchmark_drift import get_drift_series, list_tracked_datasets
from suggestions.frontier import generate_suggestions
from suggestions.gap_ranking import (
    get_benchmark_contamination,
    get_paper_contamination_warnings,
    rank_research_gaps,
)
from suggestions.hypotheses import (
    check_hypotheses_for_paper,
    create_hypothesis,
    get_hypothesis,
    list_hypotheses,
)
from suggestions.survey import generate_survey

logger = logging.getLogger("lumen")

router = APIRouter(dependencies=[Depends(require_viewer)])


async def _build_author_profiles(
    authors: list[str], paper_title: str, paper_abstract: str, paper_id: str, workspace_id: str
) -> None:
    async with SessionLocal() as db:
        await set_db_request_context(
            db,
            workspace_id=workspace_id,
            user_id="00000000-0000-0000-0000-000000000002",
            role="owner",
        )
        for author in authors:
            try:
                await build_author_profile(author, paper_title, paper_abstract, paper_id, db)
            except Exception:
                logger.exception("Failed to build profile for author '%s' (paper %s)", author, paper_id)


async def run_full_ingestion(
    paper_meta: dict, db: AsyncSession, background_tasks: BackgroundTasks
) -> dict:
    paper_id = paper_meta["id"]

    if await paper_exists(paper_id, db):
        existing = await get_paper(paper_id, db)
        return {"paper_id": paper_id, "knowledge_object": existing["knowledge_obj"], "from_cache": True}

    paper_text = await extract_paper_text(paper_meta["pdf_url"]) if paper_meta.get("pdf_url") else ""
    extracted = await extract_knowledge(paper_text or paper_meta.get("abstract", ""))
    embeddings = await embed_knowledge_object(extracted, paper_meta["title"])

    await save_paper(paper_meta, extracted, embeddings, paper_text, db)

    await link_by_citation(paper_id, extracted.get("related_work", []), db)
    await link_by_method(paper_id, extracted.get("methods", []), embeddings["methods"], db)
    await link_by_benchmark(paper_id, extracted.get("benchmarks", []), db)
    await detect_contradictions(paper_id, extracted.get("benchmarks", []), db)
    await check_hypotheses_for_paper(paper_id, extracted, db)
    await build_claim_lineage(paper_id, db)

    await record_event(
        event_type="paper_ingested",
        subject_id=paper_id,
        subject_type="paper",
        content=(
            f'Ingested paper "{paper_meta["title"]}" ({paper_meta.get("year", "")}) '
            f'— {len(extracted.get("claims", []))} claims, '
            f'{len(extracted.get("methods", []))} methods, '
            f'{len(extracted.get("benchmarks", []))} benchmarks'
        ),
        db=db,
    )

    workspace_id = "00000000-0000-0000-0000-000000000001"
    try:
        workspace_row = await db.execute(text("SELECT current_workspace_id() AS workspace_id"))
        workspace_map = workspace_row.mappings()
        if inspect.isawaitable(workspace_map):
            workspace_map = await workspace_map
        row_value = workspace_map.one()
        if inspect.isawaitable(row_value):
            row_value = await row_value
        workspace_id = str(row_value["workspace_id"] or workspace_id)
    except Exception:
        # Tests often use lightweight async mocks that do not implement mapping APIs.
        pass
    background_tasks.add_task(
        _build_author_profiles,
        paper_meta.get("authors", []),
        paper_meta["title"],
        paper_meta.get("abstract", ""),
        paper_id,
        workspace_id,
    )

    return {"paper_id": paper_id, "knowledge_object": extracted, "from_cache": False}


@router.post("/ingest", response_model=IngestResponse, dependencies=[Depends(require_editor)])
async def ingest_url(
    request: IngestURLRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    try:
        paper_meta = fetch_paper(request.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch paper: {exc}") from exc

    result = await run_full_ingestion(paper_meta, db, background_tasks)
    return IngestResponse(
        paper_id=result["paper_id"],
        knowledge_object=result["knowledge_object"],
        from_cache=result["from_cache"],
    )


@router.post("/ingest/abstract", response_model=IngestResponse, dependencies=[Depends(require_editor)])
async def ingest_abstract(
    request: IngestAbstractRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    import hashlib

    paper_id = hashlib.sha256(request.title.encode()).hexdigest()[:16]

    if await paper_exists(paper_id, db):
        existing = await get_paper(paper_id, db)
        return IngestResponse(
            paper_id=paper_id,
            knowledge_object=existing["knowledge_obj"],
            from_cache=True,
        )

    paper_meta = {
        "id": paper_id,
        "title": request.title,
        "authors": [],
        "year": 0,
        "abstract": request.abstract,
        "pdf_url": "",
        "arxiv_url": "",
    }
    extracted = await extract_knowledge(request.abstract)
    embeddings = await embed_knowledge_object(extracted, request.title)
    await save_paper(paper_meta, extracted, embeddings, request.abstract, db)

    await link_by_citation(paper_id, extracted.get("related_work", []), db)
    await link_by_method(paper_id, extracted.get("methods", []), embeddings["methods"], db)
    await link_by_benchmark(paper_id, extracted.get("benchmarks", []), db)
    await detect_contradictions(paper_id, extracted.get("benchmarks", []), db)
    await check_hypotheses_for_paper(paper_id, extracted, db)
    await build_claim_lineage(paper_id, db)

    await record_event(
        event_type="paper_ingested",
        subject_id=paper_id,
        subject_type="paper",
        content=(
            f'Ingested abstract "{request.title}" '
            f'— {len(extracted.get("claims", []))} claims, '
            f'{len(extracted.get("methods", []))} methods'
        ),
        db=db,
    )

    return IngestResponse(paper_id=paper_id, knowledge_object=extracted, from_cache=False)


@router.get("/papers")
async def list_all_papers(
    db: AsyncSession = Depends(get_db),
    q: str = Query(default=""),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
):
    if q.strip():
        return await search_papers(q.strip(), db, limit=limit)
    return await list_papers(db, limit=limit, offset=offset)


@router.get("/papers/{paper_id}")
async def get_paper_detail(paper_id: str, db: AsyncSession = Depends(get_db)):
    paper = await get_paper(paper_id, db)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.delete("/papers/{paper_id}", dependencies=[Depends(require_admin)])
async def delete_paper_route(paper_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await delete_paper(paper_id, db)
    if not deleted:
        raise HTTPException(status_code=404, detail="Paper not found")
    logger.info("Deleted paper %s", paper_id)
    return {"status": "deleted", "paper_id": paper_id}


@router.get("/papers/{paper_id}/links")
async def get_links(paper_id: str, db: AsyncSession = Depends(get_db)):
    return await get_paper_links(paper_id, db)


@router.get("/papers/{paper_id}/neighbors")
async def get_neighbors(paper_id: str, link_type: str = Query(default=""), db: AsyncSession = Depends(get_db)):
    neighbors = await knowledge_graph.neighbors_db(paper_id, db, link_type=link_type or None)
    return {"paper_id": paper_id, "neighbors": neighbors}


@router.get("/papers/{paper_id}/researchers")
async def get_researchers_for_paper(paper_id: str, db: AsyncSession = Depends(get_db)):
    return await get_paper_researchers(paper_id, db)


@router.get("/graph/subgraph/{paper_id}", response_model=GraphSubgraphOut)
async def get_subgraph(paper_id: str, depth: int = 2, db: AsyncSession = Depends(get_db)):
    if depth < 1 or depth > 5:
        raise HTTPException(status_code=400, detail="depth must be between 1 and 5")
    subgraph = await knowledge_graph.subgraph_db(paper_id, depth=depth, db=db)
    return GraphSubgraphOut(nodes=subgraph["nodes"], edges=subgraph["edges"])


@router.get("/graph/contradictions")
async def get_contradictions(db: AsyncSession = Depends(get_db)):
    return await knowledge_graph.get_contradictions_db(db)


@router.get("/graph/full")
async def get_full_graph(db: AsyncSession = Depends(get_db)):
    papers = await list_papers(db, limit=500)
    from knowledge.store import get_all_links
    links = await get_all_links(db)
    normalized_links = [
        {
            "source": link["source_id"],
            "target": link["target_id"],
            "link_type": link["link_type"],
            "strength": link.get("strength"),
            "metadata": link.get("metadata"),
        }
        for link in links
    ]
    return {"nodes": papers, "edges": normalized_links}


@router.get("/researchers/{researcher_id}")
async def get_researcher(researcher_id: str, db: AsyncSession = Depends(get_db)):
    profile = await get_profile(researcher_id, db)
    if not profile:
        raise HTTPException(status_code=404, detail="Researcher not found")
    return profile


@router.post("/researchers/{researcher_id}/refresh", dependencies=[Depends(require_editor)])
async def refresh_researcher(researcher_id: str, db: AsyncSession = Depends(get_db)):
    await refresh_profile(researcher_id, db)
    return {"status": "refreshed"}


@router.post("/suggestions")
async def get_suggestions(request: SuggestRequest, db: AsyncSession = Depends(get_db)):
    return await generate_suggestions(request.notes, db)


@router.post("/hypotheses", dependencies=[Depends(require_editor)])
async def add_hypothesis(request: HypothesisCreateRequest, db: AsyncSession = Depends(get_db)):
    hypothesis_id = await create_hypothesis(request.text, db)
    return {"id": hypothesis_id}


@router.get("/hypotheses")
async def get_hypotheses(db: AsyncSession = Depends(get_db)):
    return await list_hypotheses(db)


@router.get("/hypotheses/{hypothesis_id}")
async def get_hypothesis_detail(hypothesis_id: str, db: AsyncSession = Depends(get_db)):
    hypothesis = await get_hypothesis(hypothesis_id, db)
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found")
    return hypothesis


@router.get("/benchmarks/drift")
async def benchmark_drift(dataset: str, metric: str, db: AsyncSession = Depends(get_db)):
    return await get_drift_series(dataset, metric, db)


@router.get("/benchmarks/datasets")
async def tracked_datasets(db: AsyncSession = Depends(get_db)):
    return await list_tracked_datasets(db)


@router.get("/rss/status", response_model=RSSStatusOut)
async def rss_status():
    status = get_rss_status()
    return RSSStatusOut(feeds=status["feeds"], schedule=status["schedule"])


@router.get("/rss/subscriptions")
async def list_rss_subscriptions():
    return [{"category": k, "url": v} for k, v in get_subscriptions().items()]


@router.post("/rss/subscriptions", dependencies=[Depends(require_admin)])
async def add_rss_subscription(request: RSSSubscriptionRequest):
    add_subscription(request.category, request.url)
    return {"status": "added", "category": request.category}


@router.delete("/rss/subscriptions/{category}", dependencies=[Depends(require_admin)])
async def remove_rss_subscription(category: str):
    removed = remove_subscription(category)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Subscription '{category}' not found")
    return {"status": "removed", "category": category}


@router.post("/rss/run", dependencies=[Depends(require_admin)])
async def trigger_rss_run(db: AsyncSession = Depends(get_db)):
    await watch_feeds()
    return {"status": "completed"}


@router.get("/notifications")
async def get_notifications(
    unread_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    return await list_notifications(db, unread_only=unread_only)


@router.post("/notifications/{notification_id}/read")
async def read_notification(notification_id: str, db: AsyncSession = Depends(get_db)):
    found = await mark_read(notification_id, db)
    if not found:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "read"}


@router.post("/notifications/read-all")
async def read_all_notifications(db: AsyncSession = Depends(get_db)):
    await mark_all_read(db)
    return {"status": "all read"}


# ── Phase 8: Claim Intelligence ──────────────────────────────────────────────

@router.get("/claims/{claim_id}/lineage")
async def claim_lineage(claim_id: str, db: AsyncSession = Depends(get_db)):
    return await get_claim_lineage(claim_id, db)


@router.get("/claims/{claim_id}/score")
async def claim_score(claim_id: str, db: AsyncSession = Depends(get_db)):
    return await get_claim_score(claim_id, db)


@router.get("/papers/{paper_id}/claim-scores")
async def paper_claim_scores(paper_id: str, db: AsyncSession = Depends(get_db)):
    return await get_paper_claim_scores(paper_id, db)


# ── Phase 9: Research Rabbit Mode + Missing Experiments ──────────────────────

@router.get("/papers/{paper_id}/rabbit-hole")
async def rabbit_hole(paper_id: str, db: AsyncSession = Depends(get_db)):
    result = await get_rabbit_hole(paper_id, db)
    if result is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return result


@router.get("/papers/{paper_id}/missing-experiments")
async def missing_experiments(paper_id: str, db: AsyncSession = Depends(get_db)):
    return await get_missing_experiments(paper_id, db)


# ── Phase 10: Survey Generation, Gap Ranking, Contamination ──────────────────

@router.post("/surveys/generate")
async def create_survey(
    topic: str = Query(..., description="Research topic, e.g. 'sparse attention mechanisms'"),
    since_year: int = Query(default=0, description="Filter papers published on or after this year"),
    db: AsyncSession = Depends(get_db),
):
    return await generate_survey(topic, since_year, db)


@router.get("/gaps")
async def research_gaps(
    limit: int = Query(default=20, le=50),
    db: AsyncSession = Depends(get_db),
):
    return await rank_research_gaps(db, limit=limit)


@router.get("/benchmarks/contamination")
async def benchmark_contamination(db: AsyncSession = Depends(get_db)):
    return await get_benchmark_contamination(db)


@router.get("/papers/{paper_id}/contamination-warnings")
async def paper_contamination(paper_id: str, db: AsyncSession = Depends(get_db)):
    return await get_paper_contamination_warnings(paper_id, db)


# ── Phase 11: Research Memory ─────────────────────────────────────────────────

@router.post("/memory/query")
async def memory_query(
    question: str = Query(..., description="Natural language question about your research history"),
    db: AsyncSession = Depends(get_db),
):
    return await query_memory(question, db)


@router.get("/memory/events")
async def memory_events(
    limit: int = Query(default=50, le=200),
    event_type: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    return await list_events(db, limit=limit, event_type=event_type or None)


# ── Phase 12: Export ──────────────────────────────────────────────────────────

@router.get("/export/bibtex")
async def export_bibtex(db: AsyncSession = Depends(get_db)):
    from export.bibtex import generate_bibtex
    from fastapi.responses import Response
    content = await generate_bibtex(db)
    return Response(content=content, media_type="text/plain", headers={
        "Content-Disposition": "attachment; filename=lumen_library.bib"
    })


@router.get("/export/obsidian")
async def export_obsidian(
    topic: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    from export.obsidian import generate_obsidian_vault
    from fastapi.responses import Response
    zip_bytes = await generate_obsidian_vault(topic or None, db)
    return Response(content=zip_bytes, media_type="application/zip", headers={
        "Content-Disposition": "attachment; filename=lumen_vault.zip"
    })


@router.post("/export/notion")
async def export_notion(
    database_id: str = Query(..., description="Notion database ID"),
    topic: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    from export.notion import export_to_notion
    result = await export_to_notion(database_id, topic or None, db)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result
