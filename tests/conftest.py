"""Pytest configuration and fixtures."""

import os

import pytest


def pytest_configure(config):
    """Set up test environment variables before tests run."""
    # Set required environment variables for testing
    os.environ.setdefault("GOOGLE_PROJECT_ID", "test-project")
    os.environ.setdefault("GOOGLE_LOCATION", "us-central1")
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_NAME", "test_db")
    os.environ.setdefault("DB_USER", "test_user")
    os.environ.setdefault("DB_PASSWORD", "test_password")


@pytest.fixture
def mock_settings():
    """Provide mock settings for testing."""
    from src.config import Settings

    return Settings(
        google_project_id="test-project",
        google_location="us-central1",
        db_host="localhost",
        db_name="test_db",
        db_user="test_user",
        db_password="test_password",
    )
