"""Configuration management using Pydantic Settings.

Priority order:
1. Environment variables (highest priority, for Cloud Run)
2. Google Cloud Secret Manager (for secrets like DB_PASSWORD)
3. .env file (for local development fallback)

This approach eliminates .env/tfvars duplication by using Secret Manager
as the single source of truth.
"""

import os
from functools import lru_cache
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_secret_value(key: str) -> str | None:
    """Lazy import to avoid circular dependency."""
    # Only try Secret Manager if we have a project ID
    project_id = os.environ.get("GOOGLE_PROJECT_ID")
    if not project_id:
        return None

    try:
        from src.secret_manager import get_app_secret

        return get_app_secret(key)
    except Exception:
        return None


class Settings(BaseSettings):
    """Application settings with Secret Manager integration.

    Configuration is loaded from:
    1. Environment variables (highest priority)
    2. Secret Manager (for sensitive values)
    3. .env file (local development fallback)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Google Cloud
    google_project_id: str
    google_location: str = "us-central1"
    environment: str = "dev"
    service_account_file: str | None = None

    # Vertex AI
    embedding_model: str = "text-embedding-004"
    llm_model: str = "gemini-2.0-flash"
    llm_model_lite: str = "gemini-2.0-flash-lite"
    llm_temperature: float = 0.3

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "rag_db"
    db_user: str = "postgres"
    db_password: str = ""

    # Hybrid Search Parameters
    hybrid_search_k: int = 20  # Number of results from each search method
    rrf_k: int = 50  # RRF fusion parameter (higher = less rank difference impact)
    final_k: int = 10  # Final number of results after fusion

    # Reranker
    reranker_model: str = "BAAI/bge-reranker-v2-m3"  # Upgraded for better multilingual support
    reranker_top_k: int = 5  # Number of results after reranking
    use_fp16: bool = True  # Use FP16 for reranker inference

    # Feature flags (for gradual rollout and rollback)
    use_lite_model: bool = True  # Use flash-lite for lightweight tasks
    use_query_generator: bool = True  # Enable query generation chain
    use_style_profile_kb: bool = True  # Enable style profile knowledge base
    use_auto_rewrite: bool = True  # Enable automatic rewriting

    # Google Drive
    target_folder_id: str | None = None

    # Email for ACL filtering
    my_email: str | None = None

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200

    @model_validator(mode="before")
    @classmethod
    def load_secrets_from_secret_manager(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Load secret values from Secret Manager if not already set.

        This allows Secret Manager to be the single source of truth while
        still allowing environment variables to override.
        """
        secret_fields = ["db_password", "target_folder_id", "my_email"]

        for field in secret_fields:
            # Skip if already set via env var or .env
            if data.get(field):
                continue

            # Try to load from Secret Manager
            value = _get_secret_value(field)
            if value:
                data[field] = value

        return data

    @property
    def db_connection_string(self) -> str:
        """PostgreSQL connection string (supports Unix socket for Cloud SQL)."""
        if self.db_host.startswith("/"):
            # Unix socket connection for Cloud SQL
            return (
                f"postgresql://{self.db_user}:{self.db_password}"
                f"@/{self.db_name}?host={self.db_host}"
            )
        # TCP connection
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def db_connection_string_psycopg(self) -> str:
        """Connection string with psycopg driver for LangChain PGVector."""
        base = self.db_connection_string
        return base.replace("postgresql://", "postgresql+psycopg://")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Default settings instance
settings = get_settings()
