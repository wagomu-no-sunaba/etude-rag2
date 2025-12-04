"""Style consistency checker for generated articles."""

import logging
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, Field

from src.chains.style_analyzer import StyleAnalysis
from src.config import settings

logger = logging.getLogger(__name__)


class StyleIssue(BaseModel):
    """A single style inconsistency issue."""

    location: str = Field(description="問題のある箇所（リード文、本文N段落目など）")
    issue: str = Field(description="問題の内容")
    suggestion: str = Field(description="修正提案")


class CorrectedSection(BaseModel):
    """A corrected section of text."""

    original: str = Field(description="元のテキスト")
    corrected: str = Field(description="修正後のテキスト")


class StyleCheckResult(BaseModel):
    """Result of style consistency check."""

    is_consistent: bool = Field(description="文体が一貫しているか")
    consistency_score: float = Field(
        ge=0, le=1, description="一貫性スコア（0-1）"
    )
    issues: list[StyleIssue] = Field(
        default_factory=list, description="不一致箇所"
    )
    corrected_sections: list[dict[str, str]] = Field(
        default_factory=list, description="修正が必要な箇所の修正案"
    )


SYSTEM_PROMPT = """あなたは文体の一貫性を検証する専門家です。

## タスク
生成された記事が文体ガイドに従っているか検証してください。

## 文体ガイド
語尾パターン: {sentence_endings}
トーン: {tone}
一人称: {first_person}
特徴的フレーズ: {characteristic_phrases}

## 検証項目
1. 語尾パターンの使用率
2. トーンの一貫性
3. 一人称の統一
4. 特徴的フレーズの使用
5. 不自然な表現

## 出力形式
{format_instructions}"""

USER_PROMPT = """## 生成された記事

リード文:
{lead}

本文:
{body}

締め:
{closing}

文体の一貫性を検証してください。"""


class StyleCheckerChain:
    """Chain for checking style consistency of generated articles."""

    def __init__(self, llm: ChatVertexAI | None = None):
        """Initialize the style checker chain.

        Args:
            llm: Optional ChatVertexAI instance. Creates one if not provided.
        """
        self.llm = llm or ChatVertexAI(
            model_name=settings.llm_model,
            project=settings.google_project_id,
            location=settings.google_location,
            temperature=0.1,  # Low temperature for consistent checking
        )
        self.parser = JsonOutputParser(pydantic_object=StyleCheckResult)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                ("human", USER_PROMPT),
            ]
        )
        self.chain = self.prompt | self.llm | self.parser

    def check(
        self,
        lead: str,
        body: str,
        closing: str,
        style_analysis: StyleAnalysis,
    ) -> StyleCheckResult:
        """Check style consistency of generated content.

        Args:
            lead: Lead paragraph text.
            body: Main body text.
            closing: Closing paragraph text.
            style_analysis: Reference style analysis.

        Returns:
            StyleCheckResult with consistency score and issues.
        """
        result = self.chain.invoke(
            {
                "lead": lead,
                "body": body,
                "closing": closing,
                "sentence_endings": ", ".join(style_analysis.sentence_endings),
                "tone": style_analysis.tone,
                "first_person": style_analysis.first_person,
                "characteristic_phrases": ", ".join(
                    style_analysis.characteristic_phrases
                ),
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return StyleCheckResult(**result)

    async def acheck(
        self,
        lead: str,
        body: str,
        closing: str,
        style_analysis: StyleAnalysis,
    ) -> StyleCheckResult:
        """Async version of check."""
        result = await self.chain.ainvoke(
            {
                "lead": lead,
                "body": body,
                "closing": closing,
                "sentence_endings": ", ".join(style_analysis.sentence_endings),
                "tone": style_analysis.tone,
                "first_person": style_analysis.first_person,
                "characteristic_phrases": ", ".join(
                    style_analysis.characteristic_phrases
                ),
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return StyleCheckResult(**result)

    @staticmethod
    def apply_corrections(text: str, corrections: list[dict[str, str]]) -> str:
        """Apply corrections to text.

        Args:
            text: Original text.
            corrections: List of {"original": str, "corrected": str} dicts.

        Returns:
            Text with corrections applied.
        """
        result = text
        for correction in corrections:
            if correction.get("original") and correction.get("corrected"):
                result = result.replace(
                    correction["original"], correction["corrected"]
                )
        return result
