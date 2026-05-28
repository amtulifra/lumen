from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowledge.embedder import cosine_similarity, embed_knowledge_object, embed_text, embed_texts
from tests.conftest import FAKE_EMBEDDING, FAKE_EXTRACTED


def make_openai_embedding_response(embeddings: list[list[float]]) -> MagicMock:
    response = MagicMock()
    response.data = [MagicMock(embedding=emb) for emb in embeddings]
    return response


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self):
        vec = [1.0, 0.0, 0.0]
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors_score_zero(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors_score_negative_one(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        a = [0.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert cosine_similarity(a, b) == 0.0

    def test_both_zero_vectors_returns_zero(self):
        a = [0.0, 0.0]
        b = [0.0, 0.0]
        assert cosine_similarity(a, b) == 0.0

    def test_symmetry(self):
        a = [0.3, 0.7, 0.1]
        b = [0.1, 0.5, 0.9]
        assert cosine_similarity(a, b) == pytest.approx(cosine_similarity(b, a))


class TestEmbedText:
    async def test_returns_list_of_floats(self):
        with patch("knowledge.embedder._client") as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client
            mock_client.embeddings.create = AsyncMock(
                return_value=make_openai_embedding_response([FAKE_EMBEDDING])
            )
            result = await embed_text("some text")

        assert isinstance(result, list)
        assert len(result) == 1536
        assert all(isinstance(x, float) for x in result)

    async def test_calls_api_with_correct_model(self):
        with patch("knowledge.embedder._client") as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client
            mock_client.embeddings.create = AsyncMock(
                return_value=make_openai_embedding_response([FAKE_EMBEDDING])
            )
            await embed_text("text")

        call_kwargs = mock_client.embeddings.create.call_args.kwargs
        assert call_kwargs["model"] == "text-embedding-3-small"
        assert call_kwargs["input"] == "text"


class TestEmbedTexts:
    async def test_empty_list_returns_empty(self):
        result = await embed_texts([])
        assert result == []

    async def test_returns_one_embedding_per_text(self):
        texts = ["text a", "text b", "text c"]
        fake_embeddings = [FAKE_EMBEDDING] * 3

        with patch("knowledge.embedder._client") as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client
            mock_client.embeddings.create = AsyncMock(
                return_value=make_openai_embedding_response(fake_embeddings)
            )
            result = await embed_texts(texts)

        assert len(result) == 3

    async def test_single_api_call_for_batch(self):
        texts = ["a", "b", "c"]
        fake_embeddings = [FAKE_EMBEDDING] * 3

        with patch("knowledge.embedder._client") as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client
            mock_client.embeddings.create = AsyncMock(
                return_value=make_openai_embedding_response(fake_embeddings)
            )
            await embed_texts(texts)

        assert mock_client.embeddings.create.call_count == 1


class TestEmbedKnowledgeObject:
    async def test_returns_all_required_keys(self):
        num_claims = len(FAKE_EXTRACTED["claims"])
        num_methods = len(FAKE_EXTRACTED["methods"])
        num_problems = len(FAKE_EXTRACTED["open_problems"])

        with patch("knowledge.embedder._client") as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client
            mock_client.embeddings.create = AsyncMock(
                side_effect=[
                    make_openai_embedding_response([FAKE_EMBEDDING]),
                    make_openai_embedding_response([FAKE_EMBEDDING] * num_claims),
                    make_openai_embedding_response([FAKE_EMBEDDING] * num_methods),
                    make_openai_embedding_response([FAKE_EMBEDDING] * num_problems),
                ]
            )
            result = await embed_knowledge_object(FAKE_EXTRACTED, "Test Title")

        assert "title" in result
        assert "claims" in result
        assert "methods" in result
        assert "open_problems" in result

    async def test_empty_extracted_does_not_crash(self):
        empty_extracted = {"claims": [], "methods": [], "open_problems": []}

        with patch("knowledge.embedder._client") as mock_factory:
            mock_client = MagicMock()
            mock_factory.return_value = mock_client
            mock_client.embeddings.create = AsyncMock(
                return_value=make_openai_embedding_response([FAKE_EMBEDDING])
            )
            result = await embed_knowledge_object(empty_extracted, "Title")

        assert result["claims"] == []
        assert result["methods"] == []
        assert result["open_problems"] == []
