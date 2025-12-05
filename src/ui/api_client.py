"""API client for communicating with the FastAPI backend."""

from typing import Any

import httpx


class APIClient:
    """Client for the article generation API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize the API client.

        Args:
            base_url: Base URL of the API server.
        """
        self.base_url = base_url
        self.timeout = 120.0  # 2 minutes for LLM operations

    def health_check(self) -> bool:
        """Check if the API is healthy.

        Returns:
            True if API is healthy, False otherwise.
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/health")
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
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/generate",
                json={
                    "input_material": input_material,
                    "article_type": article_type,
                },
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
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/verify",
                json={
                    "lead": lead,
                    "body": body,
                    "closing": closing,
                    "input_material": input_material,
                },
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
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/search",
                json={
                    "query": query,
                    "article_type": article_type,
                    "top_k": top_k,
                },
            )
            response.raise_for_status()
            return response.json()
