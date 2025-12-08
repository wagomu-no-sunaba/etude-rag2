"""API client for communicating with the FastAPI backend."""

import json
import logging
import os
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ProgressUpdate:
    """Progress update from SSE stream."""

    step: str
    step_name: str
    step_number: int
    total_steps: int
    percentage: int


@dataclass
class StreamResult:
    """Final result from SSE stream."""

    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None


def _get_id_token(audience: str) -> str | None:
    """Get ID token for Cloud Run service-to-service authentication.

    Args:
        audience: The URL of the target service.

    Returns:
        ID token string, or None if not running on GCP or token fetch fails.
    """
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token

        request = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(request, audience)
        return token
    except Exception as e:
        logger.debug(f"Could not get ID token (likely running locally): {e}")
        return None


class APIClient:
    """Client for the article generation API."""

    def __init__(self, base_url: str | None = None):
        """Initialize the API client.

        Args:
            base_url: Base URL of the API server. If not provided, uses API_URL env var
                     or defaults to http://localhost:8000.
        """
        self.base_url = base_url or os.environ.get("API_URL", "http://localhost:8000")
        self.timeout = 120.0  # 2 minutes for LLM operations

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for API requests.

        Returns:
            Headers dict with Authorization if running on GCP, empty dict otherwise.
        """
        token = _get_id_token(self.base_url)
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    def health_check(self) -> bool:
        """Check if the API is healthy.

        Returns:
            True if API is healthy, False otherwise.
        """
        try:
            headers = self._get_auth_headers()
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/health", headers=headers)
                return response.status_code == 200
        except httpx.RequestError:
            return False

    def generate(
        self,
        input_material: str,
        article_type: str | None = None,
    ) -> dict[str, Any]:
        """Generate an article draft.

        Args:
            input_material: Raw input material.
            article_type: Optional article type override.

        Returns:
            Generated article draft.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        headers = self._get_auth_headers()
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/generate",
                json={
                    "input_material": input_material,
                    "article_type": article_type,
                },
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def verify(
        self,
        lead: str,
        body: str,
        closing: str,
        input_material: str,
    ) -> dict[str, Any]:
        """Verify generated content.

        Args:
            lead: Lead paragraph.
            body: Body text.
            closing: Closing paragraph.
            input_material: Original input material.

        Returns:
            Verification results.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        headers = self._get_auth_headers()
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/verify",
                json={
                    "lead": lead,
                    "body": body,
                    "closing": closing,
                    "input_material": input_material,
                },
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def search(
        self,
        query: str,
        article_type: str | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for reference articles.

        Args:
            query: Search query.
            article_type: Optional article type filter.
            top_k: Number of results to return.

        Returns:
            List of search results.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        headers = self._get_auth_headers()
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/search",
                json={
                    "query": query,
                    "article_type": article_type,
                    "top_k": top_k,
                },
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def generate_stream(
        self,
        input_material: str,
        article_type: str | None = None,
    ) -> Generator[ProgressUpdate | StreamResult, None, None]:
        """Generate an article with streaming progress updates.

        Yields ProgressUpdate objects for each step, then a StreamResult
        with the final result or error.

        Args:
            input_material: Raw input material.
            article_type: Optional article type override.

        Yields:
            ProgressUpdate for progress events, StreamResult for completion/error.
        """
        headers = self._get_auth_headers()
        headers["Accept"] = "text/event-stream"

        # Use explicit client management to avoid Streamlit re-render issues
        client = httpx.Client(timeout=None)
        try:
            with client.stream(
                "POST",
                f"{self.base_url}/generate/stream",
                json={
                    "input_material": input_material,
                    "article_type": article_type,
                },
                headers=headers,
            ) as response:
                response.raise_for_status()

                event_type: str | None = None
                data_buffer: str = ""

                for line in response.iter_lines():
                    line = line.strip()

                    if not line:
                        # Empty line marks end of event
                        if event_type and data_buffer:
                            try:
                                data = json.loads(data_buffer)
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse SSE data: {data_buffer}")
                                event_type = None
                                data_buffer = ""
                                continue

                            if event_type == "progress":
                                yield ProgressUpdate(
                                    step=data["step"],
                                    step_name=data["step_name"],
                                    step_number=data["step_number"],
                                    total_steps=data["total_steps"],
                                    percentage=data["percentage"],
                                )
                            elif event_type == "complete":
                                yield StreamResult(
                                    success=True,
                                    result=data["result"],
                                )
                                return
                            elif event_type == "error":
                                yield StreamResult(
                                    success=False,
                                    error=data.get("error", "Unknown error"),
                                )
                                return

                        event_type = None
                        data_buffer = ""
                        continue

                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data_buffer = line[5:].strip()
        except httpx.RequestError as e:
            logger.error(f"Request error during streaming: {e}")
            yield StreamResult(success=False, error=str(e))
        finally:
            client.close()
