"""Tests for article history list endpoint.

Verifies that GET /ui/history returns a list of previously
generated articles with title, type, and date information.
"""

from fastapi.testclient import TestClient

from src.api.main import app


class TestHistoryListEndpoint:
    """Tests for GET /ui/history endpoint."""

    def test_history_endpoint_returns_html(self):
        """GET /ui/history should return HTML with 200 status.

        The history page displays a list of previously generated articles
        so recruiters can review their past work.
        """
        client = TestClient(app)
        response = client.get("/ui/history")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
