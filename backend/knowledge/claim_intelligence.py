import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings

logger = logging.getLogger("lumen")

LINEAGE_RELATIONS = ("replicates", "challenges", "refines", "extends")


async def _judge_relation(claim_a: str, claim_b: str) -> str:
    """Ask Claude: does claim B replicate, challenge, refine, or extend claim A?"""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    prompt = (
        f"Older claim (Claim A): {claim_a}\n\n"
        f"Newer claim (Claim B): {claim_b}\n\n"
        "Does Claim B replicate, challenge, refine, or extend Claim A?\n"
        "- replicates: B confirms or reproduces A's finding\n"
        "- challenges: B contradicts or disputes A\n"
        "- refines: B narrows, qualifies, or improves on A\n"
        "- extends: B builds upon A to a new domain or setting\n\n"
        "Answer with exactly one word: replicates, challenges, refines, extends, or unrelated."
    )
    msg = await client.messages.create(
        model=settings.claude_model,
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    verdict = msg.content[0].text.strip().lower()
    if verdict not in (*LINEAGE_RELATIONS, "unrelated"):
        return "unrelated"
    return verdict


async def build_claim_lineage(paper_id: str, db: AsyncSession) -> None:
    """For each claim in a newly ingested paper, find similar older claims and classify the relation."""
    new_claims = await db.execute(
        text(
            "SELECT id, text, embedding FROM claims "
            "WHERE workspace_id = current_workspace_id() AND paper_id = :pid"
        ),
        {"pid": paper_id},
    )
    new_claim_rows = new_claims.mappings().all()

    for claim in new_claim_rows:
        if claim["embedding"] is None:
            continue

        similar = await db.execute(
            text(
                "SELECT c.id, c.text, c.paper_id, "
                "1 - (c.embedding <=> CAST(:emb AS vector)) AS similarity "
                "FROM claims c "
                "WHERE c.workspace_id = current_workspace_id() "
                "AND c.paper_id != :pid "
                "AND 1 - (c.embedding <=> CAST(:emb AS vector)) > 0.82 "
                "ORDER BY similarity DESC "
                "LIMIT 5"
            ),
            {"emb": json.dumps(list(claim["embedding"])), "pid": paper_id},
        )
        similar_rows = similar.mappings().all()
        if not similar_rows:
            continue

        async def judge_and_insert(parent_row, child_claim=claim):
            try:
                relation = await _judge_relation(parent_row["text"], child_claim["text"])
                if relation == "unrelated":
                    return
                await db.execute(
                    text(
                        "INSERT INTO claim_lineage "
                        "(id, workspace_id, parent_claim_id, child_claim_id, relation, confidence, created_at) "
                        "VALUES (:id, current_workspace_id(), :parent, :child, :relation, :confidence, :now) "
                        "ON CONFLICT (workspace_id, parent_claim_id, child_claim_id) DO NOTHING"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "parent": str(parent_row["id"]),
                        "child": str(claim["id"]),
                        "relation": relation,
                        "confidence": float(parent_row["similarity"]),
                        "now": datetime.now(timezone.utc),
                    },
                )
            except Exception:
                logger.exception("Failed to build lineage for claim %s", child_claim["id"])

        await asyncio.gather(*[judge_and_insert(row) for row in similar_rows])

    await db.commit()


async def get_claim_lineage(claim_id: str, db: AsyncSession) -> dict:
    """Return parents (claims this one builds on) and children (claims that build on this)."""
    parents = await db.execute(
        text(
            "SELECT cl.relation, cl.confidence, c.id AS claim_id, c.text, c.paper_id, "
            "p.title AS paper_title, p.year "
            "FROM claim_lineage cl "
            "JOIN claims c ON cl.parent_claim_id = c.id "
            "JOIN papers p ON c.paper_id = p.id "
            "WHERE cl.workspace_id = current_workspace_id() "
            "AND cl.child_claim_id = :cid "
            "ORDER BY p.year ASC"
        ),
        {"cid": claim_id},
    )
    children = await db.execute(
        text(
            "SELECT cl.relation, cl.confidence, c.id AS claim_id, c.text, c.paper_id, "
            "p.title AS paper_title, p.year "
            "FROM claim_lineage cl "
            "JOIN claims c ON cl.child_claim_id = c.id "
            "JOIN papers p ON c.paper_id = p.id "
            "WHERE cl.workspace_id = current_workspace_id() "
            "AND cl.parent_claim_id = :cid "
            "ORDER BY p.year ASC"
        ),
        {"cid": claim_id},
    )
    return {
        "claim_id": claim_id,
        "parents": [dict(r) for r in parents.mappings().all()],
        "children": [dict(r) for r in children.mappings().all()],
    }


async def get_claim_score(claim_id: str, db: AsyncSession) -> dict:
    """Compute the replication score: how well supported vs challenged this claim is."""
    rows = await db.execute(
        text(
            "SELECT relation FROM claim_lineage "
            "WHERE workspace_id = current_workspace_id() AND parent_claim_id = :cid"
        ),
        {"cid": claim_id},
    )
    relations = [r.relation for r in rows.all()]

    supported = sum(1 for r in relations if r in ("replicates", "extends"))
    challenged = sum(1 for r in relations if r == "challenges")
    neutral = sum(1 for r in relations if r == "refines")
    total = supported + challenged + neutral
    score = supported / total if total > 0 else 0.0

    return {
        "claim_id": claim_id,
        "supported": supported,
        "challenged": challenged,
        "neutral": neutral,
        "score": round(score, 3),
    }


async def get_paper_claim_scores(paper_id: str, db: AsyncSession) -> list[dict]:
    """Return all claims for a paper with their lineage scores."""
    claims = await db.execute(
        text(
            "SELECT id, text, confidence FROM claims "
            "WHERE workspace_id = current_workspace_id() AND paper_id = :pid ORDER BY confidence DESC"
        ),
        {"pid": paper_id},
    )
    claim_rows = claims.mappings().all()

    results = []
    for claim in claim_rows:
        score = await get_claim_score(str(claim["id"]), db)
        results.append({
            "claim_id": str(claim["id"]),
            "text": claim["text"],
            "extraction_confidence": claim["confidence"],
            "replication_score": score["score"],
            "supported_by": score["supported"],
            "challenged_by": score["challenged"],
            "refined_by": score["neutral"],
        })
    return results
