from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linking.method import link_by_method
from tests.conftest import FAKE_EMBEDDING, make_mock_db, make_mock_result


class TestLinkByMethod:
    @pytest.mark.asyncio
    async def test_creates_shares_method_link(self):
        db = make_mock_db()

        similar_row = MagicMock()
        similar_row.paper_id = "other_paper"
        similar_row.name = "LoRA"
        similar_row.similarity = 0.92
        db.execute.return_value = make_mock_result([similar_row])

        methods = [{"name": "Low-Rank Adaptation", "description": "Efficient fine-tuning via rank decomposition.", "is_novel": True}]

        with (
            patch("linking.method.create_link", new_callable=AsyncMock) as mock_create,
            patch("linking.method.knowledge_graph"),
        ):
            await link_by_method("new_paper", methods, [FAKE_EMBEDDING], db)

        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args.args[2] == "SHARES_METHOD"
        assert call_args.kwargs["strength"] == 0.92

    @pytest.mark.asyncio
    async def test_no_link_when_no_similar_methods(self):
        db = make_mock_db()
        db.execute.return_value = make_mock_result([])

        methods = [{"name": "Self-Attention", "description": "Scaled dot-product.", "is_novel": True}]

        with patch("linking.method.create_link", new_callable=AsyncMock) as mock_create:
            await link_by_method("paper", methods, [FAKE_EMBEDDING], db)

        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_empty_methods(self):
        db = make_mock_db()

        with patch("linking.method.create_link", new_callable=AsyncMock) as mock_create:
            await link_by_method("paper", [], [], db)

        mock_create.assert_not_called()
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_metadata_contains_method_names(self):
        db = make_mock_db()

        similar_row = MagicMock()
        similar_row.paper_id = "other"
        similar_row.name = "LoRA"
        similar_row.similarity = 0.88
        db.execute.return_value = make_mock_result([similar_row])

        methods = [{"name": "QLoRA", "description": "Quantized low-rank adaptation.", "is_novel": True}]

        with (
            patch("linking.method.create_link", new_callable=AsyncMock) as mock_create,
            patch("linking.method.knowledge_graph"),
        ):
            await link_by_method("paper", methods, [FAKE_EMBEDDING], db)

        metadata = mock_create.call_args.kwargs["metadata"]
        assert metadata["method_a"] == "QLoRA"
        assert metadata["method_b"] == "LoRA"
