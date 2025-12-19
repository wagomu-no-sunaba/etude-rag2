"""Tests for HTMX base template and configuration."""

import pytest
from fastapi.testclient import TestClient


class TestJinja2TemplatesConfiguration:
    """Test Jinja2Templates is properly configured in FastAPI app."""

    def test_jinja2_templates_configured(self):
        """FastAPI app has Jinja2Templates configured with src/templates directory."""
        from src.api.main import app

        # Check that templates attribute exists and is properly configured
        assert hasattr(app.state, "templates"), "app.state.templates should be configured"

        # Verify it's a Jinja2Templates instance
        from fastapi.templating import Jinja2Templates

        assert isinstance(
            app.state.templates, Jinja2Templates
        ), "templates should be Jinja2Templates instance"

    def test_static_files_mounted(self):
        """Static files are mounted at /static path."""
        from src.api.main import app

        # Check routes for static file mount
        routes = [route.path for route in app.routes]
        static_paths = [r for r in routes if r.startswith("/static")]

        assert len(static_paths) > 0, "Static files should be mounted at /static"

    def test_index_returns_html(self):
        """GET / returns HTML page with proper content type."""
        from src.api.main import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_html_structure(self):
        """Base template includes proper HTML5 structure with Japanese lang attribute."""
        from src.api.main import app

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        html = response.text

        # Check HTML5 doctype
        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html.lower()

        # Check Japanese language attribute
        assert 'lang="ja"' in html

        # Check basic HTML structure
        assert "<html" in html
        assert "<head>" in html
        assert "<body>" in html
