"""Style analysis chain for extracting writing style from reference articles."""

import logging

from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, Field

from src.config import settings

logger = logging.getLogger(__name__)


class StyleAnalysis(BaseModel):
    """Extracted style characteristics from reference articles."""

    sentence_endings: list[str] = Field(
        description="よく使われる語尾パターン（例: 〜です、〜ですね、〜なんです）"
    )
    tone: str = Field(description="全体的なトーン（カジュアル/フォーマル/その中間）")
    first_person: str = Field(default="私", description="使われている一人称")
    reader_address: str = Field(default="", description="読者への呼びかけ方")
    paragraph_style: str = Field(default="", description="段落の長さや区切り方の傾向")
    emoji_usage: str = Field(default="", description="絵文字の使用有無と頻度")
    characteristic_phrases: list[str] = Field(
        default_factory=list, description="特徴的なフレーズや言い回し"
    )


SYSTEM_PROMPT = """あなたは文章スタイルを分析する専門家です。

## タスク
以下の過去記事から、株式会社ギグーのnote記事の文体特徴を抽出してください。

## 記事タイプ
{article_type}

## 分析項目
1. sentence_endings: よく使われる語尾パターン（例: 「〜ですね」「〜なんです」）
2. tone: 全体的なトーン（カジュアル/フォーマル/その中間）
3. first_person: 使われている一人称（私/僕/筆者など）
4. reader_address: 読者への呼びかけ方
5. paragraph_style: 段落の長さや区切り方の傾向
6. emoji_usage: 絵文字の使用有無と頻度
7. characteristic_phrases: 特徴的なフレーズや言い回し（5-10個）

## ルール
- 具体例を挙げて説明
- 記事タイプに特有のスタイルがあれば明記
- 複数の記事に共通するパターンを優先

## 出力形式
以下のJSON形式で出力してください：
{format_instructions}"""

USER_PROMPT = """## 過去記事
{reference_articles}

上記の過去記事から文体特徴を抽出してください。"""


class StyleAnalyzerChain:
    """Chain for analyzing writing style from reference articles."""

    def __init__(self, llm: ChatVertexAI | None = None):
        """Initialize the style analyzer chain.

        Args:
            llm: Optional ChatVertexAI instance. Creates one if not provided.
        """
        self.llm = llm or ChatVertexAI(
            model_name=settings.llm_model,
            project=settings.google_project_id,
            location=settings.google_location,
            temperature=0.2,
        )
        self.parser = JsonOutputParser(pydantic_object=StyleAnalysis)
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
    ) -> StyleAnalysis:
        """Analyze writing style from reference articles.

        Args:
            reference_articles: List of reference article documents.
            article_type: Japanese name of the article type.

        Returns:
            StyleAnalysis with extracted style characteristics.
        """
        # Format reference articles
        articles_text = self._format_articles(reference_articles)

        result = self.chain.invoke(
            {
                "reference_articles": articles_text,
                "article_type": article_type,
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return StyleAnalysis(**result)

    async def aanalyze(
        self,
        reference_articles: list[Document],
        article_type: str,
    ) -> StyleAnalysis:
        """Async version of analyze.

        Args:
            reference_articles: List of reference article documents.
            article_type: Japanese name of the article type.

        Returns:
            StyleAnalysis with extracted style characteristics.
        """
        articles_text = self._format_articles(reference_articles)

        result = await self.chain.ainvoke(
            {
                "reference_articles": articles_text,
                "article_type": article_type,
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return StyleAnalysis(**result)

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
