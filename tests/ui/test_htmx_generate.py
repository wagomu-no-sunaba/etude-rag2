"""Tests for /ui/generate endpoint."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestUIGenerateEndpoint:
    """Test /ui/generate endpoint for HTMX partial updates."""

    def test_generate_returns_html_partial(self):
        """POST /ui/generate returns HTML partial with article sections."""
        from src.api.main import app

        client = TestClient(app)

        # Mock the pipeline to avoid actual generation
        mock_draft = MagicMock()
        mock_draft.titles = ["タイトル案1", "タイトル案2", "タイトル案3"]
        mock_draft.lead = "リード文です。"
        mock_draft.sections = [{"heading": "見出し1", "body": "本文1"}]
        mock_draft.closing = "締めの文章です。"
        mock_draft.article_type = "ANNOUNCEMENT"
        mock_draft.article_type_ja = "お知らせ"
        mock_draft.to_markdown.return_value = "# タイトル\n\n本文"

        with patch("src.api.main.pipeline") as mock_pipeline:
            mock_pipeline.generate.return_value = mock_draft

            response = client.post(
                "/ui/generate",
                data={"input_material": "テスト素材", "article_type": ""},
            )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

        html = response.text
        # Check result sections exist
        assert "タイトル案" in html or "タイトル" in html
        assert "リード" in html or mock_draft.lead in html

    def test_generate_with_article_type(self):
        """POST /ui/generate with specified article type."""
        from src.api.main import app

        client = TestClient(app)

        mock_draft = MagicMock()
        mock_draft.titles = ["インタビュー記事タイトル"]
        mock_draft.lead = "インタビューのリード文"
        mock_draft.sections = []
        mock_draft.closing = "締め"
        mock_draft.article_type = "INTERVIEW"
        mock_draft.article_type_ja = "インタビュー"
        mock_draft.to_markdown.return_value = "# インタビュー"

        with patch("src.api.main.pipeline") as mock_pipeline:
            mock_pipeline.generate.return_value = mock_draft

            response = client.post(
                "/ui/generate",
                data={"input_material": "テスト", "article_type": "INTERVIEW"},
            )

        assert response.status_code == 200


class TestPartialUpdateResult:
    """Test that result partial works with HTMX."""

    def test_partial_update_result(self):
        """Generation result displays in result container without full page reload."""
        from src.api.main import app

        client = TestClient(app)

        mock_draft = MagicMock()
        mock_draft.titles = ["テストタイトル"]
        mock_draft.lead = "テストリード"
        mock_draft.sections = [{"heading": "セクション", "body": "内容"}]
        mock_draft.closing = "テスト締め"
        mock_draft.article_type = "CULTURE"
        mock_draft.article_type_ja = "カルチャー"
        mock_draft.to_markdown.return_value = "# テスト"

        with patch("src.api.main.pipeline") as mock_pipeline:
            mock_pipeline.generate.return_value = mock_draft

            response = client.post(
                "/ui/generate",
                data={"input_material": "テスト素材"},
            )

        assert response.status_code == 200
        html = response.text

        # Should be a partial, not a full HTML page
        assert "<!DOCTYPE" not in html
        # Should contain result content
        assert "テストタイトル" in html or "result" in html.lower()
