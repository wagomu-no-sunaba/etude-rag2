"""SSE event models for streaming article generation."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GenerationStep(str, Enum):
    """Article generation pipeline steps."""

    INPUT_PARSING = "input_parsing"
    CLASSIFICATION = "classification"
    RETRIEVAL = "retrieval"
    ANALYSIS = "analysis"
    OUTLINE = "outline"
    CONTENT = "content"


# Step metadata for UI display
STEP_METADATA: dict[GenerationStep, dict[str, Any]] = {
    GenerationStep.INPUT_PARSING: {
        "name_ja": "入力解析",
        "order": 1,
        "percentage": 10,
    },
    GenerationStep.CLASSIFICATION: {
        "name_ja": "記事タイプ判定",
        "order": 2,
        "percentage": 20,
    },
    GenerationStep.RETRIEVAL: {
        "name_ja": "参考記事検索",
        "order": 3,
        "percentage": 35,
    },
    GenerationStep.ANALYSIS: {
        "name_ja": "スタイル・構成分析",
        "order": 4,
        "percentage": 50,
    },
    GenerationStep.OUTLINE: {
        "name_ja": "アウトライン生成",
        "order": 5,
        "percentage": 65,
    },
    GenerationStep.CONTENT: {
        "name_ja": "コンテンツ生成",
        "order": 6,
        "percentage": 100,
    },
}


class SSEEventType(str, Enum):
    """Types of SSE events."""

    PROGRESS = "progress"
    COMPLETE = "complete"
    ERROR = "error"


class ProgressEvent(BaseModel):
    """Progress update event."""

    event_type: str = Field(default=SSEEventType.PROGRESS.value, description="Event type")
    step: GenerationStep = Field(description="Current step identifier")
    step_name: str = Field(description="Step name in Japanese")
    step_number: int = Field(description="Step number (1-6)")
    total_steps: int = Field(default=6, description="Total number of steps")
    percentage: int = Field(ge=0, le=100, description="Progress percentage")


class CompleteEvent(BaseModel):
    """Generation complete event with final result."""

    event_type: str = Field(default=SSEEventType.COMPLETE.value, description="Event type")
    result: dict[str, Any] = Field(description="Generated article draft")


class ErrorEvent(BaseModel):
    """Error event."""

    event_type: str = Field(default=SSEEventType.ERROR.value, description="Event type")
    error: str = Field(description="Error message")
    step: GenerationStep | None = Field(default=None, description="Step where error occurred")
