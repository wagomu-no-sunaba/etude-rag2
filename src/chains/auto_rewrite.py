"""Auto-rewrite chain for style consistency correction.

Automatically rewrites article content to match the target style profile
when style consistency score is below threshold.
"""

import logging

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, Field

from src.llm import get_llm
from src.verification.style_checker import StyleCheckResult

logger = logging.getLogger(__name__)


class RewriteResult(BaseModel):
    """Result of automatic rewriting."""

    rewritten_text: str = Field(description="リライト後の記事テキスト")
    changes_made: list[str] = Field(default_factory=list, description="実施した変更点のリスト")
    original_length: int = Field(default=0, description="元の文字数")
    rewritten_length: int = Field(default=0, description="リライト後の文字数")


SYSTEM_PROMPT = """あなたはスタイル編集者です。
STYLE_PROFILE を満たすように本文を完全リライトしてください。

## STYLE_PROFILE（文体ルール）
{style_profile}

## 文体チェック結果
一貫性スコア: {consistency_score}
問題点: {issues}
修正案: {corrected_sections}

## 指示
1. STYLE_PROFILEに一致するよう文体を整える
2. 文体チェック結果の修正案を反映
3. 内容・事実は変更しない
4. 構成（見出し順序）は維持
5. 語尾パターン、トーン、一人称を統一

## 出力形式
{format_instructions}"""

USER_PROMPT = """## 元の記事
{article_text}

上記の記事をSTYLE_PROFILEに従ってリライトしてください。"""


class AutoRewriteChain:
    """Chain for automatically rewriting articles to match style profile.

    Corresponds to Dify v3: node_auto_rewrite

    This chain takes an article with style inconsistencies and rewrites
    it to match the target style profile while preserving the content.
    """

    def __init__(self, llm: ChatVertexAI | None = None):
        """Initialize the auto-rewrite chain.

        Args:
            llm: Optional ChatVertexAI instance. Creates one if not provided.
        """
        # Use high quality model for rewriting (quality-sensitive task)
        self.llm = llm or get_llm(quality="high", temperature=0.5)
        self.parser = JsonOutputParser(pydantic_object=RewriteResult)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                ("human", USER_PROMPT),
            ]
        )
        self.chain = self.prompt | self.llm | self.parser

    def rewrite(
        self,
        article_text: str,
        style_check_result: StyleCheckResult,
        style_profile: str,
    ) -> RewriteResult:
        """Rewrite article to match style profile.

        Args:
            article_text: Original article text (full markdown).
            style_check_result: Result from StyleCheckerChain.
            style_profile: Style profile content.

        Returns:
            RewriteResult with rewritten text and change summary.
        """
        # Format issues and corrections for the prompt
        issues_text = "\n".join(
            f"- {issue.location}: {issue.issue}" for issue in style_check_result.issues
        )
        corrections_text = "\n".join(
            f"- {c.get('original', '')} → {c.get('corrected', '')}"
            for c in style_check_result.corrected_sections
        )

        result = self.chain.invoke(
            {
                "style_profile": style_profile,
                "consistency_score": f"{style_check_result.consistency_score:.1%}",
                "issues": issues_text or "なし",
                "corrected_sections": corrections_text or "なし",
                "article_text": article_text,
                "format_instructions": self.parser.get_format_instructions(),
            }
        )

        # Calculate lengths
        rewrite_result = RewriteResult(**result)
        rewrite_result.original_length = len(article_text)
        rewrite_result.rewritten_length = len(rewrite_result.rewritten_text)

        return rewrite_result

    async def arewrite(
        self,
        article_text: str,
        style_check_result: StyleCheckResult,
        style_profile: str,
    ) -> RewriteResult:
        """Async version of rewrite.

        Args:
            article_text: Original article text (full markdown).
            style_check_result: Result from StyleCheckerChain.
            style_profile: Style profile content.

        Returns:
            RewriteResult with rewritten text and change summary.
        """
        issues_text = "\n".join(
            f"- {issue.location}: {issue.issue}" for issue in style_check_result.issues
        )
        corrections_text = "\n".join(
            f"- {c.get('original', '')} → {c.get('corrected', '')}"
            for c in style_check_result.corrected_sections
        )

        result = await self.chain.ainvoke(
            {
                "style_profile": style_profile,
                "consistency_score": f"{style_check_result.consistency_score:.1%}",
                "issues": issues_text or "なし",
                "corrected_sections": corrections_text or "なし",
                "article_text": article_text,
                "format_instructions": self.parser.get_format_instructions(),
            }
        )

        rewrite_result = RewriteResult(**result)
        rewrite_result.original_length = len(article_text)
        rewrite_result.rewritten_length = len(rewrite_result.rewritten_text)

        return rewrite_result

    def should_rewrite(
        self,
        style_check_result: StyleCheckResult,
        threshold: float = 0.8,
    ) -> bool:
        """Determine if rewriting is needed based on style check.

        Args:
            style_check_result: Result from StyleCheckerChain.
            threshold: Consistency score threshold (default: 0.8).

        Returns:
            True if consistency score is below threshold.
        """
        return style_check_result.consistency_score < threshold
