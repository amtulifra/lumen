from unittest.mock import MagicMock

import pytest

from suggestions.benchmark_drift import get_drift_series, get_current_sota, list_tracked_datasets
from tests.conftest import make_mock_db, make_mock_result


class TestGetDriftSeries:
    @pytest.mark.asyncio
    async def test_returns_sorted_data_points(self):
        db = make_mock_db()

        row_a = MagicMock()
        row_a.year = 2022
        row_a.sota_value = 85.0
        row_a.model = "ViT"
        row_a.paper_id = "paper_a"
        row_a.title = "ViT Paper"

        row_b = MagicMock()
        row_b.year = 2023
        row_b.sota_value = 88.0
        row_b.model = "ConvNeXt"
        row_b.paper_id = "paper_b"
        row_b.title = "ConvNeXt Paper"

        db.execute.return_value = make_mock_result([row_a, row_b])

        result = await get_drift_series("ImageNet", "top-1 accuracy", db)

        assert len(result) == 2
        assert result[0]["year"] == 2022
        assert result[1]["sota_value"] == 88.0
        assert result[1]["model"] == "ConvNeXt"

    @pytest.mark.asyncio
    async def test_returns_empty_for_unknown_dataset(self):
        db = make_mock_db()
        db.execute.return_value = make_mock_result([])

        result = await get_drift_series("UnknownDataset", "unknown_metric", db)
        assert result == []

    @pytest.mark.asyncio
    async def test_result_contains_required_fields(self):
        db = make_mock_db()

        row = MagicMock()
        row.year = 2024
        row.sota_value = 92.1
        row.model = "GPT-5"
        row.paper_id = "p1"
        row.title = "GPT-5 Paper"
        db.execute.return_value = make_mock_result([row])

        result = await get_drift_series("MMLU", "accuracy", db)

        assert "year" in result[0]
        assert "sota_value" in result[0]
        assert "model" in result[0]
        assert "paper_id" in result[0]
        assert "paper_title" in result[0]


class TestListTrackedDatasets:
    @pytest.mark.asyncio
    async def test_returns_dataset_metric_pairs(self):
        db = make_mock_db()

        row_a = MagicMock()
        row_a.dataset = "ImageNet"
        row_a.metric = "top-1 accuracy"

        row_b = MagicMock()
        row_b.dataset = "MMLU"
        row_b.metric = "accuracy"

        db.execute.return_value = make_mock_result([row_a, row_b])

        result = await list_tracked_datasets(db)

        assert len(result) == 2
        assert result[0] == {"dataset": "ImageNet", "metric": "top-1 accuracy"}

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_data(self):
        db = make_mock_db()
        db.execute.return_value = make_mock_result([])

        result = await list_tracked_datasets(db)
        assert result == []


class TestGetCurrentSota:
    @pytest.mark.asyncio
    async def test_returns_top_performer(self):
        db = make_mock_db()

        sota_row = {"model": "GPT-4o", "value": 91.5, "title": "GPT-4o Paper", "paper_id": "p1"}
        result_mock = make_mock_result([sota_row])
        result_mock.mappings.return_value.one_or_none.return_value = sota_row
        db.execute.return_value = result_mock

        result = await get_current_sota("MMLU", "accuracy", db)

        assert result["model"] == "GPT-4o"
        assert result["value"] == 91.5

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_dataset(self):
        db = make_mock_db()
        result_mock = make_mock_result([])
        result_mock.mappings.return_value.one_or_none.return_value = None
        db.execute.return_value = result_mock

        result = await get_current_sota("Unknown", "metric", db)
        assert result is None
