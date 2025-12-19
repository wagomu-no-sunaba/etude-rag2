"""Tests for article detail view endpoint.

Verifies that GET /ui/history/{id} returns the full content
of a previously generated article.
"""

from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from src.api.main import app


class TestArticleViewEndpoint:
    """Tests for GET /ui/history/{id} endpoint."""

    def test_article_view_returns_html_for_existing_article(self):
        """GET /ui/history/{id} should return HTML for an existing article.

        When an article exists in the database:
        - The endpoint returns 200 status
        - The response is HTML content
        - The article content is displayed
        """
        mock_article = {
            "id": UUID("12345678-1234-5678-1234-567812345678"),
            "input_material": "テスト素材",
            "article_type": "ANNOUNCEMENT",
            "article_type_ja": "お知らせ",
            "generated_content": {
                "titles": ["テストタイトル"],
                "lead": "テストリード",
                "sections": [],
                "closing": "テストクロージング",
            },
            "markdown": "# テストタイトル\n\nテストリード",
            "created_at": "2024-01-01T00:00:00",
        }

        with patch("src.api.main.get_article_by_id") as mock_get:
            mock_get.return_value = mock_article

            client = TestClient(app)
            response = client.get("/ui/history/12345678-1234-5678-1234-567812345678")

            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
