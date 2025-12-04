"""Hybrid search combining vector similarity and full-text search with RRF fusion."""

import json
import logging
from contextlib import contextmanager
from typing import Any

import psycopg2
from langchain_core.documents import Document
from langchain_google_vertexai import VertexAIEmbeddings
from psycopg2.extras import RealDictCursor

from src.config import settings

logger = logging.getLogger(__name__)


class HybridSearcher:
    """Hybrid searcher combining vector search and full-text search with RRF fusion.

    This class performs:
    1. Vector similarity search using pgvector
    2. Full-text search using pg_trgm trigram similarity
    3. Reciprocal Rank Fusion (RRF) to combine results
    """

    def __init__(
        self,
        embeddings: VertexAIEmbeddings | None = None,
        connection_string: str | None = None,
    ):
        """Initialize the hybrid searcher.

        Args:
            embeddings: Optional VertexAIEmbeddings instance. If None, creates one.
            connection_string: Optional database connection string.
        """
        self.embeddings = embeddings or VertexAIEmbeddings(
            model_name=settings.embedding_model,
            project=settings.google_project_id,
            location=settings.google_location,
        )
        self._connection_string = connection_string or settings.db_connection_string
        self._conn: psycopg2.extensions.connection | None = None

    @contextmanager
    def _get_connection(self):
        """Get database connection with automatic reconnection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self._connection_string)
        try:
            yield self._conn
        except psycopg2.OperationalError:
            # Reconnect on connection errors
            self._conn = psycopg2.connect(self._connection_string)
            yield self._conn

    def search(
        self,
        query: str,
        article_type: str | None = None,
        k: int | None = None,
        rrf_k: int | None = None,
        final_k: int | None = None,
    ) -> list[Document]:
        """Perform hybrid search combining vector and full-text search.

        Args:
            query: Search query string.
            article_type: Filter by article type (ANNOUNCEMENT, EVENT_REPORT, etc.)
            k: Number of results from each search method.
            rrf_k: RRF fusion parameter (higher = less rank difference impact).
            final_k: Final number of results after fusion.

        Returns:
            List of Document objects sorted by combined RRF score.
        """
        k = k or settings.hybrid_search_k
        rrf_k = rrf_k or settings.rrf_k
        final_k = final_k or settings.final_k

        # Generate query embedding
        try:
            query_vector = self.embeddings.embed_query(query)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise

        # Hybrid search SQL with RRF fusion
        sql = """
        WITH vector_search AS (
            SELECT
                id,
                content,
                metadata,
                article_type::text,
                source_file,
                chunk_index,
                total_chunks,
                ROW_NUMBER() OVER (ORDER BY embedding <-> %s::vector) as rank
            FROM documents
            WHERE (%s IS NULL OR article_type = %s::article_type)
            ORDER BY embedding <-> %s::vector
            LIMIT %s
        ),
        fulltext_search AS (
            SELECT
                id,
                content,
                metadata,
                article_type::text,
                source_file,
                chunk_index,
                total_chunks,
                ROW_NUMBER() OVER (ORDER BY similarity(content, %s) DESC) as rank
            FROM documents
            WHERE (%s IS NULL OR article_type = %s::article_type)
              AND similarity(content, %s) > 0.1
            ORDER BY similarity(content, %s) DESC
            LIMIT %s
        ),
        combined AS (
            SELECT
                id, content, metadata, article_type, source_file,
                chunk_index, total_chunks,
                rrf_score(rank, %s) as score,
                'vector' as search_source
            FROM vector_search
            UNION ALL
            SELECT
                id, content, metadata, article_type, source_file,
                chunk_index, total_chunks,
                rrf_score(rank, %s) as score,
                'fulltext' as search_source
            FROM fulltext_search
        )
        SELECT
            id,
            content,
            metadata,
            article_type,
            source_file,
            chunk_index,
            total_chunks,
            SUM(score) as total_score,
            array_agg(DISTINCT search_source) as matched_sources
        FROM combined
        GROUP BY id, content, metadata, article_type, source_file, chunk_index, total_chunks
        ORDER BY total_score DESC
        LIMIT %s
        """

        params = (
            # vector_search params
            query_vector,
            article_type,
            article_type,
            query_vector,
            k,
            # fulltext_search params
            query,
            article_type,
            article_type,
            query,
            query,
            k,
            # RRF params
            rrf_k,
            rrf_k,
            # final limit
            final_k,
        )

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                results = cur.fetchall()

        return self._to_documents(results)

    def vector_search_only(
        self,
        query: str,
        article_type: str | None = None,
        k: int | None = None,
    ) -> list[Document]:
        """Perform vector similarity search only (no full-text).

        Args:
            query: Search query string.
            article_type: Filter by article type.
            k: Number of results.

        Returns:
            List of Document objects sorted by vector similarity.
        """
        k = k or settings.final_k
        query_vector = self.embeddings.embed_query(query)

        sql = """
        SELECT
            id,
            content,
            metadata,
            article_type::text,
            source_file,
            chunk_index,
            total_chunks,
            1 - (embedding <-> %s::vector) as similarity_score
        FROM documents
        WHERE (%s IS NULL OR article_type = %s::article_type)
        ORDER BY embedding <-> %s::vector
        LIMIT %s
        """

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (query_vector, article_type, article_type, query_vector, k))
                results = cur.fetchall()

        return self._to_documents(results, score_key="similarity_score")

    def fulltext_search_only(
        self,
        query: str,
        article_type: str | None = None,
        k: int | None = None,
        threshold: float = 0.1,
    ) -> list[Document]:
        """Perform full-text search only using pg_trgm.

        Args:
            query: Search query string.
            article_type: Filter by article type.
            k: Number of results.
            threshold: Minimum similarity threshold.

        Returns:
            List of Document objects sorted by trigram similarity.
        """
        k = k or settings.final_k

        sql = """
        SELECT
            id,
            content,
            metadata,
            article_type::text,
            source_file,
            chunk_index,
            total_chunks,
            similarity(content, %s) as similarity_score
        FROM documents
        WHERE (%s IS NULL OR article_type = %s::article_type)
          AND similarity(content, %s) > %s
        ORDER BY similarity(content, %s) DESC
        LIMIT %s
        """

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    sql, (query, article_type, article_type, query, threshold, query, k)
                )
                results = cur.fetchall()

        return self._to_documents(results, score_key="similarity_score")

    def _to_documents(
        self,
        results: list[dict[str, Any]],
        score_key: str = "total_score",
    ) -> list[Document]:
        """Convert database results to Document objects.

        Args:
            results: List of database row dicts.
            score_key: Key for the score value in results.

        Returns:
            List of Document objects with metadata.
        """
        documents = []
        for row in results:
            # Parse metadata JSON if it's a string
            metadata = row.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    metadata = {}

            # Build comprehensive metadata
            doc_metadata = {
                **metadata,
                "id": row["id"],
                "article_type": row.get("article_type"),
                "source_file": row.get("source_file"),
                "chunk_index": row.get("chunk_index"),
                "total_chunks": row.get("total_chunks"),
            }

            # Add score if present
            if score_key in row and row[score_key] is not None:
                doc_metadata["score"] = float(row[score_key])

            # Add matched sources if present (for hybrid search)
            if "matched_sources" in row:
                doc_metadata["matched_sources"] = row["matched_sources"]

            documents.append(
                Document(
                    page_content=row["content"],
                    metadata=doc_metadata,
                )
            )

        return documents

    def close(self):
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def __del__(self):
        """Cleanup on deletion."""
        self.close()
