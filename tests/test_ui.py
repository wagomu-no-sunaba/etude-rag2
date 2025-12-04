"""Tests for the Streamlit UI components."""

import pytest


class TestUIComponents:
    """Test UI helper components and functions."""

    def test_format_article_type_ja(self):
        """Test Japanese article type formatting."""
        from src.ui.utils import format_article_type_ja

        assert format_article_type_ja("ANNOUNCEMENT") == "お知らせ"
        assert format_article_type_ja("EVENT_REPORT") == "イベントレポート"
        assert format_article_type_ja("INTERVIEW") == "インタビュー"
        assert format_article_type_ja("CULTURE") == "カルチャー"
        assert format_article_type_ja("UNKNOWN") == "UNKNOWN"

    def test_truncate_text(self):
        """Test text truncation utility."""
        from src.ui.utils import truncate_text

        short_text = "短いテキスト"
        assert truncate_text(short_text, max_length=50) == short_text

        long_text = "これは非常に長いテキストで、50文字を超える内容を含んでいます。" * 3
        truncated = truncate_text(long_text, max_length=50)
        assert len(truncated) <= 53  # 50 + "..."
        assert truncated.endswith("...")

    def test_parse_sections_to_body(self):
        """Test converting sections to body text."""
        from src.ui.utils import parse_sections_to_body

        sections = [
            {"heading": "はじめに", "body": "導入文です。"},
            {"heading": "本題", "body": "本題の内容です。"},
        ]

        body = parse_sections_to_body(sections)

        assert "はじめに" in body
        assert "導入文です。" in body
        assert "本題" in body

    def test_create_download_markdown(self):
        """Test markdown file creation for download."""
        from src.ui.utils import create_download_markdown

        data = {
            "titles": ["タイトル1", "タイトル2", "タイトル3"],
            "lead": "リード文",
            "sections": [{"heading": "見出し", "body": "本文"}],
            "closing": "締め",
            "article_type_ja": "インタビュー",
        }

        markdown = create_download_markdown(data)

        assert "# タイトル案" in markdown
        assert "タイトル1" in markdown
        assert "リード文" in markdown
        assert "見出し" in markdown
        assert "締め" in markdown


class TestUIState:
    """Test UI state management."""

    def test_generation_state_model(self):
        """Test GenerationState model."""
        from src.ui.state import GenerationState

        state = GenerationState()

        assert state.input_material == ""
        assert state.selected_article_type is None
        assert state.generated_draft is None
        assert state.is_generating is False

    def test_generation_state_with_data(self):
        """Test GenerationState with data."""
        from src.ui.state import GenerationState

        state = GenerationState(
            input_material="テスト素材",
            selected_article_type="INTERVIEW",
            is_generating=True,
        )

        assert state.input_material == "テスト素材"
        assert state.selected_article_type == "INTERVIEW"
        assert state.is_generating is True

    def test_verification_state_model(self):
        """Test VerificationState model."""
        from src.ui.state import VerificationState

        state = VerificationState()

        assert state.hallucination_result is None
        assert state.style_result is None
        assert state.is_verifying is False


class TestAPIClient:
    """Test UI API client."""

    def test_api_client_initialization(self):
        """Test APIClient initialization."""
        from src.ui.api_client import APIClient

        client = APIClient(base_url="http://localhost:8000")

        assert client.base_url == "http://localhost:8000"

    def test_api_client_default_url(self):
        """Test APIClient default URL."""
        from src.ui.api_client import APIClient

        client = APIClient()

        assert "localhost" in client.base_url or "127.0.0.1" in client.base_url
