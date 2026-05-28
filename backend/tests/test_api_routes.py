import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FAKE_EMBEDDING, FAKE_EXTRACTED, FAKE_PAPER_ID, FAKE_PAPER_META


def make_test_app():
    from fastapi import FastAPI
    from api.routes import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client():
    app = make_test_app()
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


class TestIngestURL:
    def test_returns_paper_id_and_knowledge_object(self, client, mock_db):
        with (
            patch("api.routes.fetch_paper", return_value=FAKE_PAPER_META),
            patch("api.routes.paper_exists", new_callable=AsyncMock, return_value=False),
            patch("api.routes.extract_paper_text", new_callable=AsyncMock, return_value="paper text"),
            patch("api.routes.extract_knowledge", new_callable=AsyncMock, return_value=FAKE_EXTRACTED),
            patch("api.routes.embed_knowledge_object", new_callable=AsyncMock, return_value={"title": FAKE_EMBEDDING, "claims": [], "methods": [], "open_problems": []}),
            patch("api.routes.save_paper", new_callable=AsyncMock),
            patch("api.routes.link_by_citation", new_callable=AsyncMock),
            patch("api.routes.link_by_method", new_callable=AsyncMock),
            patch("api.routes.link_by_benchmark", new_callable=AsyncMock),
            patch("api.routes.detect_contradictions", new_callable=AsyncMock),
            patch("api.routes.check_hypotheses_for_paper", new_callable=AsyncMock),
            patch("api.routes.get_db", return_value=mock_db),
        ):
            response = client.post("/ingest", json={"url": "https://arxiv.org/abs/1706.03762"})

        assert response.status_code == 200
        data = response.json()
        assert data["paper_id"] == FAKE_PAPER_ID
        assert "knowledge_object" in data
        assert "from_cache" in data

    def test_returns_400_on_bad_url(self, client):
        with patch("api.routes.fetch_paper", side_effect=Exception("arxiv error")):
            response = client.post("/ingest", json={"url": "not-a-valid-arxiv-url"})

        assert response.status_code == 400
        assert "Failed to fetch paper" in response.json()["detail"]

    def test_returns_cached_paper_if_exists(self, client, mock_db):
        cached_paper = {"knowledge_obj": FAKE_EXTRACTED}

        with (
            patch("api.routes.fetch_paper", return_value=FAKE_PAPER_META),
            patch("api.routes.paper_exists", new_callable=AsyncMock, return_value=True),
            patch("api.routes.get_paper", new_callable=AsyncMock, return_value=cached_paper),
            patch("api.routes.get_db", return_value=mock_db),
        ):
            response = client.post("/ingest", json={"url": "https://arxiv.org/abs/1706.03762"})

        assert response.status_code == 200
        data = response.json()
        assert data["paper_id"] == FAKE_PAPER_ID
        assert data["from_cache"] is True


class TestGetPaper:
    def test_returns_paper_when_found(self, client, mock_db):
        paper_data = {
            "id": FAKE_PAPER_ID,
            "title": "Attention Is All You Need",
            "authors": ["Vaswani"],
            "year": 2017,
            "arxiv_url": "https://arxiv.org/abs/1706.03762",
            "pdf_url": None,
            "knowledge_obj": FAKE_EXTRACTED,
        }

        with (
            patch("api.routes.get_paper", new_callable=AsyncMock, return_value=paper_data),
            patch("api.routes.get_db", return_value=mock_db),
        ):
            response = client.get(f"/papers/{FAKE_PAPER_ID}")

        assert response.status_code == 200
        assert response.json()["title"] == "Attention Is All You Need"

    def test_returns_404_when_not_found(self, client, mock_db):
        with (
            patch("api.routes.get_paper", new_callable=AsyncMock, return_value=None),
            patch("api.routes.get_db", return_value=mock_db),
        ):
            response = client.get("/papers/does_not_exist")

        assert response.status_code == 404


class TestSubgraph:
    def test_valid_depth_returns_subgraph(self, client):
        with patch("api.routes.knowledge_graph") as mock_graph:
            mock_graph.subgraph.return_value = {"nodes": [{"id": "a"}], "edges": []}
            response = client.get(f"/graph/subgraph/{FAKE_PAPER_ID}?depth=2")

        assert response.status_code == 200

    def test_depth_too_large_returns_400(self, client):
        response = client.get(f"/graph/subgraph/{FAKE_PAPER_ID}?depth=10")
        assert response.status_code == 400

    def test_depth_zero_returns_400(self, client):
        response = client.get(f"/graph/subgraph/{FAKE_PAPER_ID}?depth=0")
        assert response.status_code == 400


class TestHypotheses:
    def test_create_hypothesis_returns_id(self, client, mock_db):
        with (
            patch("api.routes.create_hypothesis", new_callable=AsyncMock, return_value="hyp_123"),
            patch("api.routes.get_db", return_value=mock_db),
        ):
            response = client.post("/hypotheses", json={"text": "Sparse attention is sufficient."})

        assert response.status_code == 200
        assert response.json()["id"] == "hyp_123"

    def test_get_hypothesis_returns_404_when_missing(self, client, mock_db):
        with (
            patch("api.routes.get_hypothesis", new_callable=AsyncMock, return_value=None),
            patch("api.routes.get_db", return_value=mock_db),
        ):
            response = client.get("/hypotheses/nonexistent_id")

        assert response.status_code == 404

    def test_list_hypotheses_returns_list(self, client, mock_db):
        fake_hypotheses = [
            {"id": "h1", "text": "Hypothesis one", "status": "open", "evidence_for": [], "evidence_against": []}
        ]

        with (
            patch("api.routes.list_hypotheses", new_callable=AsyncMock, return_value=fake_hypotheses),
            patch("api.routes.get_db", return_value=mock_db),
        ):
            response = client.get("/hypotheses")

        assert response.status_code == 200
        assert len(response.json()) == 1


class TestRSSStatus:
    def test_returns_feeds_and_schedule(self, client):
        response = client.get("/rss/status")

        assert response.status_code == 200
        data = response.json()
        assert "feeds" in data
        assert "schedule" in data
        assert isinstance(data["feeds"], list)
