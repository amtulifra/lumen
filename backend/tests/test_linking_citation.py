from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linking.citation import FUZZY_DISTANCE_THRESHOLD, find_paper_by_title, link_by_citation
from tests.conftest import make_mock_db, make_mock_result


class TestFindPaperByTitle:
    @pytest.mark.asyncio
    async def test_exact_match_returns_id(self):
        db = make_mock_db()
        db.execute.return_value = make_mock_result(["paper_abc"])

        result = await find_paper_by_title("Attention Is All You Need", db)
        assert result == "paper_abc"

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self):
        db = make_mock_db()

        exact_result = make_mock_result([])
        exact_result.scalar_one_or_none.return_value = None

        fuzzy_row = MagicMock()
        fuzzy_row.id = "p1"
        fuzzy_row.title = "A Completely Different Paper"
        fuzzy_result = make_mock_result([fuzzy_row])

        db.execute.side_effect = [exact_result, fuzzy_result]

        result = await find_paper_by_title("Attention Is All You Need", db)
        assert result is None

    @pytest.mark.asyncio
    async def test_fuzzy_match_within_threshold(self):
        db = make_mock_db()

        exact_result = make_mock_result([])
        exact_result.scalar_one_or_none.return_value = None

        fuzzy_row = MagicMock()
        fuzzy_row.id = "paper_xyz"
        fuzzy_row.title = "Attention is All You Need"
        fuzzy_result = make_mock_result([fuzzy_row])

        db.execute.side_effect = [exact_result, fuzzy_result]

        result = await find_paper_by_title("Attention Is All You Need", db)
        assert result == "paper_xyz"


class TestLinkByCitation:
    @pytest.mark.asyncio
    async def test_creates_link_for_matching_title(self):
        db = make_mock_db()

        with (
            patch("linking.citation.find_paper_by_title", return_value="target_paper"),
            patch("linking.citation.create_link", new_callable=AsyncMock) as mock_create,
            patch("linking.citation.knowledge_graph"),
        ):
            await link_by_citation("source_paper", ["Attention Is All You Need"], db)

        mock_create.assert_called_once_with(
            "source_paper", "target_paper", "CITES", strength=1.0, metadata={}, db=db
        )

    @pytest.mark.asyncio
    async def test_skips_self_citation(self):
        db = make_mock_db()

        with (
            patch("linking.citation.find_paper_by_title", return_value="source_paper"),
            patch("linking.citation.create_link", new_callable=AsyncMock) as mock_create,
            patch("linking.citation.knowledge_graph"),
        ):
            await link_by_citation("source_paper", ["Same Paper Title"], db)

        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_unmatched_titles(self):
        db = make_mock_db()

        with (
            patch("linking.citation.find_paper_by_title", return_value=None),
            patch("linking.citation.create_link", new_callable=AsyncMock) as mock_create,
            patch("linking.citation.knowledge_graph"),
        ):
            await link_by_citation("source_paper", ["Unknown Title"], db)

        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_empty_related_work(self):
        db = make_mock_db()

        with patch("linking.citation.create_link", new_callable=AsyncMock) as mock_create:
            await link_by_citation("source_paper", [], db)

        mock_create.assert_not_called()
