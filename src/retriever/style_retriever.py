"""Style profile retriever for category-specific writing style guidelines.

Retrieves style profiles and excerpts from the style_profiles table
for guiding article generation with consistent writing style.
"""

import logging

import psycopg2
from langchain_core.documents import Document
from langchain_google_vertexai import VertexAIEmbeddings

from src.config import settings
from src.retriever.article_retriever import ArticleType
from src.retriever.reranker import BGEReranker, NoOpReranker, get_reranker

logger = logging.getLogger(__name__)


class StyleProfileRetriever:
    """Retrieves style profiles and excerpts for article categories.

    Corresponds to Dify v3: STYLE_PROFILE + STYLE_EXCERPTS knowledge bases.

    This retriever provides two types of content:
    1. Style profiles: Writing style rules and guidelines for each article category
    2. Style excerpts: Sample text excerpts demonstrating the target writing style
    """

    def __init__(
        self,
        embeddings: VertexAIEmbeddings | None = None,
        reranker: BGEReranker | NoOpReranker | None = None,
    ):
        """Initialize the style profile retriever.

        Args:
            embeddings: VertexAI embeddings instance for excerpt similarity search.
            reranker: Optional reranker for improving excerpt relevance.
        """
        self.embeddings = embeddings or VertexAIEmbeddings(
            model=settings.embedding_model,
            project=settings.google_project_id,
            location=settings.google_location,
        )
        self.conn_string = settings.db_connection_string

        # Initialize reranker with graceful fallback
        if reranker is not None:
            self.reranker = reranker
        else:
            actual_reranker = get_reranker()
            self.reranker = actual_reranker if actual_reranker else NoOpReranker()

        self._reranker_available = not isinstance(self.reranker, NoOpReranker)

    def retrieve_profile(self, article_type: ArticleType) -> str | None:
        """Retrieve the style profile (writing rules) for an article category.

        Corresponds to Dify v3: node_style_profile_* (top_k=1)

        Args:
            article_type: Article category (ArticleType enum).

        Returns:
            Style profile content as string, or None if not found.
        """
        conn = None
        try:
            conn = psycopg2.connect(self.conn_string)
            cur = conn.cursor()

            cur.execute(
                """
                SELECT content FROM style_profiles
                WHERE article_type = %s AND profile_type = 'profile'
                LIMIT 1
                """,
                (article_type.value,),
            )

            result = cur.fetchone()
            cur.close()

            if result:
                logger.debug(f"Retrieved style profile for {article_type.value}")
                return result[0]

            logger.warning(f"No style profile found for {article_type.value}")
            return None

        except Exception as e:
            logger.error(f"Error retrieving style profile: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def retrieve_excerpts(
        self,
        theme: str,
        article_type: ArticleType,
        top_k: int = 5,
    ) -> list[str]:
        """Retrieve style excerpts similar to the given theme.

        Corresponds to Dify v3: node_style_excerpts_* (top_k=5)

        Uses vector similarity search to find excerpts that best match
        the theme, then optionally applies reranking for better relevance.

        Args:
            theme: Theme/topic to search for similar excerpts.
            article_type: Article category to filter excerpts.
            top_k: Number of excerpts to return.

        Returns:
            List of excerpt content strings.
        """
        conn = None
        try:
            # Generate embedding for the theme
            query_embedding = self.embeddings.embed_query(theme)

            conn = psycopg2.connect(self.conn_string)
            cur = conn.cursor()

            # Vector similarity search on excerpts only
            cur.execute(
                """
                SELECT content, 1 - (embedding <=> %s::vector) as similarity
                FROM style_profiles
                WHERE article_type = %s AND profile_type = 'excerpt'
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (query_embedding, article_type.value, query_embedding, top_k * 2),
            )

            results = cur.fetchall()
            cur.close()

            if not results:
                logger.debug(f"No style excerpts found for {article_type.value}")
                return []

            # Apply reranking if available
            if self._reranker_available and len(results) > 1:
                documents = [
                    Document(page_content=content, metadata={"similarity": sim})
                    for content, sim in results
                ]
                reranked = self.reranker.rerank(theme, documents, top_k=top_k)
                return [doc.page_content for doc in reranked]

            # Return top_k without reranking
            return [content for content, _ in results[:top_k]]

        except Exception as e:
            logger.error(f"Error retrieving style excerpts: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def retrieve_all(
        self,
        theme: str,
        article_type: ArticleType,
        excerpt_top_k: int = 5,
    ) -> tuple[str | None, list[str]]:
        """Retrieve both style profile and excerpts in one call.

        Convenience method for retrieving all style-related content.

        Args:
            theme: Theme/topic for excerpt similarity search.
            article_type: Article category.
            excerpt_top_k: Number of excerpts to return.

        Returns:
            Tuple of (style_profile, list_of_excerpts).
        """
        profile = self.retrieve_profile(article_type)
        excerpts = self.retrieve_excerpts(theme, article_type, top_k=excerpt_top_k)
        return profile, excerpts

    async def aretrieve_profile(self, article_type: ArticleType) -> str | None:
        """Async version of retrieve_profile.

        Note: Currently uses sync psycopg2, but provides async interface
        for compatibility with async pipelines.
        """
        # TODO: Use asyncpg for true async support
        return self.retrieve_profile(article_type)

    async def aretrieve_excerpts(
        self,
        theme: str,
        article_type: ArticleType,
        top_k: int = 5,
    ) -> list[str]:
        """Async version of retrieve_excerpts.

        Note: Currently uses sync psycopg2, but provides async interface
        for compatibility with async pipelines.
        """
        # TODO: Use asyncpg for true async support
        return self.retrieve_excerpts(theme, article_type, top_k)
