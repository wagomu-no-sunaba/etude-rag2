"""Integration tests for full HTMX form submission flow."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestFullFormSubmissionFlow:
    """Test complete form submission flow with HTMX."""

    def test_form_submission_returns_partial(self):
        """Submitting form updates result container without page reload."""
        from src.api.main import app

        client = TestClient(app)

        # First, load the main page to verify form structure
        index_response = client.get("/")
        assert index_response.status_code == 200
        index_html = index_response.text

        # Verify HTMX attributes are present
        assert "hx-post=" in index_html
        assert "hx-target=" in index_html
        assert 'id="result"' in index_html

        # Mock the pipeline
        mock_draft = MagicMock()
        mock_draft.titles = ["統合テストタイトル1", "統合テストタイトル2"]
        mock_draft.lead = "これは統合テストのリード文です。"
        mock_draft.sections = [
            {"heading": "第1章", "body": "第1章の内容"},
            {"heading": "第2章", "body": "第2章の内容"},
        ]
        mock_draft.closing = "統合テストの締めくくり。"
        mock_draft.article_type = "ANNOUNCEMENT"
        mock_draft.article_type_ja = "お知らせ"
        mock_draft.to_markdown.return_value = "# 統合テスト\n\n本文"

        with patch("src.api.main.pipeline") as mock_pipeline:
            mock_pipeline.generate.return_value = mock_draft

            # Submit form (simulating HTMX POST)
            generate_response = client.post(
                "/ui/generate",
                data={
                    "input_material": "統合テスト用の素材テキスト",
                    "article_type": "ANNOUNCEMENT",
                },
            )

        # Verify response
        assert generate_response.status_code == 200

        result_html = generate_response.text

        # Should be a partial (no DOCTYPE)
        assert "<!DOCTYPE" not in result_html

        # Should contain generated content
        assert "統合テストタイトル1" in result_html
        assert "これは統合テストのリード文です" in result_html
        assert "第1章" in result_html
        assert "統合テストの締めくくり" in result_html

    def test_form_with_auto_detect_article_type(self):
        """Form submission with empty article_type triggers auto-detection."""
        from src.api.main import app

        client = TestClient(app)

        mock_draft = MagicMock()
        mock_draft.titles = ["自動判定タイトル"]
        mock_draft.lead = "自動判定リード"
        mock_draft.sections = []
        mock_draft.closing = "締め"
        mock_draft.article_type = "INTERVIEW"
        mock_draft.article_type_ja = "インタビュー"
        mock_draft.to_markdown.return_value = "# 自動判定"

        with patch("src.api.main.pipeline") as mock_pipeline:
            mock_pipeline.generate.return_value = mock_draft

            response = client.post(
                "/ui/generate",
                data={
                    "input_material": "インタビュー形式のテキスト",
                    "article_type": "",  # Empty = auto-detect
                },
            )

        assert response.status_code == 200
        assert "インタビュー" in response.text

    def test_end_to_end_form_elements(self):
        """Verify all form elements are properly connected."""
        from src.api.main import app

        client = TestClient(app)

        # Get the index page
        response = client.get("/")
        html = response.text

        # Form should post to /ui/generate/stream for SSE streaming
        assert 'hx-post="/ui/generate/stream"' in html

        # Form should target #result
        assert 'hx-target="#result"' in html

        # Form should swap innerHTML
        assert 'hx-swap="innerHTML"' in html

        # Result container should exist
        assert '<div id="result"' in html

        # Form elements should have correct names
        assert 'name="article_type"' in html
        assert 'name="input_material"' in html
