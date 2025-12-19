"""Tests for generated_articles table schema.

Verifies that the schema.sql file contains the generated_articles table
with the required structure:
- id: UUID primary key
- input_material: TEXT NOT NULL
- article_type: article_type NOT NULL
- generated_content: JSONB NOT NULL
- markdown: TEXT NOT NULL
- created_at: TIMESTAMPTZ with default
"""

from pathlib import Path

import pytest

SCHEMA_FILE = Path(__file__).parent.parent / "schemas" / "schema.sql"


@pytest.fixture
def schema_sql():
    """Load the schema.sql file content."""
    return SCHEMA_FILE.read_text()


def test_generated_articles_table_exists(schema_sql):
    """Test that generated_articles table definition exists in schema.sql.

    This is the first test in the TDD cycle for PBI-003.
    The table should store generated article history for recruiters.
    """
    assert "CREATE TABLE IF NOT EXISTS generated_articles" in schema_sql, (
        "schema.sql should contain generated_articles table definition"
    )


def test_generated_articles_has_uuid_primary_key(schema_sql):
    """Test that generated_articles has UUID primary key with auto-generation."""
    assert "id UUID PRIMARY KEY DEFAULT gen_random_uuid()" in schema_sql, (
        "generated_articles should have UUID primary key with default"
    )


def test_generated_articles_has_input_material_column(schema_sql):
    """Test that generated_articles has input_material TEXT NOT NULL column."""
    assert "input_material TEXT NOT NULL" in schema_sql, (
        "generated_articles should have input_material TEXT NOT NULL"
    )


def test_generated_articles_has_article_type_column(schema_sql):
    """Test that generated_articles has article_type column using the enum."""
    assert "article_type article_type NOT NULL" in schema_sql, (
        "generated_articles should have article_type column with enum type"
    )


def test_generated_articles_has_generated_content_jsonb(schema_sql):
    """Test that generated_articles has generated_content JSONB NOT NULL column."""
    assert "generated_content JSONB NOT NULL" in schema_sql, (
        "generated_articles should have generated_content JSONB NOT NULL"
    )


def test_generated_articles_has_markdown_column(schema_sql):
    """Test that generated_articles has markdown TEXT NOT NULL column."""
    assert "markdown TEXT NOT NULL" in schema_sql, (
        "generated_articles should have markdown TEXT NOT NULL"
    )


def test_generated_articles_has_created_at_column(schema_sql):
    """Test that generated_articles has created_at with default timestamp."""
    assert "created_at TIMESTAMPTZ DEFAULT NOW()" in schema_sql, (
        "generated_articles should have created_at TIMESTAMPTZ DEFAULT NOW()"
    )
