from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest

from ingestion.arxiv import fetch_paper, parse_arxiv_id


class TestParseArxivId:
    def test_standard_url(self):
        assert parse_arxiv_id("https://arxiv.org/abs/1706.03762") == "1706.03762"

    def test_url_with_version_suffix(self):
        assert parse_arxiv_id("https://arxiv.org/abs/1706.03762v3") == "1706.03762"

    def test_url_with_trailing_whitespace(self):
        assert parse_arxiv_id("https://arxiv.org/abs/2305.12345  ") == "2305.12345"

    def test_new_format_id(self):
        assert parse_arxiv_id("https://arxiv.org/abs/2312.00752") == "2312.00752"


class TestFetchPaper:
    def test_returns_expected_fields(self):
        mock_paper = MagicMock()
        mock_paper.title = "Attention Is All You Need"
        mock_paper.authors = [MagicMock(name="Vaswani"), MagicMock(name="Shazeer")]
        mock_paper.authors[0].name = "Vaswani"
        mock_paper.authors[1].name = "Shazeer"
        mock_paper.published = datetime(2017, 6, 12)
        mock_paper.summary = "We propose the Transformer..."
        mock_paper.pdf_url = "https://arxiv.org/pdf/1706.03762"

        with patch("ingestion.arxiv.arxiv.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.results.return_value = iter([mock_paper])

            result = fetch_paper("https://arxiv.org/abs/1706.03762")

        assert result["id"] == "1706.03762"
        assert result["title"] == "Attention Is All You Need"
        assert result["year"] == 2017
        assert "Vaswani" in result["authors"]
        assert result["arxiv_url"] == "https://arxiv.org/abs/1706.03762"

    def test_raises_on_empty_results(self):
        with patch("ingestion.arxiv.arxiv.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.results.return_value = iter([])

            with pytest.raises(StopIteration):
                fetch_paper("https://arxiv.org/abs/9999.99999")
