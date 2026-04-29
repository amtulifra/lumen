import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from suggestions.frontier import fetch_method_gaps, fetch_relevant_papers, generate_suggestions
from tests.conftest import FAKE_EMBEDDING, make_mock_db, make_mock_result


class TestFetchMethodGaps:
    @pytest.mark.asyncio
    async def test_returns_empty_for_no_paper_ids(self):
        db = make_mock_db()
        result = await fetch_method_gaps([], FAKE_EMBEDDING, db)
        assert result == []
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_name_description_pairs(self):
        db = make_mock_db()

        row = MagicMock()
        row.name = "Sparse Attention"
        row.description = "Attends to only a subset of tokens."
        db.execute.return_value = make_mock_result([row])

        result = await fetch_method_gaps(["paper_a", "paper_b"], FAKE_EMBEDDING, db)

        assert len(result) == 1
        assert "Sparse Attention" in result[0]
        assert "Attends to only a subset of tokens." in result[0]

    @pytest.mark.asyncio
    async def test_uses_parameterized_query(self):
        db = make_mock_db()
        db.execute.return_value = make_mock_result([])

        paper_ids = ["p1", "p2"]
        await fetch_method_gaps(paper_ids, FAKE_EMBEDDING, db)

        call_args = db.execute.call_args
        query_str = str(call_args.args[0])
        params = call_args.args[1]

        assert "ids" in params
        assert params["ids"] == paper_ids
        assert "f'" not in query_str


class TestFetchRelevantPapers:
    @pytest.mark.asyncio
    async def test_returns_paper_dicts(self):
        db = make_mock_db()

        row = MagicMock()
        row.id = "paper_1"
        row.title = "Attention Is All You Need"
        row.knowledge_obj = {"claims": []}
        db.execute.return_value = make_mock_result([row])

        result = await fetch_relevant_papers(FAKE_EMBEDDING, db)

        assert len(result) == 1
        assert result[0]["id"] == "paper_1"
        assert result[0]["title"] == "Attention Is All You Need"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_papers(self):
        db = make_mock_db()
        db.execute.return_value = make_mock_result([])

        result = await fetch_relevant_papers(FAKE_EMBEDDING, db)
        assert result == []


class TestGenerateSuggestions:
    @pytest.mark.asyncio
    async def test_returns_suggestions_and_relevant_papers(self):
        db = make_mock_db()

        fake_suggestions = [
            {
                "direction": "Apply sparse attention to code generation.",
                "rationale": "Efficiency gap.",
                "papers": ["LoRA"],
                "difficulty": "1-month project",
            }
        ]

        with (
            patch("suggestions.frontier.embed_text", return_value=FAKE_EMBEDDING),
            patch("suggestions.frontier.fetch_relevant_papers", new_callable=AsyncMock, return_value=[{"id": "p1", "title": "Paper"}]),
            patch("suggestions.frontier.fetch_relevant_open_problems", new_callable=AsyncMock, return_value=["Problem A"]),
            patch("suggestions.frontier.fetch_method_gaps", new_callable=AsyncMock, return_value=["Method B: desc"]),
            patch("suggestions.frontier.anthropic.Anthropic") as mock_anthropic,
        ):
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text=json.dumps(fake_suggestions))]
            )

            result = await generate_suggestions("I want to work on efficient attention.", db)

        assert "suggestions" in result
        assert "relevant_papers" in result
        assert len(result["suggestions"]) == 1
        assert result["suggestions"][0]["difficulty"] == "1-month project"

    @pytest.mark.asyncio
    async def test_prompt_includes_user_notes(self):
        db = make_mock_db()
        user_notes = "I am thinking about sparse attention for long documents."

        with (
            patch("suggestions.frontier.embed_text", return_value=FAKE_EMBEDDING),
            patch("suggestions.frontier.fetch_relevant_papers", new_callable=AsyncMock, return_value=[]),
            patch("suggestions.frontier.fetch_relevant_open_problems", new_callable=AsyncMock, return_value=[]),
            patch("suggestions.frontier.fetch_method_gaps", new_callable=AsyncMock, return_value=[]),
            patch("suggestions.frontier.anthropic.Anthropic") as mock_anthropic,
        ):
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client
            mock_client.messages.create.return_value = MagicMock(
                content=[MagicMock(text="[]")]
            )

            await generate_suggestions(user_notes, db)

        prompt_content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert user_notes in prompt_content
