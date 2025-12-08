#!/usr/bin/env python3
"""Seed style profile data into the database.

This script reads style profile markdown files and inserts them into
the style_profiles table with their embeddings.

Usage:
    uv run python scripts/seed_style_profiles.py
"""

import logging
import sys
from pathlib import Path

import psycopg2
from langchain_google_vertexai import VertexAIEmbeddings

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROFILE_DIR = Path(__file__).parent.parent / "data" / "style_profiles"

# Mapping of article types to profile file names
CATEGORY_FILES = {
    "INTERVIEW": "interview.md",
    "EVENT_REPORT": "event_report.md",
    "ANNOUNCEMENT": "announcement.md",
    "CULTURE": "culture.md",
}


def seed_profiles():
    """Insert or update style profiles in the database."""
    logger.info("Initializing embeddings model...")
    embeddings = VertexAIEmbeddings(
        model_name=settings.embedding_model,
        project=settings.google_project_id,
        location=settings.google_location,
    )

    logger.info(f"Connecting to database: {settings.db_host}...")
    conn = psycopg2.connect(settings.db_connection_string)
    cur = conn.cursor()

    success_count = 0
    error_count = 0

    for article_type, filename in CATEGORY_FILES.items():
        filepath = PROFILE_DIR / filename

        if not filepath.exists():
            logger.warning(f"Profile file not found: {filepath}, skipping")
            error_count += 1
            continue

        try:
            logger.info(f"Processing {article_type} from {filename}...")

            # Read content
            content = filepath.read_text(encoding="utf-8")

            # Generate embedding
            embedding = embeddings.embed_query(content)

            # UPSERT: Insert or update if exists
            # First check if profile exists
            cur.execute(
                """
                SELECT id FROM style_profiles
                WHERE article_type = %s AND profile_type = 'profile'
                """,
                (article_type,),
            )
            existing = cur.fetchone()

            if existing:
                # Update existing
                cur.execute(
                    """
                    UPDATE style_profiles
                    SET content = %s, embedding = %s, updated_at = NOW()
                    WHERE article_type = %s AND profile_type = 'profile'
                    """,
                    (content, embedding, article_type),
                )
                logger.info(f"  Updated existing profile for {article_type}")
            else:
                # Insert new
                cur.execute(
                    """
                    INSERT INTO style_profiles (article_type, profile_type, content, embedding)
                    VALUES (%s, 'profile', %s, %s)
                    """,
                    (article_type, content, embedding),
                )
                logger.info(f"  Inserted new profile for {article_type}")

            success_count += 1

        except Exception as e:
            logger.error(f"Error processing {article_type}: {e}")
            error_count += 1
            conn.rollback()
            continue

    conn.commit()
    cur.close()
    conn.close()

    logger.info(f"Done! Processed {success_count} profiles, {error_count} errors")
    return success_count, error_count


def verify_profiles():
    """Verify that profiles were inserted correctly."""
    logger.info("Verifying inserted profiles...")

    conn = psycopg2.connect(settings.db_connection_string)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT article_type, profile_type, LENGTH(content) as content_length,
               embedding IS NOT NULL as has_embedding, created_at
        FROM style_profiles
        WHERE profile_type = 'profile'
        ORDER BY article_type
        """
    )

    results = cur.fetchall()
    cur.close()
    conn.close()

    if not results:
        logger.warning("No profiles found in database!")
        return False

    logger.info("\nProfile verification:")
    logger.info("-" * 60)
    for row in results:
        article_type, profile_type, content_len, has_embedding, created_at = row
        status = "OK" if has_embedding else "NO EMBEDDING"
        logger.info(f"  {article_type}: {content_len} chars, {status}, {created_at}")

    logger.info("-" * 60)
    return True


if __name__ == "__main__":
    try:
        success, errors = seed_profiles()
        if errors == 0:
            verify_profiles()
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)
