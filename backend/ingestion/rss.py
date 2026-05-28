from datetime import datetime, timezone

import feedparser

from config import settings
from knowledge.embedder import embed_text
from knowledge.store import find_similar_papers, paper_exists


async def is_relevant(abstract: str, db) -> bool:
    embedding = await embed_text(abstract)
    similar = await find_similar_papers(embedding, db, limit=1)

    if not similar:
        return False

    return similar[0].get("similarity", 0) >= settings.rss_relevance_threshold


async def ingest_from_entry(entry, db) -> None:
    from ingestion.arxiv import parse_arxiv_id
    from ingestion.extractor import extract_knowledge
    from ingestion.pdf import extract_paper_text
    from knowledge.embedder import embed_knowledge_object
    from knowledge.store import save_paper
    from linking.benchmark import link_by_benchmark
    from linking.citation import link_by_citation
    from linking.contradiction import detect_contradictions
    from linking.method import link_by_method
    from suggestions.hypotheses import check_hypotheses_for_paper

    arxiv_url = entry.link
    arxiv_id = parse_arxiv_id(arxiv_url)

    if await paper_exists(arxiv_id, db):
        return

    pdf_url = arxiv_url.replace("/abs/", "/pdf/") + ".pdf"

    published = entry.get("published_parsed")
    year = datetime(*published[:3], tzinfo=timezone.utc).year if published else datetime.now(timezone.utc).year

    paper_meta = {
        "id": arxiv_id,
        "title": entry.title,
        "authors": [a.get("name", "") for a in entry.get("authors", [])][:5],
        "year": year,
        "abstract": entry.summary,
        "pdf_url": pdf_url,
        "arxiv_url": arxiv_url,
    }

    paper_text = await extract_paper_text(pdf_url)
    extracted = await extract_knowledge(paper_text)
    embeddings = await embed_knowledge_object(extracted, paper_meta["title"])
    paper_id = await save_paper(paper_meta, extracted, embeddings, paper_text, db)

    await link_by_citation(paper_id, extracted.get("related_work", []), db)
    await link_by_method(paper_id, extracted.get("methods", []), embeddings["methods"], db)
    await link_by_benchmark(paper_id, extracted.get("benchmarks", []), db)
    await detect_contradictions(paper_id, extracted.get("benchmarks", []), db)
    await check_hypotheses_for_paper(paper_id, extracted, db)


async def watch_feeds() -> None:
    from database import SessionLocal

    async with SessionLocal() as db:
        for category, url in settings.rss_feeds.items():
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if await is_relevant(entry.summary, db):
                    await ingest_from_entry(entry, db)


def get_rss_status() -> dict:
    return {
        "feeds": list(settings.rss_feeds.keys()),
        "schedule": "daily at 06:00 UTC",
    }
