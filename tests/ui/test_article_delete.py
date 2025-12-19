"""Tests for article delete endpoint.

Verifies that DELETE /ui/history/{id} removes an article
from the database and returns a success response.
"""

from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from src.api.main import app


class TestArticleDeleteEndpoint:
    """Tests for DELETE /ui/history/{id} endpoint."""

    def test_delete_article_returns_success(self):
        """DELETE /ui/history/{id} should return 200 on successful deletion.

        When an article exists and is deleted:
        - The endpoint returns 200 status
        - The delete function is called with the correct ID
        """
        with patch("src.api.main.delete_article_by_id") as mock_delete:
            mock_delete.return_value = True  # Deletion successful

            client = TestClient(app)
            response = client.delete("/ui/history/12345678-1234-5678-1234-567812345678")

            assert response.status_code == 200
            mock_delete.assert_called_once_with(UUID("12345678-1234-5678-1234-567812345678"))
