"""Tests for new endpoints: search, delete, neighbors, RSS subscriptions, notifications."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import FAKE_PAPER_ID


def make_test_app():
    from fastapi import FastAPI
    from api.routes import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(mock_db):
    from fastapi.testclient import TestClient

    app = make_test_app()
    from database import get_db

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


class TestSearchPapers:
    def test_search_with_query_calls_search_papers(self, client, mock_db):
        results = [{"id": "p1", "title": "Attention Is All You Need", "authors": [], "year": 2017, "arxiv_url": None}]

        with (
            patch("api.routes.search_papers", new_callable=AsyncMock, return_value=results),
        ):
            response = client.get("/papers?q=attention")

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_empty_query_calls_list_papers(self, client, mock_db):
        with (
            patch("api.routes.list_papers", new_callable=AsyncMock, return_value=[]),
        ):
            response = client.get("/papers")

        assert response.status_code == 200

    def test_whitespace_query_calls_list_papers(self, client, mock_db):
        with (
            patch("api.routes.list_papers", new_callable=AsyncMock, return_value=[]),
        ):
            response = client.get("/papers?q=   ")

        assert response.status_code == 200


class TestDeletePaper:
    def test_delete_existing_paper(self, client, mock_db):
        with (
            patch("api.routes.delete_paper", new_callable=AsyncMock, return_value=True),
        ):
            response = client.delete(f"/papers/{FAKE_PAPER_ID}")

        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

    def test_delete_nonexistent_paper_returns_404(self, client, mock_db):
        with (
            patch("api.routes.delete_paper", new_callable=AsyncMock, return_value=False),
        ):
            response = client.delete("/papers/nonexistent")

        assert response.status_code == 404


class TestNeighbors:
    def test_returns_neighbor_list(self, client):
        with patch("api.routes.knowledge_graph") as mock_graph:
            mock_graph.neighbors_db = AsyncMock(return_value=["paper_b", "paper_c"])
            response = client.get(f"/papers/{FAKE_PAPER_ID}/neighbors")

        assert response.status_code == 200
        data = response.json()
        assert data["paper_id"] == FAKE_PAPER_ID
        assert len(data["neighbors"]) == 2

    def test_passes_link_type_filter(self, client):
        with patch("api.routes.knowledge_graph") as mock_graph:
            mock_graph.neighbors_db = AsyncMock(return_value=["paper_b"])
            response = client.get(f"/papers/{FAKE_PAPER_ID}/neighbors?link_type=CITES")

        mock_graph.neighbors_db.assert_called_once()


class TestRSSSubscriptions:
    def test_list_subscriptions(self, client):
        with patch("api.routes.get_subscriptions", return_value={"cs.LG": "https://rss.arxiv.org/rss/cs.LG"}):
            response = client.get("/rss/subscriptions")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["category"] == "cs.LG"

    def test_add_subscription(self, client):
        with patch("api.routes.add_subscription") as mock_add:
            response = client.post(
                "/rss/subscriptions",
                json={"category": "cs.RO", "url": "https://rss.arxiv.org/rss/cs.RO"},
            )

        assert response.status_code == 200
        mock_add.assert_called_once_with("cs.RO", "https://rss.arxiv.org/rss/cs.RO")

    def test_remove_existing_subscription(self, client):
        with patch("api.routes.remove_subscription", return_value=True):
            response = client.delete("/rss/subscriptions/cs.LG")

        assert response.status_code == 200

    def test_remove_nonexistent_subscription_returns_404(self, client):
        with patch("api.routes.remove_subscription", return_value=False):
            response = client.delete("/rss/subscriptions/cs.XYZ")

        assert response.status_code == 404


class TestNotifications:
    def test_list_notifications(self, client, mock_db):
        fake_notifs = [
            {"id": "n1", "type": "hypothesis_evidence", "message": "New evidence", "payload": {}, "read": False, "created_at": "2026-04-29T12:00:00"}
        ]

        with (
            patch("api.routes.list_notifications", new_callable=AsyncMock, return_value=fake_notifs),
        ):
            response = client.get("/notifications")

        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_mark_notification_read(self, client, mock_db):
        with (
            patch("api.routes.mark_read", new_callable=AsyncMock, return_value=True),
        ):
            response = client.post("/notifications/n1/read")

        assert response.status_code == 200

    def test_mark_nonexistent_notification_returns_404(self, client, mock_db):
        with (
            patch("api.routes.mark_read", new_callable=AsyncMock, return_value=False),
        ):
            response = client.post("/notifications/bad_id/read")

        assert response.status_code == 404

    def test_mark_all_read(self, client, mock_db):
        with (
            patch("api.routes.mark_all_read", new_callable=AsyncMock),
        ):
            response = client.post("/notifications/read-all")

        assert response.status_code == 200


class TestPhaseEndpoints:
    def test_graph_full_normalizes_edge_shape(self, client, mock_db):
        with (
            patch(
                "api.routes.list_papers",
                new_callable=AsyncMock,
                return_value=[{"id": "p1", "title": "Paper"}],
            ),
            patch(
                "knowledge.store.get_all_links",
                new_callable=AsyncMock,
                return_value=[
                    {
                        "source_id": "p1",
                        "target_id": "p2",
                        "link_type": "CITES",
                        "strength": 0.9,
                        "metadata": {},
                    }
                ],
            ),
        ):
            response = client.get("/graph/full")

        assert response.status_code == 200
        edge = response.json()["edges"][0]
        assert edge["source"] == "p1"
        assert edge["target"] == "p2"

    def test_memory_events(self, client, mock_db):
        events = [{"id": "e1", "type": "paper_ingested", "content": "x", "occurred_at": "2026-01-01"}]
        with patch("api.routes.list_events", new_callable=AsyncMock, return_value=events):
            response = client.get("/memory/events")

        assert response.status_code == 200
        assert response.json()[0]["type"] == "paper_ingested"

    def test_memory_query(self, client, mock_db):
        payload = {"answer": "A", "events": []}
        with patch("api.routes.query_memory", new_callable=AsyncMock, return_value=payload):
            response = client.post("/memory/query?question=what%20changed")

        assert response.status_code == 200
        assert response.json()["answer"] == "A"

    def test_hypothesis_evidence_feedback(self, client, mock_db):
        payload = {"status": "ok", "feedback": "agree"}
        with patch("api.routes.submit_evidence_feedback", new_callable=AsyncMock, return_value=payload):
            response = client.post(
                "/hypotheses/evidence/e1/feedback",
                json={"feedback": "agree", "note": "looks correct"},
            )
        assert response.status_code == 200
        assert response.json()["feedback"] == "agree"

    def test_open_paper_from_evidence(self, client, mock_db):
        payload = {"paper_id": "p1"}
        with patch("api.routes.log_paper_open_from_evidence", new_callable=AsyncMock, return_value=payload):
            response = client.post("/hypotheses/evidence/e1/open-paper")
        assert response.status_code == 200
        assert response.json()["paper_id"] == "p1"

    def test_list_conflicts(self, client, mock_db):
        payload = [{"id": "c1", "severity": "likely", "dataset": "MMLU"}]
        with patch("api.routes.list_benchmark_conflicts", new_callable=AsyncMock, return_value=payload):
            response = client.get("/conflicts")
        assert response.status_code == 200
        assert response.json()[0]["id"] == "c1"

    def test_conflict_feedback(self, client, mock_db):
        payload = {"status": "ok", "feedback": "agree"}
        with patch("api.routes.submit_conflict_feedback", new_callable=AsyncMock, return_value=payload):
            response = client.post("/conflicts/c1/feedback", json={"feedback": "agree", "note": ""})
        assert response.status_code == 200
        assert response.json()["feedback"] == "agree"

    def test_list_claim_conflicts(self, client, mock_db):
        payload = [{"id": "cc1", "relation": "challenges"}]
        with patch("api.routes.list_claim_conflicts", new_callable=AsyncMock, return_value=payload):
            response = client.get("/conflicts/claims")
        assert response.status_code == 200
        assert response.json()[0]["id"] == "cc1"

    def test_claim_conflict_feedback(self, client, mock_db):
        payload = {"status": "ok", "feedback": "disagree"}
        with patch("api.routes.submit_claim_conflict_feedback", new_callable=AsyncMock, return_value=payload):
            response = client.post("/conflicts/claims/cc1/feedback", json={"feedback": "disagree", "note": ""})
        assert response.status_code == 200
        assert response.json()["feedback"] == "disagree"

    def test_claim_score(self, client, mock_db):
        with patch("api.routes.get_claim_score", new_callable=AsyncMock, return_value={"score": 0.7}):
            response = client.get("/claims/c1/score")
        assert response.status_code == 200
        assert response.json()["score"] == 0.7

    def test_claim_lineage(self, client, mock_db):
        with patch("api.routes.get_claim_lineage", new_callable=AsyncMock, return_value={"claim_id": "c1", "ancestors": []}):
            response = client.get("/claims/c1/lineage")
        assert response.status_code == 200
        assert response.json()["claim_id"] == "c1"

    def test_paper_claim_scores(self, client, mock_db):
        with patch("api.routes.get_paper_claim_scores", new_callable=AsyncMock, return_value=[{"claim_id": "c1"}]):
            response = client.get(f"/papers/{FAKE_PAPER_ID}/claim-scores")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_research_gaps(self, client, mock_db):
        with patch("api.routes.rank_research_gaps", new_callable=AsyncMock, return_value=[{"gap": "x"}]):
            response = client.get("/gaps")
        assert response.status_code == 200
        assert response.json()[0]["gap"] == "x"

    def test_generate_survey(self, client, mock_db):
        with patch("api.routes.generate_survey", new_callable=AsyncMock, return_value={"topic": "llm"}):
            response = client.post("/surveys/generate?topic=llm&since_year=2024")
        assert response.status_code == 200
        assert response.json()["topic"] == "llm"
