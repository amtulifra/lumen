import io
import json
import re
import zipfile
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _slug(title: str) -> str:
    """Convert title to a safe filename slug."""
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug[:60] or "untitled"


def _paper_to_md(paper: dict, links: list[dict]) -> str:
    ko = paper.get("knowledge_obj") or {}
    lines = [
        f"# {paper['title']}",
        "",
        f"**Authors:** {', '.join(paper.get('authors') or [])}  ",
        f"**Year:** {paper.get('year') or 'unknown'}  ",
    ]
    if paper.get("arxiv_url"):
        lines.append(f"**ArXiv:** [{paper['arxiv_url']}]({paper['arxiv_url']})  ")
    lines.append("")

    keywords = ko.get("keywords") or []
    if keywords:
        lines += ["## Keywords", " ".join(f"#{kw.replace(' ', '_')}" for kw in keywords), ""]

    claims = ko.get("claims") or []
    if claims:
        lines.append("## Claims")
        for c in claims:
            conf = c.get("confidence", 0)
            lines.append(f"- **[{conf:.0%}]** {c.get('text', '')}")
            if c.get("evidence"):
                lines.append(f"  > {c['evidence']}")
        lines.append("")

    methods = ko.get("methods") or []
    if methods:
        lines.append("## Methods")
        for m in methods:
            tag = "🆕 novel" if m.get("is_novel") else "borrowed"
            lines.append(f"- **{m.get('name', '')}** ({tag}) — {m.get('description', '')}")
        lines.append("")

    benchmarks = ko.get("benchmarks") or []
    if benchmarks:
        lines += [
            "## Benchmarks",
            "| Dataset | Metric | Model | Value |",
            "|---------|--------|-------|-------|",
        ]
        for b in benchmarks:
            lines.append(
                f"| {b.get('dataset','')} | {b.get('metric','')} | {b.get('model','')} | {b.get('value','')} |"
            )
        lines.append("")

    limitations = ko.get("limitations") or []
    if limitations:
        lines.append("## Limitations")
        for lim in limitations:
            lines.append(f"- {lim}")
        lines.append("")

    open_problems = ko.get("open_problems") or []
    if open_problems:
        lines.append("## Open Problems")
        for op in open_problems:
            lines.append(f"- {op}")
        lines.append("")

    # Graph links as wikilinks
    related_titles = set()
    for link in links:
        if link.get("source_id") == paper["id"]:
            t = link.get("target_title")
        else:
            t = link.get("source_title")
        if t:
            related_titles.add(t)

    related_work = ko.get("related_work") or []
    all_related = related_titles | set(related_work)
    if all_related:
        lines.append("## Related Papers")
        for title in sorted(all_related):
            lines.append(f"- [[{title}]]")
        lines.append("")

    return "\n".join(lines)


def _hypothesis_to_md(hyp: dict) -> str:
    lines = [
        f"# Hypothesis: {hyp['text'][:80]}{'…' if len(hyp['text']) > 80 else ''}",
        "",
        f"**Status:** {hyp.get('status', 'open')}  ",
        f"**Created:** {str(hyp.get('created_at', ''))[:10]}  ",
        "",
        f"> {hyp['text']}",
        "",
    ]
    evidence_for = hyp.get("evidence_for") or []
    if evidence_for:
        lines.append("## Evidence For")
        for ev in evidence_for[:10]:
            paper_id = ev.get("paper_id", "")
            claim = ev.get("claim_text", "")[:120]
            lines.append(f"- (paper `{paper_id}`) {claim}")
        lines.append("")

    evidence_against = hyp.get("evidence_against") or []
    if evidence_against:
        lines.append("## Evidence Against")
        for ev in evidence_against[:10]:
            paper_id = ev.get("paper_id", "")
            claim = ev.get("claim_text", "")[:120]
            lines.append(f"- (paper `{paper_id}`) {claim}")
        lines.append("")

    return "\n".join(lines)


def _index_to_md(papers: list[dict], hypotheses: list[dict]) -> str:
    lines = [
        "# Lumen Knowledge Vault",
        f"*Generated {datetime.now().strftime('%Y-%m-%d')}*",
        "",
        f"**{len(papers)} papers · {len(hypotheses)} hypotheses**",
        "",
        "## Papers",
    ]
    for p in sorted(papers, key=lambda x: (-(x.get("year") or 0), x.get("title", ""))):
        slug = _slug(p.get("title", "untitled"))
        year = p.get("year") or ""
        lines.append(f"- [[papers/{slug}|{p['title']}]] ({year})")

    if hypotheses:
        lines += ["", "## Hypotheses"]
        for h in hypotheses:
            slug = _slug(h["text"][:60])
            short = h["text"][:80]
            status = h.get("status", "open")
            lines.append(f"- [[hypotheses/{slug}|{short}]] — {status}")

    return "\n".join(lines)


async def generate_obsidian_vault(topic: str | None, db: AsyncSession) -> bytes:
    # Load papers
    if topic:
        from knowledge.embedder import embed_text
        emb = await embed_text(topic)
        rows = await db.execute(
            text(
                "SELECT id, title, authors, year, arxiv_url, knowledge_obj "
                "FROM papers "
                "WHERE workspace_id = current_workspace_id() "
                "ORDER BY title_embedding <=> CAST(:emb AS vector) "
                "LIMIT 50"
            ),
            {"emb": json.dumps(emb)},
        )
    else:
        rows = await db.execute(
            text("SELECT id, title, authors, year, arxiv_url, knowledge_obj FROM papers WHERE workspace_id = current_workspace_id() ORDER BY year DESC NULLS LAST")
        )
    papers = [dict(r) for r in rows.mappings().all()]

    # Load all links for these papers
    if papers:
        paper_ids = [p["id"] for p in papers]
        placeholders = ", ".join([f":p{i}" for i in range(len(paper_ids))])
        params = {f"p{i}": pid for i, pid in enumerate(paper_ids)}
        link_rows = await db.execute(
            text(
                f"SELECT pl.source_id, pl.target_id, pl.link_type, "
                f"ps.title AS source_title, pt.title AS target_title "
                f"FROM paper_links pl "
                f"LEFT JOIN papers ps ON pl.source_id = ps.id "
                f"LEFT JOIN papers pt ON pl.target_id = pt.id "
                f"WHERE pl.workspace_id = current_workspace_id() "
                f"AND (pl.source_id IN ({placeholders}) OR pl.target_id IN ({placeholders}))"
            ),
            params,
        )
        links = [dict(r) for r in link_rows.mappings().all()]
    else:
        links = []

    # Load hypotheses
    hyp_rows = await db.execute(
        text("SELECT id, text, status, evidence_for, evidence_against, created_at FROM hypotheses WHERE workspace_id = current_workspace_id() ORDER BY created_at DESC")
    )
    hypotheses = [dict(r) for r in hyp_rows.mappings().all()]

    # Build zip in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", _index_to_md(papers, hypotheses))

        for paper in papers:
            slug = _slug(paper.get("title", "untitled"))
            paper_links = [l for l in links if l["source_id"] == paper["id"] or l["target_id"] == paper["id"]]
            content = _paper_to_md(paper, paper_links)
            zf.writestr(f"papers/{slug}.md", content)

        for hyp in hypotheses:
            slug = _slug(hyp["text"][:60])
            content = _hypothesis_to_md(hyp)
            zf.writestr(f"hypotheses/{slug}.md", content)

    buf.seek(0)
    return buf.read()
