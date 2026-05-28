from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linking.citation import find_paper_by_title, link_by_citation
from tests.conftest import make_mock_db, make_mock_result


class TestFindPaperByTitle:
    async def test_exact_match_returns_id(self):
        db = make_mock_db()
        db.execute.return_value = make_mock_result(["paper_abc"])

        result = await find_paper_by_title("Attention Is All You Need", db)
        assert result == "paper_abc"

    async def test_no_match_returns_none(self):
        db = make_mock_db()

        exact_result = make_mock_result([])
        exact_result.scalar_one_or_none.return_value = None

        trgm_result = MagicMock()
        trgm_result.one_or_none.return_value = None
        db.execute.side_effect = [exact_result, trgm_result]

        result = await find_paper_by_title("Attention Is All You Need", db)
        assert result is None

    async def test_trigram_match_returns_id(self):
        db = make_mock_db()

        exact_result = make_mock_result([])
        exact_result.scalar_one_or_none.return_value = None

        trgm_row = MagicMock()
        trgm_row.id = "paper_xyz"
        trgm_result = MagicMock()
        trgm_result.one_or_none.return_value = trgm_row
        db.execute.side_effect = [exact_result, trgm_result]

        result = await find_paper_by_title("Attention Is All You Need", db)
        assert result == "paper_xyz"


class TestLinkByCitation:
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

    async def test_skips_self_citation(self):
        db = make_mock_db()

        with (
            patch("linking.citation.find_paper_by_title", return_value="source_paper"),
            patch("linking.citation.create_link", new_callable=AsyncMock) as mock_create,
            patch("linking.citation.knowledge_graph"),
        ):
            await link_by_citation("source_paper", ["Same Paper Title"], db)

        mock_create.assert_not_called()

    async def test_skips_unmatched_titles(self):
        db = make_mock_db()

        with (
            patch("linking.citation.find_paper_by_title", return_value=None),
            patch("linking.citation.create_link", new_callable=AsyncMock) as mock_create,
            patch("linking.citation.knowledge_graph"),
        ):
            await link_by_citation("source_paper", ["Unknown Title"], db)

        mock_create.assert_not_called()

    async def test_handles_empty_related_work(self):
        db = make_mock_db()

        with patch("linking.citation.create_link", new_callable=AsyncMock) as mock_create:
            await link_by_citation("source_paper", [], db)

        mock_create.assert_not_called()
