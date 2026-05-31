from pathlib import Path


VECTOR_QUERY_FILES = [
    "backend/knowledge/store.py",
    "backend/linking/method.py",
    "backend/suggestions/frontier.py",
    "backend/suggestions/hypotheses.py",
    "backend/knowledge/memory.py",
    "backend/knowledge/claim_intelligence.py",
    "backend/suggestions/survey.py",
    "backend/export/notion.py",
    "backend/export/obsidian.py",
]


def test_vector_queries_always_include_workspace_predicate() -> None:
    root = Path(__file__).resolve().parents[2]
    for rel_path in VECTOR_QUERY_FILES:
        content = (root / rel_path).read_text()
        assert "<=>" in content, f"{rel_path} no longer has vector queries; update the guard list"
        assert (
            "workspace_id = current_workspace_id()" in content
        ), f"{rel_path} must include explicit workspace predicate in vector SQL"
