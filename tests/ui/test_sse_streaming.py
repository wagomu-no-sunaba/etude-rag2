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


class TestProgressPartial:
    """Tests for progress partial template."""

    def test_progress_bar_updates(self, client: TestClient):
        """POST /ui/generate/stream should return progress partial with progress bar.

        The progress partial displays:
        - A progress bar showing percentage
        - Current step name in Japanese
        - SSE connection attributes for live updates
        """
        response = client.post(
            "/ui/generate/stream",
            data={"input_material": "テスト素材", "article_type": ""},
        )
        assert response.status_code == 200

        html = response.text
        # Should contain progress bar element
        assert "progress" in html.lower(), "Response should contain progress element"
        # Should have SSE extension enabled
        assert 'hx-ext="sse"' in html, "Progress partial should use SSE extension"

    def test_step_name_display(self, client: TestClient):
        """Progress partial should display current step name in Japanese.

        The step name element should:
        - Have an ID for SSE targeting
        - Display initial "準備中..." text
        - Be updatable via SSE events
        """
        response = client.post(
            "/ui/generate/stream",
            data={"input_material": "テスト素材", "article_type": ""},
        )
        assert response.status_code == 200

        html = response.text
        # Should have step name element with initial text
        assert "準備中" in html, "Should display initial step name in Japanese"
        # Should have sse-swap that includes progress event
        assert "sse-swap=" in html, "Should have SSE swap attribute"
        assert "progress" in html, "Should handle progress events"

    def test_result_displays_on_complete(self, client: TestClient):
        """Progress partial should have sse-swap for complete event.

        When SSE sends a 'complete' event, the result partial should
        replace the progress container with the generated article.
        """
        response = client.post(
            "/ui/generate/stream",
            data={"input_material": "テスト素材", "article_type": ""},
        )
        assert response.status_code == 200

        html = response.text
        # Should have sse-swap that includes complete event
        assert "sse-swap=" in html, "Should have SSE swap attribute"
        assert "complete" in html, "Should handle complete events"

    def test_error_message_display(self, client: TestClient):
        """Progress partial should have sse-swap for error event.

        When SSE sends an 'error' event, an error message should
        be displayed to the user.
        """
        response = client.post(
            "/ui/generate/stream",
            data={"input_material": "テスト素材", "article_type": ""},
        )
        assert response.status_code == 200

        html = response.text
        # Should have sse-swap that includes error event
        assert "sse-swap=" in html, "Should have SSE swap attribute"
        assert "error" in html, "Should handle error events"


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
        assert "ext/sse" in html or "sse.js" in html, "HTMX SSE extension should be loaded from CDN"
