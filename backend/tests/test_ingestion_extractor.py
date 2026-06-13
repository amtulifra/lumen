from unittest.mock import AsyncMock, patch

import pytest

from ingestion.extractor import extract_knowledge
from tests.conftest import FAKE_EXTRACTED


class TestExtractKnowledge:
    async def test_assembles_results_from_all_extractors(self):
        with (
            patch("ingestion.extractor.chunk_by_sections", return_value=[{"section": "results", "text": "x"}]),
            patch(
                "ingestion.extractor._extract_section_payload",
                new=AsyncMock(
                    return_value={
                        "claims": FAKE_EXTRACTED["claims"],
                        "benchmarks": FAKE_EXTRACTED["benchmarks"],
                        "limitations": FAKE_EXTRACTED["limitations"],
                    }
                ),
            ),
            patch("ingestion.extractor.extract_methods", new=AsyncMock(return_value=FAKE_EXTRACTED["methods"])),
            patch("ingestion.extractor.extract_open_problems", new=AsyncMock(return_value=FAKE_EXTRACTED["open_problems"])),
            patch("ingestion.extractor.extract_related_work", new=AsyncMock(return_value=FAKE_EXTRACTED["related_work"])),
            patch("ingestion.extractor.extract_keywords", new=AsyncMock(return_value=FAKE_EXTRACTED["keywords"])),
        ):
            result = await extract_knowledge("some paper text")

        assert result["claims"][0]["text"] == FAKE_EXTRACTED["claims"][0]["text"]
        assert result["methods"][0]["name"] == "Self-Attention"
        assert result["benchmarks"][0]["value"] == 28.4
        assert result["limitations"] == FAKE_EXTRACTED["limitations"]
        assert result["keywords"] == FAKE_EXTRACTED["keywords"]

    async def test_returns_empty_lists_on_extractor_failure(self):
        with (
            patch("ingestion.extractor.chunk_by_sections", return_value=[{"section": "results", "text": "x"}]),
            patch("ingestion.extractor._extract_section_payload", new=AsyncMock(side_effect=Exception("API error"))),
            patch("ingestion.extractor.extract_methods", new=AsyncMock(return_value=FAKE_EXTRACTED["methods"])),
            patch("ingestion.extractor.extract_open_problems", new=AsyncMock(return_value=[])),
            patch("ingestion.extractor.extract_related_work", new=AsyncMock(return_value=[])),
            patch("ingestion.extractor.extract_keywords", new=AsyncMock(return_value=[])),
        ):
            result = await extract_knowledge("some paper text")

        # Failed extractors fall back to empty lists, not exceptions
        assert result["claims"] == []
        assert result["benchmarks"] == []
        # Successful extractors still work
        assert result["methods"][0]["name"] == "Self-Attention"

    async def test_passes_paper_text_to_chunker_and_section_extractor(self):
        paper_text = "This is a very specific paper about attention mechanisms."
        section_mock = AsyncMock(return_value={"claims": [], "benchmarks": [], "limitations": []})
        methods_mock = AsyncMock(return_value=[])

        with (
            patch("ingestion.extractor.chunk_by_sections", return_value=[{"section": "intro", "text": paper_text}]),
            patch("ingestion.extractor._extract_section_payload", new=section_mock),
            patch("ingestion.extractor.extract_methods", new=methods_mock),
            patch("ingestion.extractor.extract_open_problems", new=AsyncMock(return_value=[])),
            patch("ingestion.extractor.extract_related_work", new=AsyncMock(return_value=[])),
            patch("ingestion.extractor.extract_keywords", new=AsyncMock(return_value=[])),
        ):
            await extract_knowledge(paper_text)

        section_mock.assert_called_once_with("intro", paper_text)
        methods_mock.assert_called_once_with(paper_text)

    async def test_returns_all_required_keys(self):
        with (
            patch("ingestion.extractor.extract_claims", new=AsyncMock(return_value=[])),
            patch("ingestion.extractor.extract_methods", new=AsyncMock(return_value=[])),
            patch("ingestion.extractor.extract_benchmarks", new=AsyncMock(return_value=[])),
            patch("ingestion.extractor.extract_limitations", new=AsyncMock(return_value=[])),
            patch("ingestion.extractor.extract_open_problems", new=AsyncMock(return_value=[])),
            patch("ingestion.extractor.extract_related_work", new=AsyncMock(return_value=[])),
            patch("ingestion.extractor.extract_keywords", new=AsyncMock(return_value=[])),
        ):
            result = await extract_knowledge("text")

        required_keys = {"claims", "methods", "benchmarks", "limitations", "open_problems", "related_work", "keywords"}
        assert required_keys.issubset(result.keys())
