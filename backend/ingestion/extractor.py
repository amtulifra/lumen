import asyncio
import logging

from ingestion.extractors.benchmarks import extract_benchmarks
from ingestion.extractors.claims import extract_claims
from ingestion.extractors.limitations import extract_limitations, extract_open_problems
from ingestion.extractors.meta import extract_keywords, extract_related_work
from ingestion.extractors.methods import extract_methods

logger = logging.getLogger("lumen")


async def extract_knowledge(paper_text: str) -> dict:
    results = await asyncio.gather(
        extract_claims(paper_text),
        extract_methods(paper_text),
        extract_benchmarks(paper_text),
        extract_limitations(paper_text),
        extract_open_problems(paper_text),
        extract_related_work(paper_text),
        extract_keywords(paper_text),
        return_exceptions=True,
    )

    def safe(val, default):
        if isinstance(val, Exception):
            logger.warning("Extractor failed: %s", val)
            return default
        return val

    return {
        "claims": safe(results[0], []),
        "methods": safe(results[1], []),
        "benchmarks": safe(results[2], []),
        "limitations": safe(results[3], []),
        "open_problems": safe(results[4], []),
        "related_work": safe(results[5], []),
        "keywords": safe(results[6], []),
    }
