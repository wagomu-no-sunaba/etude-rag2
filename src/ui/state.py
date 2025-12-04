"""State management models for the Streamlit UI."""

from typing import Any

from pydantic import BaseModel, Field


class GenerationState(BaseModel):
    """State for article generation."""

    input_material: str = Field(default="", description="入力素材")
    selected_article_type: str | None = Field(
        default=None, description="選択された記事タイプ"
    )
    generated_draft: dict[str, Any] | None = Field(
        default=None, description="生成されたドラフト"
    )
    is_generating: bool = Field(default=False, description="生成中フラグ")
    error_message: str | None = Field(default=None, description="エラーメッセージ")


class VerificationState(BaseModel):
    """State for content verification."""

    hallucination_result: dict[str, Any] | None = Field(
        default=None, description="ハルシネーション検証結果"
    )
    style_result: dict[str, Any] | None = Field(
        default=None, description="文体検証結果"
    )
    is_verifying: bool = Field(default=False, description="検証中フラグ")
    error_message: str | None = Field(default=None, description="エラーメッセージ")
