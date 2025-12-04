"""Tests for the FastAPI REST API."""

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check_returns_ok(self):
        """Test that health check returns OK status."""
        from src.api.main import app

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestGenerateEndpoint:
    """Test article generation endpoint."""

    def test_generate_request_model(self):
        """Test GenerateRequest model validation."""
        from src.api.models import GenerateRequest

        request = GenerateRequest(
            input_material="テーマ: 新入社員の紹介\n名前: 山田太郎",
            article_type=None,
        )

        assert request.input_material == "テーマ: 新入社員の紹介\n名前: 山田太郎"
        assert request.article_type is None

    def test_generate_request_with_article_type(self):
        """Test GenerateRequest with specified article type."""
        from src.api.models import GenerateRequest

        request = GenerateRequest(
            input_material="イベント報告",
            article_type="EVENT_REPORT",
        )

        assert request.article_type == "EVENT_REPORT"

    def test_generate_response_model(self):
        """Test GenerateResponse model."""
        from src.api.models import GenerateResponse

        response = GenerateResponse(
            titles=["タイトル1", "タイトル2", "タイトル3"],
            lead="リード文です。",
            sections=[{"heading": "見出し1", "body": "本文1"}],
            closing="締めの文章です。",
            article_type="INTERVIEW",
            article_type_ja="インタビュー",
            markdown="## タイトル...",
        )

        assert len(response.titles) == 3
        assert response.article_type == "INTERVIEW"


class TestVerifyEndpoint:
    """Test verification endpoint."""

    def test_verify_request_model(self):
        """Test VerifyRequest model."""
        from src.api.models import VerifyRequest

        request = VerifyRequest(
            lead="リード文",
            body="本文",
            closing="締め",
            input_material="テーマ: テスト",
        )

        assert request.lead == "リード文"
        assert request.input_material == "テーマ: テスト"

    def test_verify_response_model(self):
        """Test VerifyResponse model."""
        from src.api.models import VerifyResponse, HallucinationResult, StyleResult

        response = VerifyResponse(
            hallucination=HallucinationResult(
                has_hallucination=False,
                confidence=0.95,
                verified_facts=["事実1"],
                unverified_claims=[],
            ),
            style=StyleResult(
                is_consistent=True,
                consistency_score=0.9,
                issues=[],
            ),
        )

        assert response.hallucination.has_hallucination is False
        assert response.style.is_consistent is True


class TestSearchEndpoint:
    """Test search endpoint."""

    def test_search_request_model(self):
        """Test SearchRequest model."""
        from src.api.models import SearchRequest

        request = SearchRequest(
            query="新入社員 インタビュー",
            article_type="INTERVIEW",
            top_k=5,
        )

        assert request.query == "新入社員 インタビュー"
        assert request.top_k == 5

    def test_search_request_defaults(self):
        """Test SearchRequest default values."""
        from src.api.models import SearchRequest

        request = SearchRequest(query="テスト")

        assert request.article_type is None
        assert request.top_k == 10

    def test_search_result_model(self):
        """Test SearchResult model."""
        from src.api.models import SearchResult

        result = SearchResult(
            id="doc-123",
            title="記事タイトル",
            content="記事の内容...",
            article_type="INTERVIEW",
            score=0.85,
        )

        assert result.id == "doc-123"
        assert result.score == 0.85


class TestAPIModels:
    """Test API model utilities."""

    def test_article_type_enum(self):
        """Test ArticleType enum values."""
        from src.api.models import ArticleType

        assert ArticleType.ANNOUNCEMENT.value == "ANNOUNCEMENT"
        assert ArticleType.EVENT_REPORT.value == "EVENT_REPORT"
        assert ArticleType.INTERVIEW.value == "INTERVIEW"
        assert ArticleType.CULTURE.value == "CULTURE"

    def test_error_response_model(self):
        """Test ErrorResponse model."""
        from src.api.models import ErrorResponse

        error = ErrorResponse(
            error="ValidationError",
            detail="入力が不正です",
        )

        assert error.error == "ValidationError"
        assert error.detail == "入力が不正です"
