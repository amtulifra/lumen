import json
import uuid

from sqlalchemy import Column, Float, Integer, String, Text, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import UserDefinedType

from config import settings
from database import Base


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    def get_col_spec(self, **kwargs):
        return f"VECTOR({self.dimensions})"


class PaperRow(Base):
    __tablename__ = "papers"

    id = Column(String, primary_key=True)
    workspace_id = Column(Text, nullable=False, server_default=text("current_workspace_id()"))
    title = Column(Text, nullable=False)
    authors = Column(JSONB)
    year = Column(Integer)
    arxiv_url = Column(Text)
    pdf_url = Column(Text)
    raw_text = Column(Text)
    knowledge_obj = Column(JSONB)
    title_embedding = Column(Vector(settings.embedding_dimensions))


async def paper_exists(paper_id: str, db: AsyncSession) -> bool:
    result = await db.execute(
        text("SELECT id FROM papers WHERE id = :id AND workspace_id = current_workspace_id()"),
        {"id": paper_id},
    )
    return result.scalar() is not None


async def save_paper(
    meta: dict, extracted: dict, embeddings: dict, raw_text: str, db: AsyncSession
) -> str:
    paper_id = meta["id"]

    row = PaperRow(
        id=paper_id,
        title=meta["title"],
        authors=meta["authors"],
        year=meta["year"],
        arxiv_url=meta.get("arxiv_url"),
        pdf_url=meta.get("pdf_url"),
        raw_text=raw_text,
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
    result = await db.execute(
        text(
            "SELECT id, title, authors, year, arxiv_url, pdf_url, knowledge_obj "
            "FROM papers WHERE id = :id AND workspace_id = current_workspace_id()"
        ),
        {"id": paper_id},
    )
    row = result.mappings().one_or_none()
    if not row:
        return None
    return {
        "id": row["id"],
        "title": row["title"],
        "authors": row["authors"],
        "year": row["year"],
        "arxiv_url": row["arxiv_url"],
        "pdf_url": row["pdf_url"],
        "knowledge_obj": row["knowledge_obj"],
    }


async def list_papers(db: AsyncSession, limit: int = 100, offset: int = 0) -> list[dict]:
    result = await db.execute(
        select(PaperRow.id, PaperRow.title, PaperRow.authors, PaperRow.year, PaperRow.arxiv_url)
        .where(text("papers.workspace_id = current_workspace_id()"))
        .order_by(PaperRow.id)
        .limit(limit)
        .offset(offset)
    )
    return [
        {"id": r.id, "title": r.title, "authors": r.authors, "year": r.year, "arxiv_url": r.arxiv_url}
        for r in result.all()
    ]


async def search_papers(query: str, db: AsyncSession, limit: int = 20) -> list[dict]:
    result = await db.execute(
        text(
            "SELECT id, title, authors, year, arxiv_url "
            "FROM papers "
            "WHERE workspace_id = current_workspace_id() "
            "AND (title ILIKE '%' || :q || '%' "
            "   OR EXISTS ( "
            "       SELECT 1 FROM jsonb_array_elements_text(knowledge_obj->'keywords') kw "
            "       WHERE kw ILIKE '%' || :q || '%' "
            "   )) "
            "ORDER BY title "
            "LIMIT :limit"
        ),
        {"q": query, "limit": limit},
    )
    return [
        {"id": r.id, "title": r.title, "authors": r.authors, "year": r.year, "arxiv_url": r.arxiv_url}
        for r in result.all()
    ]


async def delete_paper(paper_id: str, db: AsyncSession) -> bool:
    result = await db.execute(
        text("DELETE FROM papers WHERE id = :id AND workspace_id = current_workspace_id()"),
        {"id": paper_id},
    )
    # Clean up stale paper_ids references in researchers
    await db.execute(
        text(
            "UPDATE researchers "
            "SET paper_ids = ( "
            "    SELECT jsonb_agg(pid) FROM jsonb_array_elements_text(paper_ids) pid "
            "    WHERE pid != :paper_id "
            ") "
            "WHERE workspace_id = current_workspace_id() AND paper_ids @> :pid_json"
        ),
        {"paper_id": paper_id, "pid_json": json.dumps([paper_id])},
    )
    await db.commit()
    return result.rowcount > 0


async def find_similar_papers(
    embedding: list[float], db: AsyncSession, limit: int = 10
) -> list[dict]:
    rows = await db.execute(
        text(
            "SELECT id, title, 1 - (title_embedding <=> CAST(:emb AS vector)) AS similarity "
            "FROM papers "
            "WHERE workspace_id = current_workspace_id() "
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
            "SELECT :id, :source_id, :target_id, :link_type, :strength, :metadata "
            "WHERE EXISTS (SELECT 1 FROM papers p WHERE p.id = :source_id AND p.workspace_id = current_workspace_id()) "
            "  AND EXISTS (SELECT 1 FROM papers p WHERE p.id = :target_id AND p.workspace_id = current_workspace_id()) "
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
            "SELECT pl.source_id, pl.target_id, pl.link_type, pl.strength, pl.metadata, "
            "       ps.title AS source_title, pt.title AS target_title "
            "FROM paper_links pl "
            "LEFT JOIN papers ps ON pl.source_id = ps.id "
            "LEFT JOIN papers pt ON pl.target_id = pt.id "
            "WHERE pl.workspace_id = current_workspace_id() "
            "AND (pl.source_id = :id OR pl.target_id = :id)"
        ),
        {"id": paper_id},
    )
    return [
        {
            "source_id": r.source_id,
            "source_title": r.source_title,
            "target_id": r.target_id,
            "target_title": r.target_title,
            "link_type": r.link_type,
            "strength": r.strength,
            "metadata": r.metadata,
        }
        for r in rows.all()
    ]


async def get_all_links(db: AsyncSession) -> list[dict]:
    rows = await db.execute(
        text(
            "SELECT source_id, target_id, link_type, strength, metadata "
            "FROM paper_links WHERE workspace_id = current_workspace_id()"
        )
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
