"""Structure analysis chain for extracting article structure patterns."""

import logging

from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, Field

from src.config import settings

logger = logging.getLogger(__name__)


class StructureAnalysis(BaseModel):
    """Extracted structure patterns from reference articles."""

    typical_headings: list[str] = Field(description="よく使われる見出しパターン")
    intro_pattern: str = Field(description="リード文の書き方パターン")
    section_flow: str = Field(default="", description="セクションの流れ（導入→展開→まとめ等）")
    closing_pattern: str = Field(description="締めの文章パターン")
    average_length: str = Field(default="", description="平均的な文字数の目安")


SYSTEM_PROMPT = """あなたは記事構成を分析する専門家です。

## タスク
以下の過去記事から、記事の構成パターンを分析してください。

## 今回の記事タイプ
{article_type}

## 分析項目
1. typical_headings: よく使われる見出しパターン
2. intro_pattern: リード文の書き方パターン
3. section_flow: セクションの流れ（導入→展開→まとめ等）
4. closing_pattern: 締めの文章パターン
5. average_length: 平均的な文字数の目安

## 記事タイプ別の特徴
- アナウンスメント: 結論先行、簡潔、リンク誘導
- イベントレポート: 時系列、参加者の声、学び
- インタビュー: Q&A形式、人物描写、ストーリー
- カルチャー: 制度説明、具体例、メリット

## 出力形式
以下のJSON形式で出力してください：
{format_instructions}"""

USER_PROMPT = """## 過去記事
{reference_articles}

上記から構成パターンを分析してください。"""


class StructureAnalyzerChain:
    """Chain for analyzing article structure patterns from reference articles."""

    def __init__(self, llm: ChatVertexAI | None = None):
        """Initialize the structure analyzer chain.

        Args:
            llm: Optional ChatVertexAI instance. Creates one if not provided.
        """
        self.llm = llm or ChatVertexAI(
            model_name=settings.llm_model,
            project=settings.google_project_id,
            location=settings.google_location,
            temperature=0.2,
        )
        self.parser = JsonOutputParser(pydantic_object=StructureAnalysis)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                ("human", USER_PROMPT),
            ]
        )
        self.chain = self.prompt | self.llm | self.parser

    def analyze(
        self,
        reference_articles: list[Document],
        article_type: str,
    ) -> StructureAnalysis:
        """Analyze article structure patterns from reference articles.

        Args:
            reference_articles: List of reference article documents.
            article_type: Japanese name of the article type.

        Returns:
            StructureAnalysis with extracted structure patterns.
        """
        articles_text = self._format_articles(reference_articles)

        result = self.chain.invoke(
            {
                "reference_articles": articles_text,
                "article_type": article_type,
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return StructureAnalysis(**result)

    async def aanalyze(
        self,
        reference_articles: list[Document],
        article_type: str,
    ) -> StructureAnalysis:
        """Async version of analyze.

        Args:
            reference_articles: List of reference article documents.
            article_type: Japanese name of the article type.

        Returns:
            StructureAnalysis with extracted structure patterns.
        """
        articles_text = self._format_articles(reference_articles)

        result = await self.chain.ainvoke(
            {
                "reference_articles": articles_text,
                "article_type": article_type,
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return StructureAnalysis(**result)

    def _format_articles(self, articles: list[Document]) -> str:
        """Format articles for the prompt.

        Args:
            articles: List of Document objects.

        Returns:
            Formatted string of articles.
        """
        formatted = []
        for i, doc in enumerate(articles, 1):
            title = doc.metadata.get("source_file", f"記事{i}")
            formatted.append(f"【{i}. {title}】\n{doc.page_content}")
        return "\n\n---\n\n".join(formatted)
