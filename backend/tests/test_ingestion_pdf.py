from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ingestion.pdf import clean_text, extract_paper_text, truncate_to_budget, MAX_CHARS


class TestCleanText:
    def test_collapses_multiple_blank_lines(self):
        raw = "line one\n\n\n\nline two"
        result = clean_text(raw)
        assert "\n\n\n" not in result
        assert "line one" in result
        assert "line two" in result

    def test_collapses_multiple_spaces(self):
        raw = "word    another"
        assert clean_text(raw) == "word another"

    def test_strips_standalone_page_numbers(self):
        raw = "Introduction\n  3  \nSome text"
        result = clean_text(raw)
        assert "  3  " not in result

    def test_strips_leading_trailing_whitespace(self):
        raw = "   hello world   "
        assert clean_text(raw) == "hello world"

    def test_empty_string(self):
        assert clean_text("") == ""


class TestTruncateToBudget:
    def test_short_text_is_unchanged(self):
        text = "Short text"
        assert truncate_to_budget(text) == text

    def test_long_text_is_truncated(self):
        long_text = "x" * (MAX_CHARS + 1000)
        result = truncate_to_budget(long_text)
        assert len(result) <= MAX_CHARS

    def test_prioritizes_abstract_section(self):
        abstract_content = "This is the abstract. " * 100
        method_content = "This is the method section. " * 100
        filler = "z" * (MAX_CHARS + 5000)

        text = f"Abstract\n{abstract_content}\nMethod\n{method_content}\n{filler}"
        result = truncate_to_budget(text)

        assert "abstract" in result.lower()

    def test_result_within_budget(self):
        text = "A" * (MAX_CHARS * 2)
        result = truncate_to_budget(text)
        assert len(result) <= MAX_CHARS


class TestExtractPaperText:
    async def test_downloads_and_extracts(self):
        fake_pdf_bytes = b"%PDF fake content"

        with (
            patch("ingestion.pdf.download_pdf", new_callable=AsyncMock, return_value=fake_pdf_bytes),
            patch("ingestion.pdf.extract_text", return_value="Extracted text from PDF."),
        ):
            result = await extract_paper_text("https://arxiv.org/pdf/1706.03762")

        assert "Extracted text from PDF." in result

    async def test_raises_on_failed_download(self):
        with patch(
            "ingestion.pdf.download_pdf",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock()),
        ):
            with pytest.raises(httpx.HTTPStatusError):
                await extract_paper_text("https://bad-url.example/file.pdf")
