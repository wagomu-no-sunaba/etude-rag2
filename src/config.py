"""Configuration management using Pydantic Settings.

Environment variables or .env file can be used to configure the application.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Google Cloud
    google_project_id: str
    google_location: str = "us-central1"
    service_account_file: str | None = None

    # Vertex AI
    embedding_model: str = "text-embedding-004"
    llm_model: str = "gemini-1.5-pro"
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
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_top_k: int = 5  # Number of results after reranking
    use_fp16: bool = True  # Use FP16 for reranker inference

    # Google Drive
    target_folder_id: str | None = None

    # Chunking
    chunk_size: int = 1000
    chunk_overlap: int = 200

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
