"""Tests for SSE streaming in HTMX UI."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestFormSSEConnection:
    """Tests for form SSE connection setup."""

    def test_form_uses_sse_connection(self, client: TestClient):
        """Form should submit to streaming endpoint and trigger SSE connection.

        The form posts to /ui/generate/stream which returns HTML with
        SSE connection attributes for real-time progress updates.
        """
        response = client.get("/")
        assert response.status_code == 200

        html = response.text
        # Form should post to streaming endpoint
        assert 'hx-post="/ui/generate/stream"' in html, (
            "Form should POST to /ui/generate/stream for SSE streaming"
        )


class TestHTMXSSEExtension:
    """Tests for HTMX SSE extension loading."""

    def test_htmx_sse_extension_loaded(self, client: TestClient):
        """Base template should include HTMX SSE extension script from CDN.

        The SSE extension enables HTMX to handle Server-Sent Events,
        which is required for streaming generation progress updates.
        """
        response = client.get("/")
        assert response.status_code == 200

        html = response.text
        # Check for HTMX SSE extension script tag
        assert "htmx.org" in html, "HTMX core should be loaded"
        assert "sse" in html.lower(), "SSE extension script should be present"
        # Verify it's the extension, not just any mention of "sse"
        assert 'ext/sse' in html or 'sse.js' in html, (
            "HTMX SSE extension should be loaded from CDN"
        )
