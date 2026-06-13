import asyncio
import logging

from ingestion.chunker import chunk_by_sections
from ingestion.extractors.benchmarks import extract_benchmarks
from ingestion.extractors.claims import extract_claims
from ingestion.extractors.limitations import extract_limitations, extract_open_problems
from ingestion.extractors.meta import extract_keywords, extract_related_work
from ingestion.extractors.methods import extract_methods

logger = logging.getLogger("lumen")


async def extract_knowledge(paper_text: str) -> dict:
    section_chunks = chunk_by_sections(paper_text)
    claims: list[dict] = []
    benchmarks: list[dict] = []
    limitations: list[str] = []

    if section_chunks:
        section_results = await asyncio.gather(
            *[_extract_section_payload(chunk["section"], chunk["text"]) for chunk in section_chunks],
            return_exceptions=True,
        )
        for result in section_results:
            if isinstance(result, Exception):
                logger.warning("Section extractor failed: %s", result)
                continue
            claims.extend(result["claims"])
            benchmarks.extend(result["benchmarks"])
            limitations.extend(result["limitations"])

    results = await asyncio.gather(
        extract_methods(paper_text),
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
        "claims": _dedupe_claims(claims),
        "methods": safe(results[0], []),
        "benchmarks": _dedupe_benchmarks(benchmarks),
        "limitations": _dedupe_strings(limitations),
        "open_problems": safe(results[1], []),
        "related_work": safe(results[2], []),
        "keywords": safe(results[3], []),
    }


async def _extract_section_payload(section: str, section_text: str) -> dict:
    claims_raw, benchmarks_raw, limitations_raw = await asyncio.gather(
        extract_claims(section_text),
        extract_benchmarks(section_text),
        extract_limitations(section_text),
        return_exceptions=True,
    )

    claims = []
    if not isinstance(claims_raw, Exception):
        for claim in claims_raw if isinstance(claims_raw, list) else []:
            if not isinstance(claim, dict):
                continue
            claim.setdefault("section", section)
            claim.setdefault("page_number", None)
            evidence_span = claim.get("evidence_span", claim.get("evidence", ""))
            claim["evidence_span"] = evidence_span
            claim["evidence"] = evidence_span
            claims.append(claim)

    benchmarks = []
    if not isinstance(benchmarks_raw, Exception):
        for benchmark in benchmarks_raw if isinstance(benchmarks_raw, list) else []:
            if not isinstance(benchmark, dict):
                continue
            benchmark.setdefault("section", section)
            benchmark.setdefault("page_number", None)
            benchmark.setdefault("evidence_span", "")
            benchmarks.append(benchmark)

    limitations: list[str] = []
    if not isinstance(limitations_raw, Exception):
        limitations = [str(item).strip() for item in limitations_raw if str(item).strip()]

    return {"claims": claims, "benchmarks": benchmarks, "limitations": limitations}


def _dedupe_claims(claims: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for claim in claims:
        key = str(claim.get("text", "")).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(claim)
    return deduped


def _dedupe_benchmarks(benchmarks: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[dict] = []
    for bm in benchmarks:
        key = (
            str(bm.get("dataset", "")).strip().lower(),
            str(bm.get("metric", "")).strip().lower(),
            str(bm.get("model", "")).strip().lower(),
            str(bm.get("split", "")).strip().lower(),
        )
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        deduped.append(bm)
    return deduped


def _dedupe_strings(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
