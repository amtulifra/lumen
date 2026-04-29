from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linking.contradiction import detect_contradictions
from tests.conftest import make_mock_db, make_mock_result


class TestDetectContradictions:
    @pytest.mark.asyncio
    async def test_creates_contradicts_link_above_delta(self):
        db = make_mock_db()

        existing_row = MagicMock()
        existing_row.paper_id = "old_paper"
        existing_row.value = 85.0
        db.execute.return_value = make_mock_result([existing_row])

        new_benchmarks = [
            {"dataset": "ImageNet", "metric": "top-1", "model": "ViT", "value": 88.0, "split": "test"}
        ]

        with (
            patch("linking.contradiction.create_link", new_callable=AsyncMock) as mock_create,
            patch("linking.contradiction.knowledge_graph"),
        ):
            await detect_contradictions("new_paper", new_benchmarks, db)

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["metadata"]["delta"] == pytest.approx(3.0)
        assert call_kwargs["metadata"]["value_a"] == 88.0
        assert call_kwargs["metadata"]["value_b"] == 85.0

    @pytest.mark.asyncio
    async def test_no_link_when_delta_within_threshold(self):
        db = make_mock_db()

        existing_row = MagicMock()
        existing_row.paper_id = "old_paper"
        existing_row.value = 88.5
        db.execute.return_value = make_mock_result([existing_row])

        new_benchmarks = [
            {"dataset": "ImageNet", "metric": "top-1", "model": "ViT", "value": 88.0, "split": "test"}
        ]

        with patch("linking.contradiction.create_link", new_callable=AsyncMock) as mock_create:
            await detect_contradictions("new_paper", new_benchmarks, db)

        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_empty_benchmarks(self):
        db = make_mock_db()

        with patch("linking.contradiction.create_link", new_callable=AsyncMock) as mock_create:
            await detect_contradictions("paper", [], db)

        mock_create.assert_not_called()
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_existing_papers_no_contradiction(self):
        db = make_mock_db()
        db.execute.return_value = make_mock_result([])

        new_benchmarks = [
            {"dataset": "MMLU", "metric": "accuracy", "model": "GPT-4", "value": 90.0, "split": "test"}
        ]

        with patch("linking.contradiction.create_link", new_callable=AsyncMock) as mock_create:
            await detect_contradictions("paper", new_benchmarks, db)

        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_link_type_is_contradicts(self):
        db = make_mock_db()

        existing_row = MagicMock()
        existing_row.paper_id = "other"
        existing_row.value = 70.0
        db.execute.return_value = make_mock_result([existing_row])

        new_benchmarks = [
            {"dataset": "HumanEval", "metric": "pass@1", "model": "CodeLM", "value": 80.0, "split": "test"}
        ]

        with (
            patch("linking.contradiction.create_link", new_callable=AsyncMock) as mock_create,
            patch("linking.contradiction.knowledge_graph"),
        ):
            await detect_contradictions("paper", new_benchmarks, db)

        assert mock_create.call_args.args[2] == "CONTRADICTS"
