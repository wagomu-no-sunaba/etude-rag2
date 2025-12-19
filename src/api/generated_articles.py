"""Repository for managing generated articles in the database."""

import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class GeneratedArticle(BaseModel):
    """Model for a generated article to be saved."""

    input_material: str
    article_type: str
    generated_content: dict[str, Any]
    markdown: str


class GeneratedArticleRepository:
    """Repository for CRUD operations on generated articles."""

    def __init__(self, connection: Any) -> None:
        """Initialize repository with database connection."""
        self._conn = connection

    def save(self, article: GeneratedArticle) -> UUID:
        """Save a generated article and return its UUID."""
        with self._conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO generated_articles
                    (input_material, article_type, generated_content, markdown)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (
                    article.input_material,
                    article.article_type,
                    json.dumps(article.generated_content),
                    article.markdown,
                ),
            )
            result = cursor.fetchone()
            self._conn.commit()
            return UUID(result[0])
