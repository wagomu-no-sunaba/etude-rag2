"""BGE Cross-Encoder Reranker for relevance re-scoring."""

import logging
import math
from collections.abc import Sequence

from langchain_core.documents import Document

from src.config import settings

logger = logging.getLogger(__name__)


class BGEReranker:
    """Cross-encoder reranker using BGE (BAAI General Embedding) models.

    This reranker uses a cross-encoder architecture to score query-document pairs
    directly, providing more accurate relevance scoring than bi-encoder approaches.
    """

    def __init__(
        self,
        model_name: str | None = None,
        use_fp16: bool | None = None,
    ):
        """Initialize the BGE reranker.

        Args:
            model_name: HuggingFace model name (default: BAAI/bge-reranker-base).
            use_fp16: Use FP16 precision for faster inference (default: True).
        """
        model_name = model_name or settings.reranker_model
        use_fp16 = use_fp16 if use_fp16 is not None else settings.use_fp16

        try:
            from FlagEmbedding import FlagReranker

            self.reranker = FlagReranker(model_name, use_fp16=use_fp16)
            logger.info(f"Initialized BGE reranker with model: {model_name}")
        except ImportError as e:
            logger.error("FlagEmbedding not installed. Run: pip install FlagEmbedding")
            raise ImportError(
                "FlagEmbedding is required for BGE reranker. "
                "Install it with: pip install FlagEmbedding"
            ) from e

    def rerank(
        self,
        query: str,
        documents: Sequence[Document],
        top_k: int | None = None,
    ) -> list[Document]:
        """Rerank documents based on query relevance.

        Args:
            query: The search query.
            documents: List of documents to rerank.
            top_k: Number of top documents to return (default from settings).

        Returns:
            List of documents sorted by relevance score, limited to top_k.
        """
        top_k = top_k or settings.reranker_top_k

        if not documents:
            return []

        # Create query-document pairs for cross-encoder
        pairs = [[query, doc.page_content] for doc in documents]

        # Compute relevance scores
        scores = self.reranker.compute_score(pairs)

        # Handle single document case (returns float instead of list)
        if not isinstance(scores, list):
            scores = [scores]

        # Apply sigmoid normalization for interpretable 0-1 scores
        normalized_scores = [self._sigmoid(s) for s in scores]

        # Pair scores with documents and sort by score descending
        scored_docs = sorted(
            zip(scores, normalized_scores, documents, strict=True),
            key=lambda x: x[0],
            reverse=True,
        )

        # Build result with scores in metadata
        result = []
        for rank, (raw_score, norm_score, doc) in enumerate(scored_docs[:top_k]):
            # Create a copy to avoid mutating original document
            new_metadata = {
                **doc.metadata,
                "rerank_score": float(raw_score),
                "rerank_score_normalized": float(norm_score),
                "rerank_position": rank + 1,
            }
            result.append(
                Document(
                    page_content=doc.page_content,
                    metadata=new_metadata,
                )
            )

        return result

    def compute_scores(
        self,
        query: str,
        documents: Sequence[Document],
    ) -> list[tuple[Document, float, float]]:
        """Compute reranking scores without filtering.

        Args:
            query: The search query.
            documents: List of documents to score.

        Returns:
            List of tuples (document, raw_score, normalized_score).
        """
        if not documents:
            return []

        pairs = [[query, doc.page_content] for doc in documents]
        scores = self.reranker.compute_score(pairs)

        if not isinstance(scores, list):
            scores = [scores]

        return [
            (doc, float(score), self._sigmoid(score))
            for doc, score in zip(documents, scores, strict=True)
        ]

    @staticmethod
    def _sigmoid(x: float) -> float:
        """Apply sigmoid function for normalization.

        Maps any real number to (0, 1) range.
        """
        return 1 / (1 + math.exp(-x))


def get_reranker() -> BGEReranker | None:
    """Get a reranker instance with graceful degradation.

    Returns:
        BGEReranker instance if initialization succeeds, None otherwise.
        This allows the system to fall back to non-reranked results.
    """
    try:
        return BGEReranker()
    except Exception as e:
        logger.warning(f"Reranker initialization failed: {e}. Continuing without reranking.")
        return None


class NoOpReranker:
    """No-op reranker that returns documents unchanged.

    Used as a fallback when BGE reranker is not available.
    """

    def rerank(
        self,
        query: str,
        documents: Sequence[Document],
        top_k: int | None = None,
    ) -> list[Document]:
        """Return documents without reranking, just limited to top_k."""
        top_k = top_k or settings.reranker_top_k
        return list(documents[:top_k])

    def compute_scores(
        self,
        query: str,
        documents: Sequence[Document],
    ) -> list[tuple[Document, float, float]]:
        """Return documents with default scores."""
        return [(doc, 0.0, 0.5) for doc in documents]
