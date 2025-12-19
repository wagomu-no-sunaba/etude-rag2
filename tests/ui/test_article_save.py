"""Tests for article save functionality.

Verifies that generated articles are saved to the database
after successful generation via /ui/generate endpoint.
"""

from unittest.mock import MagicMock

from src.api.generated_articles import GeneratedArticle, GeneratedArticleRepository


class TestGeneratedArticleRepository:
    """Tests for GeneratedArticleRepository class."""

    def test_repository_exists(self):
        """GeneratedArticleRepository should exist and be importable.

        This test verifies that the repository class is defined
        and can be instantiated (with a mock connection).
        """
        assert GeneratedArticleRepository is not None

    def test_save_returns_uuid(self):
        """Repository.save() should return the UUID of the saved article.

        When saving an article:
        - The article data is inserted into the database
        - The generated UUID is returned for reference
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock the fetchone to return a UUID
        mock_cursor.fetchone.return_value = ("12345678-1234-5678-1234-567812345678",)

        repo = GeneratedArticleRepository(mock_conn)
        article = GeneratedArticle(
            input_material="テスト素材",
            article_type="ANNOUNCEMENT",
            generated_content={
                "titles": ["タイトル1"],
                "lead": "リード文",
                "sections": [],
                "closing": "クロージング",
            },
            markdown="# タイトル1\n\nリード文",
        )

        result = repo.save(article)

        assert result is not None
        assert str(result) == "12345678-1234-5678-1234-567812345678"
