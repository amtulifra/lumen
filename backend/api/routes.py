from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import (
    GraphSubgraphOut,
    HypothesisCreateRequest,
    HypothesisOut,
    IngestAbstractRequest,
    IngestResponse,
    IngestURLRequest,
    RSSStatusOut,
    SuggestRequest,
)
from database import get_db
from ingestion.arxiv import fetch_paper
from ingestion.extractor import extract_knowledge
from ingestion.pdf import extract_paper_text
from ingestion.rss import get_rss_status, watch_feeds
from knowledge.embedder import embed_knowledge_object
from knowledge.graph import knowledge_graph
from knowledge.store import (
    create_link,
    get_paper,
    get_paper_links,
    list_papers,
    paper_exists,
    save_paper,
)
from linking.benchmark import link_by_benchmark
from linking.citation import link_by_citation
from linking.contradiction import detect_contradictions
from linking.method import link_by_method
from researchers.profiles import (
    build_author_profile,
    get_paper_researchers,
    get_profile,
    refresh_profile,
)
from suggestions.benchmark_drift import get_drift_series, list_tracked_datasets
from suggestions.frontier import generate_suggestions
from suggestions.hypotheses import (
    check_hypotheses_for_paper,
    create_hypothesis,
    get_hypothesis,
    list_hypotheses,
)

router = APIRouter()


async def run_full_ingestion(paper_meta: dict, db: AsyncSession) -> dict:
    paper_id = paper_meta["id"]

    if await paper_exists(paper_id, db):
        existing = await get_paper(paper_id, db)
        return {"paper_id": paper_id, "knowledge_object": existing["knowledge_obj"]}

    paper_text = extract_paper_text(paper_meta["pdf_url"])
    extracted = extract_knowledge(paper_text)
    embeddings = embed_knowledge_object(extracted, paper_meta["title"])

    await save_paper(paper_meta, extracted, embeddings, db)

    await link_by_citation(paper_id, extracted.get("related_work", []), db)
    await link_by_method(paper_id, extracted.get("methods", []), embeddings["methods"], db)
    await link_by_benchmark(paper_id, extracted.get("benchmarks", []), db)
    await detect_contradictions(paper_id, extracted.get("benchmarks", []), db)
    await check_hypotheses_for_paper(paper_id, extracted, db)

    for author in paper_meta.get("authors", []):
        await build_author_profile(
            author,
            paper_meta["title"],
            paper_meta.get("abstract", ""),
            paper_id,
            db,
        )

    return {"paper_id": paper_id, "knowledge_object": extracted}


@router.post("/ingest", response_model=IngestResponse)
async def ingest_url(request: IngestURLRequest, db: AsyncSession = Depends(get_db)):
    try:
        paper_meta = fetch_paper(request.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch paper: {exc}") from exc

    result = await run_full_ingestion(paper_meta, db)
    return IngestResponse(paper_id=result["paper_id"], knowledge_object=result["knowledge_object"])


@router.post("/ingest/abstract", response_model=IngestResponse)
async def ingest_abstract(request: IngestAbstractRequest, db: AsyncSession = Depends(get_db)):
    import hashlib

    paper_id = hashlib.sha256(request.title.encode()).hexdigest()[:16]

    if await paper_exists(paper_id, db):
        existing = await get_paper(paper_id, db)
        return IngestResponse(paper_id=paper_id, knowledge_object=existing["knowledge_obj"])

    paper_meta = {
        "id": paper_id,
        "title": request.title,
        "authors": [],
        "year": 0,
        "abstract": request.abstract,
        "pdf_url": "",
        "arxiv_url": "",
    }
    extracted = extract_knowledge(request.abstract)
    embeddings = embed_knowledge_object(extracted, request.title)
    await save_paper(paper_meta, extracted, embeddings, db)

    await link_by_citation(paper_id, extracted.get("related_work", []), db)
    await link_by_method(paper_id, extracted.get("methods", []), embeddings["methods"], db)
    await link_by_benchmark(paper_id, extracted.get("benchmarks", []), db)
    await detect_contradictions(paper_id, extracted.get("benchmarks", []), db)
    await check_hypotheses_for_paper(paper_id, extracted, db)

    return IngestResponse(paper_id=paper_id, knowledge_object=extracted)


@router.get("/papers")
async def list_all_papers(db: AsyncSession = Depends(get_db)):
    return await list_papers(db)


@router.get("/papers/{paper_id}")
async def get_paper_detail(paper_id: str, db: AsyncSession = Depends(get_db)):
    paper = await get_paper(paper_id, db)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.get("/papers/{paper_id}/links")
async def get_links(paper_id: str, db: AsyncSession = Depends(get_db)):
    return await get_paper_links(paper_id, db)


@router.get("/papers/{paper_id}/researchers")
async def get_researchers_for_paper(paper_id: str, db: AsyncSession = Depends(get_db)):
    return await get_paper_researchers(paper_id, db)


@router.get("/graph/subgraph/{paper_id}", response_model=GraphSubgraphOut)
async def get_subgraph(paper_id: str, depth: int = 2):
    if depth < 1 or depth > 5:
        raise HTTPException(status_code=400, detail="depth must be between 1 and 5")
    subgraph = knowledge_graph.subgraph(paper_id, depth=depth)
    return GraphSubgraphOut(nodes=subgraph["nodes"], edges=subgraph["edges"])


@router.get("/graph/contradictions")
async def get_contradictions():
    return knowledge_graph.get_contradictions()


@router.get("/graph/full")
async def get_full_graph(db: AsyncSession = Depends(get_db)):
    papers = await list_papers(db)
    from knowledge.store import get_all_links
    links = await get_all_links(db)
    return {"nodes": papers, "edges": links}


@router.get("/researchers/{researcher_id}")
async def get_researcher(researcher_id: str, db: AsyncSession = Depends(get_db)):
    profile = await get_profile(researcher_id, db)
    if not profile:
        raise HTTPException(status_code=404, detail="Researcher not found")
    return profile


@router.post("/researchers/{researcher_id}/refresh")
async def refresh_researcher(researcher_id: str, db: AsyncSession = Depends(get_db)):
    await refresh_profile(researcher_id, db)
    return {"status": "refreshed"}


@router.post("/suggestions")
async def get_suggestions(request: SuggestRequest, db: AsyncSession = Depends(get_db)):
    return await generate_suggestions(request.notes, db)


@router.post("/hypotheses")
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
async def benchmark_drift(
    dataset: str, metric: str, db: AsyncSession = Depends(get_db)
):
    return await get_drift_series(dataset, metric, db)


@router.get("/benchmarks/datasets")
async def tracked_datasets(db: AsyncSession = Depends(get_db)):
    return await list_tracked_datasets(db)


@router.get("/rss/status", response_model=RSSStatusOut)
async def rss_status():
    status = get_rss_status()
    return RSSStatusOut(feeds=status["feeds"], schedule=status["schedule"])


@router.post("/rss/run")
async def trigger_rss_run(db: AsyncSession = Depends(get_db)):
    await watch_feeds()
    return {"status": "completed"}
