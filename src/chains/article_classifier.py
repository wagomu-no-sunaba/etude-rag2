"""Article type classification chain."""

import logging
from typing import Literal

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, Field

from src.chains.input_parser import ParsedInput
from src.llm import get_llm

logger = logging.getLogger(__name__)

ArticleTypeStr = Literal["ANNOUNCEMENT", "EVENT_REPORT", "INTERVIEW", "CULTURE"]


class ClassificationResult(BaseModel):
    """Result of article type classification."""

    article_type: ArticleTypeStr = Field(
        description="記事タイプ（ANNOUNCEMENT, EVENT_REPORT, INTERVIEW, CULTURE）"
    )
    article_type_ja: str = Field(
        description="日本語での記事タイプ名（アナウンスメント, イベントレポート, インタビュー, カルチャー）"  # noqa: E501
    )
    confidence: float = Field(ge=0, le=1, description="判定の確信度（0-1）")
    reason: str = Field(description="判定理由")
    suggested_headings: list[str] = Field(
        min_length=2, max_length=4, description="推奨される見出し構成（2-4個）"
    )


SYSTEM_PROMPT = """あなたは記事タイプを分類する専門家です。

## タスク
構造化された素材から、作成すべき記事のタイプを判定してください。

## 記事タイプ（4種類）

1. ANNOUNCEMENT（アナウンスメント）
   - 新サービス、新機能のリリース告知
   - 会社からの重要なお知らせ
   - プレスリリース的な内容
   - キーワード: リリース、お知らせ、開始、発表、ローンチ

2. EVENT_REPORT（イベントレポート）
   - 社内勉強会の報告
   - 外部イベント参加レポート
   - ワークショップ、セミナーの振り返り
   - キーワード: 勉強会、イベント、セミナー、参加、開催、LT

3. INTERVIEW（インタビュー）
   - 社員インタビュー
   - 入社エントリ、退職エントリ
   - 特定の人物にフォーカスした記事
   - キーワード: インタビュー、入社、〇〇さん、働き方、キャリア

4. CULTURE（カルチャー）
   - 企業文化、価値観の紹介
   - 制度紹介（リモートワーク、福利厚生など）
   - チーム・組織の紹介
   - キーワード: 制度、文化、働き方、チーム、環境、福利厚生

## 判定ルール
- 迷った場合は素材の主目的で判定
- 複合的な場合は最も強い要素で判定

## 出力形式
以下のJSON形式で出力してください：
{format_instructions}"""

USER_PROMPT = """## 素材情報
テーマ: {theme}
キーポイント: {key_points}
登場人物: {people}
キーワード: {keywords}
インタビュー引用: {interview_quotes}

上記の素材から記事タイプを判定してください。"""


class ArticleClassifierChain:
    """Chain for classifying article type from parsed input."""

    def __init__(self, llm: ChatVertexAI | None = None):
        """Initialize the article classifier chain.

        Args:
            llm: Optional ChatVertexAI instance. Creates one if not provided.
        """
        # Use lite model for 4-category classification (lightweight task)
        self.llm = llm or get_llm(quality="lite", temperature=0.1)
        self.parser = JsonOutputParser(pydantic_object=ClassificationResult)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                ("human", USER_PROMPT),
            ]
        )
        self.chain = self.prompt | self.llm | self.parser

    def classify(self, parsed_input: ParsedInput) -> ClassificationResult:
        """Classify article type from parsed input.

        Args:
            parsed_input: Structured input from InputParserChain.

        Returns:
            ClassificationResult with article type and metadata.
        """
        result = self.chain.invoke(
            {
                "theme": parsed_input.theme,
                "key_points": ", ".join(parsed_input.key_points),
                "people": ", ".join(f"{p.name}({p.role})" for p in parsed_input.people),
                "keywords": ", ".join(parsed_input.keywords),
                "interview_quotes": ", ".join(
                    f"{q.speaker}: {q.quote}" for q in parsed_input.interview_quotes
                ),
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return ClassificationResult(**result)

    async def aclassify(self, parsed_input: ParsedInput) -> ClassificationResult:
        """Async version of classify.

        Args:
            parsed_input: Structured input from InputParserChain.

        Returns:
            ClassificationResult with article type and metadata.
        """
        result = await self.chain.ainvoke(
            {
                "theme": parsed_input.theme,
                "key_points": ", ".join(parsed_input.key_points),
                "people": ", ".join(f"{p.name}({p.role})" for p in parsed_input.people),
                "keywords": ", ".join(parsed_input.keywords),
                "interview_quotes": ", ".join(
                    f"{q.speaker}: {q.quote}" for q in parsed_input.interview_quotes
                ),
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return ClassificationResult(**result)
