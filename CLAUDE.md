# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RAG system for generating note article drafts (recruiting articles). Supports 4 article types: ANNOUNCEMENT, EVENT_REPORT, INTERVIEW, CULTURE. Uses hybrid search (vector + full-text) with BGE reranking.

## Common Commands

```bash
# Install dependencies
uv sync

# Run API server
uv run uvicorn src.api.main:app --reload --port 8000

# Run Streamlit UI
uv run streamlit run src/ui/app.py

# Run tests
uv run pytest tests/ -v
uv run pytest tests/test_retriever.py::test_function_name -v  # Single test

# Lint and format
uv run ruff format .
uv run ruff check --fix .
uv run mypy src/

# Data ingestion
uv run python src/main.py --folder-id FOLDER_ID
uv run python src/main.py --local-file input.md --article-type ANNOUNCEMENT

# Database setup
psql rag_db < schemas/schema.sql
```

## Architecture

### Core Pipeline (src/chains/)

`ArticleGenerationPipeline` orchestrates the full generation flow:

1. **InputParserChain** - Extracts structured data (theme, keywords, facts) from raw input
2. **ArticleClassifierChain** - Determines article type (ANNOUNCEMENT/EVENT_REPORT/INTERVIEW/CULTURE)
3. **ArticleRetriever** - Fetches similar past articles using hybrid search
4. **StyleAnalyzerChain** + **StructureAnalyzerChain** - Analyzes reference articles
5. **OutlineGeneratorChain** - Creates article outline
6. **Content Generators** - TitleGeneratorChain, LeadGeneratorChain, SectionGeneratorChain, ClosingGeneratorChain

### Hybrid Search (src/retriever/)

- **HybridSearcher** - Combines pgvector cosine similarity + pg_trgm trigram matching
- Uses Reciprocal Rank Fusion (RRF): `score = Σ(1/(rank + k))`
- **BGEReranker** - Cross-encoder reranking with BAAI/bge-reranker-base

### Verification (src/verification/)

- **HallucinationDetectorChain** - Identifies claims not grounded in source material
- **StyleCheckerChain** - Verifies consistency with company writing style

### API Layer (src/api/)

FastAPI with endpoints: `/generate`, `/search`, `/verify`, `/health`

### Configuration (src/config.py, src/secrets.py)

Pydantic Settings with **Secret Manager integration**. Configuration priority:
1. Environment variables (highest priority, for Cloud Run)
2. Google Cloud Secret Manager (for secrets)
3. `.env` file (local development fallback)

Key settings:
- `HYBRID_SEARCH_K`, `RRF_K`, `FINAL_K` - Search tuning parameters
- `RERANKER_MODEL`, `RERANKER_TOP_K` - Reranker configuration
- `DB_HOST` starting with `/` triggers Unix socket connection (Cloud SQL)
- `DB_PASSWORD`, `TARGET_FOLDER_ID`, `MY_EMAIL` - Auto-loaded from Secret Manager

Secret Manager secrets (managed by Terraform):
- `etude-rag2-db-password-{env}` - Database password
- `etude-rag2-drive-folder-id-{env}` - Google Drive folder ID
- `etude-rag2-my-email-{env}` - Email for ACL filtering
- `etude-rag2-app-config-{env}` - App config (JSON)

Local development:
```bash
# Generate .env from Secret Manager
./scripts/sync-env-from-secrets.sh dev
```

## Database

PostgreSQL with pgvector and pg_trgm extensions. Schema in `schemas/schema.sql`.

Key table: `documents` with columns:
- `embedding vector(768)` - Vertex AI text-embedding-004
- `article_type` - ENUM for filtering
- `content` - Text with trigram index

## Code Style

- Line length: 100
- Python 3.12+ type hints
- Pydantic for all data models
- LangChain Expression Language (LCEL) for chains: `chain = prompt | llm | parser`
