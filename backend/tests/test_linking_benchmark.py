from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linking.benchmark import link_by_benchmark
from tests.conftest import make_mock_db, make_mock_result


class TestLinkByBenchmark:
    @pytest.mark.asyncio
    async def test_creates_link_for_shared_dataset(self):
        db = make_mock_db()

        matching_row = MagicMock()
        matching_row.paper_id = "existing_paper"
        db.execute.return_value = make_mock_result([matching_row])

        with (
            patch("linking.benchmark.create_link", new_callable=AsyncMock) as mock_create,
            patch("linking.benchmark.knowledge_graph"),
        ):
            await link_by_benchmark(
                "new_paper",
                [{"dataset": "ImageNet", "metric": "top-1 accuracy", "value": 85.0, "model": "ViT", "split": "test"}],
                db,
            )

        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args.args[2] == "BENCHMARKS_ON"
        assert call_args.kwargs["metadata"]["dataset"] == "ImageNet"

    @pytest.mark.asyncio
    async def test_no_link_when_no_matching_papers(self):
        db = make_mock_db()
        db.execute.return_value = make_mock_result([])

        with patch("linking.benchmark.create_link", new_callable=AsyncMock) as mock_create:
            await link_by_benchmark(
                "new_paper",
                [{"dataset": "ImageNet", "metric": "top-1 accuracy", "value": 85.0, "model": "ViT", "split": "test"}],
                db,
            )

        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_empty_benchmarks(self):
        db = make_mock_db()

        with patch("linking.benchmark.create_link", new_callable=AsyncMock) as mock_create:
            await link_by_benchmark("paper", [], db)

        mock_create.assert_not_called()
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_links_multiple_papers(self):
        db = make_mock_db()

        row_a = MagicMock()
        row_a.paper_id = "paper_a"
        row_b = MagicMock()
        row_b.paper_id = "paper_b"
        db.execute.return_value = make_mock_result([row_a, row_b])

        with (
            patch("linking.benchmark.create_link", new_callable=AsyncMock) as mock_create,
            patch("linking.benchmark.knowledge_graph"),
        ):
            await link_by_benchmark(
                "new_paper",
                [{"dataset": "MMLU", "metric": "accuracy", "value": 90.0, "model": "GPT-4", "split": "test"}],
                db,
            )

        assert mock_create.call_count == 2
