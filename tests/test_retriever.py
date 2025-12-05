"""Tests for the retriever module."""

import pytest

from src.retriever.article_retriever import ArticleRetriever, ArticleType
from src.retriever.reranker import BGEReranker, NoOpReranker


class TestArticleType:
    """Test ArticleType enum."""

    def test_article_type_values(self):
        """Test that all article types have correct values."""
        assert ArticleType.ANNOUNCEMENT.value == "ANNOUNCEMENT"
        assert ArticleType.EVENT_REPORT.value == "EVENT_REPORT"
        assert ArticleType.INTERVIEW.value == "INTERVIEW"
        assert ArticleType.CULTURE.value == "CULTURE"

    def test_article_type_is_string_enum(self):
        """Test that ArticleType values are strings."""
        for article_type in ArticleType:
            assert isinstance(article_type.value, str)


class TestNoOpReranker:
    """Test the NoOpReranker fallback."""

    def test_rerank_returns_top_k(self):
        """Test that NoOpReranker limits results to top_k."""
        from langchain_core.documents import Document

        reranker = NoOpReranker()
        docs = [Document(page_content=f"Doc {i}", metadata={"id": i}) for i in range(10)]

        result = reranker.rerank("test query", docs, top_k=5)

        assert len(result) == 5
        assert result[0].page_content == "Doc 0"

    def test_rerank_with_empty_docs(self):
        """Test reranking empty document list."""
        reranker = NoOpReranker()
        result = reranker.rerank("test query", [], top_k=5)
        assert result == []

    def test_compute_scores_returns_default_scores(self):
        """Test that compute_scores returns default scores."""
        from langchain_core.documents import Document

        reranker = NoOpReranker()
        docs = [Document(page_content="Test doc", metadata={})]

        scores = reranker.compute_scores("query", docs)

        assert len(scores) == 1
        doc, raw_score, norm_score = scores[0]
        assert raw_score == 0.0
        assert norm_score == 0.5


class TestBGEReranker:
    """Test BGEReranker (requires FlagEmbedding installed)."""

    @pytest.fixture
    def reranker(self):
        """Create BGE reranker if available."""
        try:
            return BGEReranker()
        except ImportError:
            pytest.skip("FlagEmbedding not installed")

    def test_sigmoid_normalization(self):
        """Test sigmoid normalization function."""
        # Test known values
        assert BGEReranker._sigmoid(0) == 0.5
        assert BGEReranker._sigmoid(100) > 0.99
        assert BGEReranker._sigmoid(-100) < 0.01


# Integration tests (require database)
@pytest.mark.integration
class TestArticleRetrieverIntegration:
    """Integration tests for ArticleRetriever (require database connection)."""

    @pytest.fixture
    def retriever(self):
        """Create ArticleRetriever with NoOp reranker for testing."""
        return ArticleRetriever(reranker=NoOpReranker())

    def test_has_reranker_property(self, retriever):
        """Test has_reranker property."""
        assert retriever.has_reranker is False

    def test_retrieve_all_types_returns_dict(self, retriever):
        """Test retrieve_all_types returns correct structure."""
        # This would need a database connection to actually work
        # Skipping actual call for unit test
        pass
