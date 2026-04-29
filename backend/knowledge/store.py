import json
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Float, Integer, String, Text, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from database import Base


class PaperRow(Base):
    __tablename__ = "papers"

    id = Column(String, primary_key=True)
    title = Column(Text, nullable=False)
    authors = Column(JSONB)
    year = Column(Integer)
    arxiv_url = Column(Text)
    pdf_url = Column(Text)
    raw_text = Column(Text)
    knowledge_obj = Column(JSONB)
    title_embedding = Column(Vector(1536))


async def paper_exists(paper_id: str, db: AsyncSession) -> bool:
    result = await db.execute(select(PaperRow.id).where(PaperRow.id == paper_id))
    return result.scalar() is not None


async def save_paper(
    meta: dict, extracted: dict, embeddings: dict, db: AsyncSession
) -> str:
    paper_id = meta["id"]

    row = PaperRow(
        id=paper_id,
        title=meta["title"],
        authors=meta["authors"],
        year=meta["year"],
        arxiv_url=meta.get("arxiv_url"),
        pdf_url=meta.get("pdf_url"),
        knowledge_obj=extracted,
        title_embedding=embeddings["title"],
    )
    db.add(row)

    claims = extracted.get("claims", [])
    claim_embeddings = embeddings.get("claims", [])
    for claim, embedding in zip(claims, claim_embeddings):
        await db.execute(
            text(
                "INSERT INTO claims (id, paper_id, text, confidence, evidence, embedding) "
                "VALUES (:id, :paper_id, :text, :confidence, :evidence, :embedding)"
            ),
            {
                "id": str(uuid.uuid4()),
                "paper_id": paper_id,
                "text": claim["text"],
                "confidence": claim.get("confidence", 0.0),
                "evidence": claim.get("evidence", ""),
                "embedding": json.dumps(embedding),
            },
        )

    methods = extracted.get("methods", [])
    method_embeddings = embeddings.get("methods", [])
    for method, embedding in zip(methods, method_embeddings):
        await db.execute(
            text(
                "INSERT INTO methods (id, paper_id, name, description, is_novel, embedding) "
                "VALUES (:id, :paper_id, :name, :description, :is_novel, :embedding)"
            ),
            {
                "id": str(uuid.uuid4()),
                "paper_id": paper_id,
                "name": method["name"],
                "description": method.get("description", ""),
                "is_novel": method.get("is_novel", False),
                "embedding": json.dumps(embedding),
            },
        )

    for bm in extracted.get("benchmarks", []):
        await db.execute(
            text(
                "INSERT INTO benchmarks (id, paper_id, dataset, metric, value, model, split) "
                "VALUES (:id, :paper_id, :dataset, :metric, :value, :model, :split)"
            ),
            {
                "id": str(uuid.uuid4()),
                "paper_id": paper_id,
                "dataset": bm["dataset"],
                "metric": bm["metric"],
                "value": bm.get("value", 0.0),
                "model": bm.get("model", ""),
                "split": bm.get("split", "test"),
            },
        )

        await db.execute(
            text(
                "INSERT INTO benchmark_drift (id, paper_id, dataset, metric, model, value, year) "
                "VALUES (:id, :paper_id, :dataset, :metric, :model, :value, :year)"
            ),
            {
                "id": str(uuid.uuid4()),
                "paper_id": paper_id,
                "dataset": bm["dataset"],
                "metric": bm["metric"],
                "model": bm.get("model", ""),
                "value": bm.get("value", 0.0),
                "year": meta.get("year", 0),
            },
        )

    open_problems = extracted.get("open_problems", [])
    problem_embeddings = embeddings.get("open_problems", [])
    for problem, embedding in zip(open_problems, problem_embeddings):
        await db.execute(
            text(
                "INSERT INTO open_problems (id, paper_id, text, embedding) "
                "VALUES (:id, :paper_id, :text, :embedding)"
            ),
            {
                "id": str(uuid.uuid4()),
                "paper_id": paper_id,
                "text": problem,
                "embedding": json.dumps(embedding),
            },
        )

    await db.commit()
    return paper_id


async def get_paper(paper_id: str, db: AsyncSession) -> dict | None:
    result = await db.execute(select(PaperRow).where(PaperRow.id == paper_id))
    row = result.scalar_one_or_none()
    if not row:
        return None
    return {
        "id": row.id,
        "title": row.title,
        "authors": row.authors,
        "year": row.year,
        "arxiv_url": row.arxiv_url,
        "pdf_url": row.pdf_url,
        "knowledge_obj": row.knowledge_obj,
    }


async def list_papers(db: AsyncSession, limit: int = 100) -> list[dict]:
    result = await db.execute(
        select(PaperRow.id, PaperRow.title, PaperRow.authors, PaperRow.year, PaperRow.arxiv_url)
        .order_by(PaperRow.id)
        .limit(limit)
    )
    return [
        {"id": r.id, "title": r.title, "authors": r.authors, "year": r.year, "arxiv_url": r.arxiv_url}
        for r in result.all()
    ]


async def find_similar_papers(
    embedding: list[float], db: AsyncSession, limit: int = 10
) -> list[dict]:
    rows = await db.execute(
        text(
            "SELECT id, title, 1 - (title_embedding <=> CAST(:emb AS vector)) AS similarity "
            "FROM papers "
            "ORDER BY title_embedding <=> CAST(:emb AS vector) "
            "LIMIT :limit"
        ),
        {"emb": json.dumps(embedding), "limit": limit},
    )
    return [{"id": r.id, "title": r.title, "similarity": r.similarity} for r in rows.all()]


async def create_link(
    source_id: str, target_id: str, link_type: str, strength: float, metadata: dict, db: AsyncSession
) -> None:
    await db.execute(
        text(
            "INSERT INTO paper_links (id, source_id, target_id, link_type, strength, metadata) "
            "VALUES (:id, :source_id, :target_id, :link_type, :strength, :metadata) "
            "ON CONFLICT DO NOTHING"
        ),
        {
            "id": str(uuid.uuid4()),
            "source_id": source_id,
            "target_id": target_id,
            "link_type": link_type,
            "strength": strength,
            "metadata": json.dumps(metadata),
        },
    )
    await db.commit()


async def get_paper_links(paper_id: str, db: AsyncSession) -> list[dict]:
    rows = await db.execute(
        text(
            "SELECT source_id, target_id, link_type, strength, metadata "
            "FROM paper_links "
            "WHERE source_id = :id OR target_id = :id"
        ),
        {"id": paper_id},
    )
    return [
        {
            "source_id": r.source_id,
            "target_id": r.target_id,
            "link_type": r.link_type,
            "strength": r.strength,
            "metadata": r.metadata,
        }
        for r in rows.all()
    ]


async def get_all_links(db: AsyncSession) -> list[dict]:
    rows = await db.execute(
        text("SELECT source_id, target_id, link_type, strength, metadata FROM paper_links")
    )
    return [
        {
            "source_id": r.source_id,
            "target_id": r.target_id,
            "link_type": r.link_type,
            "strength": r.strength,
            "metadata": r.metadata,
        }
        for r in rows.all()
    ]
