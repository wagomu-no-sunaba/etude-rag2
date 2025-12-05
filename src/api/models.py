"""API request and response models."""

from enum import Enum

from pydantic import BaseModel, Field


class ArticleType(str, Enum):
    """Article type enumeration."""

    ANNOUNCEMENT = "ANNOUNCEMENT"
    EVENT_REPORT = "EVENT_REPORT"
    INTERVIEW = "INTERVIEW"
    CULTURE = "CULTURE"


class GenerateRequest(BaseModel):
    """Request model for article generation."""

    input_material: str = Field(
        description="入力素材（テーマ、キーポイント、インタビュー引用など）"
    )
    article_type: str | None = Field(
        default=None, description="記事タイプ（指定しない場合は自動分類）"
    )


class GenerateResponse(BaseModel):
    """Response model for article generation."""

    titles: list[str] = Field(description="タイトル案（3つ）")
    lead: str = Field(description="リード文")
    sections: list[dict[str, str]] = Field(description="本文セクション")
    closing: str = Field(description="締めの文章")
    article_type: str = Field(description="記事タイプ")
    article_type_ja: str = Field(description="記事タイプ（日本語）")
    markdown: str = Field(description="マークダウン形式の全文")


class HallucinationResult(BaseModel):
    """Hallucination check result for API response."""

    has_hallucination: bool = Field(description="ハルシネーションがあるか")
    confidence: float = Field(description="検証の信頼度（0-1）")
    verified_facts: list[str] = Field(default_factory=list, description="確認された事実")
    unverified_claims: list[dict[str, str]] = Field(
        default_factory=list, description="未確認の主張"
    )


class StyleResult(BaseModel):
    """Style check result for API response."""

    is_consistent: bool = Field(description="文体が一貫しているか")
    consistency_score: float = Field(description="一貫性スコア（0-1）")
    issues: list[dict[str, str]] = Field(default_factory=list, description="問題点")


class VerifyRequest(BaseModel):
    """Request model for content verification."""

    lead: str = Field(description="リード文")
    body: str = Field(description="本文")
    closing: str = Field(description="締め")
    input_material: str = Field(description="元の入力素材")


class VerifyResponse(BaseModel):
    """Response model for content verification."""

    hallucination: HallucinationResult = Field(description="ハルシネーション検証結果")
    style: StyleResult = Field(description="文体検証結果")


class SearchRequest(BaseModel):
    """Request model for article search."""

    query: str = Field(description="検索クエリ")
    article_type: str | None = Field(default=None, description="記事タイプでフィルタ")
    top_k: int = Field(default=10, ge=1, le=50, description="取得件数")


class SearchResult(BaseModel):
    """Single search result."""

    id: str = Field(description="ドキュメントID")
    title: str = Field(description="タイトル")
    content: str = Field(description="内容（抜粋）")
    article_type: str = Field(description="記事タイプ")
    score: float = Field(description="スコア")


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(description="エラータイプ")
    detail: str = Field(description="エラー詳細")
