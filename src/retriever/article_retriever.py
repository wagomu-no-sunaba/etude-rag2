"""Article-type aware retriever combining hybrid search and reranking."""

import logging
from collections.abc import Sequence
from enum import Enum

from langchain_core.documents import Document

from src.config import settings
from src.retriever.hybrid_search import HybridSearcher
from src.retriever.reranker import BGEReranker, NoOpReranker, get_reranker

logger = logging.getLogger(__name__)


class ArticleType(str, Enum):
    """Supported article types for filtering."""

    ANNOUNCEMENT = "ANNOUNCEMENT"
    EVENT_REPORT = "EVENT_REPORT"
    INTERVIEW = "INTERVIEW"
    CULTURE = "CULTURE"


class ArticleRetriever:
    """High-level retriever for article search with reranking support.

    This class provides:
    - Article type-specific search
    - Hybrid search (vector + full-text + RRF)
    - Optional BGE cross-encoder reranking
    - Multi-query search with deduplication
    """

    def __init__(
        self,
        searcher: HybridSearcher | None = None,
        reranker: BGEReranker | NoOpReranker | None = None,
    ):
        """Initialize the article retriever.

        Args:
            searcher: HybridSearcher instance (creates one if None).
            reranker: Reranker instance (uses get_reranker() if None).
        """
        self.searcher = searcher or HybridSearcher()

        # Try to initialize reranker, fall back to NoOp if unavailable
        if reranker is not None:
            self.reranker = reranker
        else:
            actual_reranker = get_reranker()
            self.reranker = actual_reranker if actual_reranker else NoOpReranker()

        self._reranker_available = not isinstance(self.reranker, NoOpReranker)

    @property
    def has_reranker(self) -> bool:
        """Check if BGE reranker is available."""
        return self._reranker_available

    def retrieve(
        self,
        query: str,
        article_type: str | ArticleType | None = None,
        use_reranker: bool = True,
        search_k: int | None = None,
        rerank_top_k: int | None = None,
    ) -> list[Document]:
        """Retrieve documents matching the query.

        Args:
            query: Search query string.
            article_type: Filter by article type (optional).
            use_reranker: Whether to apply reranking (default: True).
            search_k: Number of results from initial search.
            rerank_top_k: Number of results after reranking.

        Returns:
            List of relevant documents sorted by relevance.
        """
        # Convert ArticleType enum to string if needed
        type_str = article_type.value if isinstance(article_type, ArticleType) else article_type

        # Perform hybrid search
        documents = self.searcher.search(
            query=query,
            article_type=type_str,
            final_k=search_k or settings.final_k,
        )

        if not documents:
            logger.debug(f"No documents found for query: {query[:50]}...")
            return []

        # Apply reranking if requested and available
        if use_reranker and self._reranker_available:
            documents = self.reranker.rerank(
                query=query,
                documents=documents,
                top_k=rerank_top_k or settings.reranker_top_k,
            )

        return documents

    def retrieve_by_type(
        self,
        query: str,
        article_type: ArticleType,
        top_k: int | None = None,
    ) -> list[Document]:
        """Retrieve documents of a specific article type.

        Convenience method for type-specific retrieval.

        Args:
            query: Search query string.
            article_type: Article type to filter by.
            top_k: Number of results to return.

        Returns:
            List of relevant documents of the specified type.
        """
        return self.retrieve(
            query=query,
            article_type=article_type,
            use_reranker=True,
            rerank_top_k=top_k,
        )

    def retrieve_multi_query(
        self,
        queries: Sequence[str],
        article_type: str | ArticleType | None = None,
        final_top_k: int | None = None,
    ) -> list[Document]:
        """Retrieve documents using multiple queries with deduplication.

        Useful for query expansion where multiple reformulations of the
        original query are used to improve recall.

        Args:
            queries: List of query strings.
            article_type: Filter by article type (optional).
            final_top_k: Number of final results after merging and reranking.

        Returns:
            List of relevant documents, deduplicated and reranked.
        """
        if not queries:
            return []

        # Convert ArticleType enum to string if needed
        type_str = article_type.value if isinstance(article_type, ArticleType) else article_type

        # Collect results from all queries
        all_docs: list[Document] = []
        seen_ids: set[int] = set()

        for query in queries:
            docs = self.searcher.search(
                query=query,
                article_type=type_str,
            )
            for doc in docs:
                doc_id = doc.metadata.get("id")
                if doc_id is not None and doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    all_docs.append(doc)

        if not all_docs:
            return []

        # Rerank using the first query as representative
        if self._reranker_available:
            all_docs = self.reranker.rerank(
                query=queries[0],
                documents=all_docs,
                top_k=final_top_k or settings.reranker_top_k,
            )

        return all_docs

    def retrieve_all_types(
        self,
        query: str,
        top_k_per_type: int = 3,
    ) -> dict[ArticleType, list[Document]]:
        """Retrieve documents from all article types.

        Useful for exploring which types of content are relevant.

        Args:
            query: Search query string.
            top_k_per_type: Number of results per article type.

        Returns:
            Dict mapping article types to their relevant documents.
        """
        results = {}
        for article_type in ArticleType:
            docs = self.retrieve(
                query=query,
                article_type=article_type,
                rerank_top_k=top_k_per_type,
            )
            results[article_type] = docs
        return results

    def close(self):
        """Close underlying resources."""
        self.searcher.close()
