import json
import logging

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings

logger = logging.getLogger("lumen")

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _headers() -> dict:
    if not settings.notion_api_key:
        raise ValueError("NOTION_API_KEY is not set in environment")
    return {
        "Authorization": f"Bearer {settings.notion_api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _paper_page_payload(paper: dict, database_id: str) -> dict:
    ko = paper.get("knowledge_obj") or {}
    claims = ko.get("claims") or []
    keywords = ko.get("keywords") or []
    authors = paper.get("authors") or []

    children = []

    if claims:
        children.append({
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Claims"}}]},
        })
        for c in claims[:5]:
            text_content = f"[{int((c.get('confidence') or 0) * 100)}%] {c.get('text', '')}"
            children.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text_content[:2000]}}]},
            })

    methods = ko.get("methods") or []
    if methods:
        children.append({
            "object": "block", "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "Methods"}}]},
        })
        for m in methods[:5]:
            tag = "[novel]" if m.get("is_novel") else "[borrowed]"
            text_content = f"{tag} {m.get('name', '')} — {m.get('description', '')}"
            children.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text_content[:2000]}}]},
            })

    return {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {"title": [{"type": "text", "text": {"content": (paper.get("title") or "Untitled")[:2000]}}]},
            "Year": {"number": paper.get("year") or 0},
            "Authors": {"rich_text": [{"type": "text", "text": {"content": ", ".join(str(a) for a in authors)[:2000]}}]},
            "ArXiv": {"url": paper.get("arxiv_url") or None},
            "Keywords": {"multi_select": [{"name": str(kw)[:100]} for kw in keywords[:5]]},
            "Status": {"select": {"name": "Ingested"}},
        },
        "children": children[:100],
    }


async def export_to_notion(database_id: str, topic: str | None, db: AsyncSession) -> dict:
    """Push papers to a Notion database. Requires NOTION_API_KEY in environment."""
    try:
        headers = _headers()
    except ValueError as e:
        return {"error": str(e), "exported": 0}

    if topic:
        from knowledge.embedder import embed_text
        emb = await embed_text(topic)
        rows = await db.execute(
            text(
                "SELECT id, title, authors, year, arxiv_url, knowledge_obj "
                "FROM papers "
                "WHERE workspace_id = current_workspace_id() "
                "ORDER BY title_embedding <=> CAST(:emb AS vector) "
                "LIMIT 30"
            ),
            {"emb": json.dumps(emb)},
        )
    else:
        rows = await db.execute(
            text("SELECT id, title, authors, year, arxiv_url, knowledge_obj FROM papers WHERE workspace_id = current_workspace_id() ORDER BY year DESC NULLS LAST LIMIT 100")
        )
    papers = [dict(r) for r in rows.mappings().all()]

    exported = 0
    errors = []
    async with httpx.AsyncClient(timeout=30) as client:
        for paper in papers:
            payload = _paper_page_payload(paper, database_id)
            try:
                resp = await client.post(f"{NOTION_API}/pages", headers=headers, json=payload)
                if resp.status_code == 200:
                    exported += 1
                else:
                    errors.append(f"{paper.get('title', paper['id'])}: {resp.status_code} {resp.text[:200]}")
            except Exception as e:
                errors.append(f"{paper.get('title', paper['id'])}: {e}")

    return {
        "exported": exported,
        "total": len(papers),
        "errors": errors[:10],
    }
