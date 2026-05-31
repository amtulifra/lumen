from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from suggestions.hypotheses import check_hypotheses_for_paper, compute_status, judge_evidence
from tests.conftest import FAKE_EMBEDDING, make_mock_db, make_mock_result


class TestComputeStatus:
    def test_no_evidence_is_open(self):
        assert compute_status([], []) == "open"

    def test_only_for_is_supported(self):
        assert compute_status([{"paper_id": "p1"}], []) == "supported"

    def test_only_against_is_refuted(self):
        assert compute_status([], [{"paper_id": "p1"}]) == "refuted"

    def test_both_is_mixed(self):
        assert compute_status([{"paper_id": "p1"}], [{"paper_id": "p2"}]) == "mixed"


class TestJudgeEvidence:
    async def test_returns_supports(self):
        with patch("suggestions.hypotheses.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                return_value=MagicMock(content=[MagicMock(text="supports")])
            )
            result = await judge_evidence("sparse attention is sufficient", "We show sparse attention matches dense.", "Some Paper")

        assert result == "supports"

    async def test_returns_refutes(self):
        with patch("suggestions.hypotheses.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                return_value=MagicMock(content=[MagicMock(text="refutes")])
            )
            result = await judge_evidence("sparse attention is sufficient", "Dense attention is necessary.", "Some Paper")

        assert result == "refutes"

    async def test_returns_mixed(self):
        with patch("suggestions.hypotheses.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                return_value=MagicMock(content=[MagicMock(text="mixed")])
            )
            result = await judge_evidence("hypothesis", "Ambiguous finding.", "Paper")

        assert result == "mixed"

    async def test_falls_back_to_mixed_on_unexpected_response(self):
        with patch("suggestions.hypotheses.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                return_value=MagicMock(content=[MagicMock(text="I cannot determine this.")])
            )
            result = await judge_evidence("hypothesis", "Some claim.", "Paper")

        assert result == "mixed"


class TestCheckHypothesesForPaper:
    async def test_updates_hypothesis_when_similar_claim_found(self):
        db = make_mock_db()

        paper_result = make_mock_result([])
        paper_result.mappings.return_value.one_or_none.return_value = {"title": "Test Paper"}

        hypothesis_row = MagicMock()
        hypothesis_row.id = "hyp_1"
        hypothesis_row.text = "sparse attention is sufficient"
        hypothesis_row.status = "open"
        hypothesis_row.evidence_for = []
        hypothesis_row.evidence_against = []
        hypothesis_row.similarity = 0.91
        hypothesis_result = make_mock_result([hypothesis_row])

        update_result = make_mock_result([])
        db.execute.side_effect = [paper_result, hypothesis_result, update_result]

        extracted = {
            "claims": [{"text": "Sparse attention achieves parity with dense.", "confidence": 0.9, "evidence": "..."}]
        }

        with (
            patch("suggestions.hypotheses.embed_text", new_callable=AsyncMock, return_value=FAKE_EMBEDDING),
            patch("suggestions.hypotheses.judge_evidence", new_callable=AsyncMock, return_value="supports"),
            patch("suggestions.hypotheses.create_notification", new_callable=AsyncMock),
        ):
            await check_hypotheses_for_paper("paper_id", extracted, db)

        assert db.execute.call_count == 3
        db.commit.assert_called_once()

    async def test_skips_empty_claims(self):
        db = make_mock_db()

        paper_result = make_mock_result([])
        paper_result.mappings.return_value.one_or_none.return_value = {"title": "Paper"}
        db.execute.return_value = paper_result

        extracted = {"claims": [{"text": "", "confidence": 0.5, "evidence": ""}]}

        with patch("suggestions.hypotheses.embed_text", new_callable=AsyncMock, return_value=FAKE_EMBEDDING) as mock_embed:
            await check_hypotheses_for_paper("paper_id", extracted, db)

        mock_embed.assert_not_called()
