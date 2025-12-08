"""LLM factory functions for 2-tier model configuration.

Provides centralized LLM instance creation with quality-based model selection:
- "high": gemini-2.0-flash for creative/quality-sensitive tasks
- "lite": gemini-2.0-flash-lite for lightweight/cost-sensitive tasks
"""

from langchain_google_vertexai import ChatVertexAI

from src.config import settings


def get_llm(
    quality: str = "high",
    temperature: float | None = None,
) -> ChatVertexAI:
    """Get LLM instance based on quality level.

    Args:
        quality: Model quality level
            - "high": Use gemini-2.0-flash (creative tasks, quality-sensitive)
            - "lite": Use gemini-2.0-flash-lite (lightweight tasks, cost-sensitive)
        temperature: Override default temperature. If None, uses settings.llm_temperature.

    Returns:
        ChatVertexAI instance configured with the appropriate model.

    Examples:
        >>> # High quality for content generation
        >>> llm = get_llm(quality="high", temperature=0.7)

        >>> # Lite for classification/extraction
        >>> llm = get_llm(quality="lite", temperature=0.1)
    """
    # Select model based on quality and feature flag
    if quality == "lite" and settings.use_lite_model:
        model = settings.llm_model_lite
    else:
        model = settings.llm_model

    # Use provided temperature or default
    temp = temperature if temperature is not None else settings.llm_temperature

    return ChatVertexAI(
        model_name=model,
        project=settings.google_project_id,
        location=settings.google_location,
        temperature=temp,
    )
