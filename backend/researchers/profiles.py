import json
import uuid
from datetime import datetime, timezone

import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from researchers.github import find_github_repo, get_user_repos
from researchers.semantic_scholar import get_author_papers, search_author


def extract_research_themes(paper_titles: list[str]) -> list[str]:
    if not paper_titles:
        return []

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    titles_block = "\n".join(f"- {t}" for t in paper_titles[:10])
    prompt = (
        f"Here are recent paper titles by a researcher:\n{titles_block}\n\n"
        "Extract 5 research themes that characterize this researcher's body of work. "
        "Return as a JSON array of strings, nothing else."
    )
    message = client.messages.create(
        model=settings.claude_model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return json.loads(message.content[0].text.strip())


async def build_author_profile(
    author_name: str,
    paper_title: str,
    paper_abstract: str,
    paper_id: str,
    db: AsyncSession,
) -> str | None:
    existing = await db.execute(
        text("SELECT id FROM researchers WHERE name = :name"),
        {"name": author_name},
    )
    existing_id = existing.scalar_one_or_none()

    ss_data = search_author(author_name)
    if not ss_data:
        return None

    ss_id = ss_data.get("authorId", "")
    h_index = ss_data.get("hIndex", 0)
    citation_count = ss_data.get("citationCount", 0)
    affiliations = ss_data.get("affiliations", [])
    institution = affiliations[0] if affiliations else ""

    ss_papers = get_author_papers(ss_id)
    paper_titles = [p["title"] for p in ss_papers]
    themes = extract_research_themes(paper_titles)

    github_url = find_github_repo(paper_title, author_name, paper_abstract)
    github_username = None
    recent_repos: list[str] = []
    if github_url:
        github_username = github_url.rstrip("/").split("/")[-2]
        recent_repos = get_user_repos(github_username)

    profile_id = existing_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    if existing_id:
        await db.execute(
            text(
                "UPDATE researchers SET institution=:institution, h_index=:h_index, "
                "citation_count=:citation_count, research_themes=:themes, "
                "github_username=:github, recent_repos=:repos, refreshed_at=:now "
                "WHERE id=:id"
            ),
            {
                "institution": institution,
                "h_index": h_index,
                "citation_count": citation_count,
                "themes": json.dumps(themes),
                "github": github_username,
                "repos": json.dumps(recent_repos),
                "now": now,
                "id": profile_id,
            },
        )
    else:
        await db.execute(
            text(
                "INSERT INTO researchers "
                "(id, name, institution, semantic_scholar_id, github_username, h_index, "
                "citation_count, research_themes, paper_ids, recent_repos, refreshed_at) "
                "VALUES (:id, :name, :institution, :ss_id, :github, :h_index, "
                ":citation_count, :themes, :paper_ids, :repos, :now)"
            ),
            {
                "id": profile_id,
                "name": author_name,
                "institution": institution,
                "ss_id": ss_id,
                "github": github_username,
                "h_index": h_index,
                "citation_count": citation_count,
                "themes": json.dumps(themes),
                "paper_ids": json.dumps([paper_id]),
                "repos": json.dumps(recent_repos),
                "now": now,
            },
        )

    await db.commit()
    return profile_id


async def get_profile(researcher_id: str, db: AsyncSession) -> dict | None:
    result = await db.execute(
        text("SELECT * FROM researchers WHERE id = :id"),
        {"id": researcher_id},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def get_paper_researchers(paper_id: str, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        text(
            "SELECT r.* FROM researchers r "
            "WHERE r.paper_ids @> :paper_id_json"
        ),
        {"paper_id_json": json.dumps([paper_id])},
    )
    return [dict(row) for row in result.mappings().all()]


async def refresh_profile(researcher_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        text("SELECT name, paper_ids FROM researchers WHERE id = :id"),
        {"id": researcher_id},
    )
    row = result.mappings().one_or_none()
    if not row:
        return

    paper_ids = row["paper_ids"] or []
    if paper_ids:
        paper_result = await db.execute(
            text("SELECT title, knowledge_obj->>'abstract' AS abstract FROM papers WHERE id = :id"),
            {"id": paper_ids[0]},
        )
        paper = paper_result.mappings().one_or_none()
        if paper:
            await build_author_profile(
                row["name"],
                paper["title"],
                paper["abstract"] or "",
                paper_ids[0],
                db,
            )
