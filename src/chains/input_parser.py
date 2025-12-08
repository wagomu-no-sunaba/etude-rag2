"""Input material parsing and structuring chain."""

import logging
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, Field

from src.llm import get_llm

logger = logging.getLogger(__name__)


class InterviewQuote(BaseModel):
    """Interview quote with speaker attribution."""

    speaker: str = Field(description="発言者の名前")
    quote: str = Field(description="引用可能な発言内容")


class Person(BaseModel):
    """Person mentioned in the material."""

    name: str = Field(description="名前")
    role: str = Field(description="役職・立場")


class ParsedInput(BaseModel):
    """Structured representation of input material (Dify v3 compatible)."""

    # Existing fields
    theme: str = Field(description="記事のテーマ・主旨（1文で要約）")
    key_points: list[str] = Field(default_factory=list, description="記事に含めるべき重要ポイント")
    interview_quotes: list[InterviewQuote] = Field(
        default_factory=list, description="引用可能なインタビュー発言"
    )
    data_facts: list[str] = Field(default_factory=list, description="具体的な数値やデータ")
    people: list[Person] = Field(default_factory=list, description="登場人物")
    keywords: list[str] = Field(default_factory=list, description="検索用キーワード（5-10個）")
    missing_info: list[str] = Field(
        default_factory=list, description="記事作成に不足していそうな情報"
    )

    # New fields for Dify v3 compatibility
    category: str = Field(
        default="",
        description="記事カテゴリ（INTERVIEW / EVENT_REPORT / ANNOUNCEMENT / CULTURE）",
    )
    audience: str = Field(default="", description="想定読者")
    goal: str = Field(default="", description="記事の目的")
    desired_length: int = Field(default=2000, description="希望文字数")


SYSTEM_PROMPT = """あなたは入力情報を構造化するエキスパートです。

## タスク
ユーザーから提供された記事素材を分析し、以下の情報を抽出・構造化してください。

## 抽出項目
1. category: 記事カテゴリ（INTERVIEW / EVENT_REPORT / ANNOUNCEMENT / CULTURE）
2. theme: 記事のテーマ・主旨（1文で要約）
3. audience: 想定読者
4. goal: 記事の目的
5. desired_length: 希望文字数（指定なしの場合は2000）
6. key_points: 記事に含めるべき重要ポイント
7. interview_quotes: インタビュー発言（該当する場合）
8. data_facts: 具体的な数値やデータ
9. people: 登場人物（名前、役職）
10. keywords: 検索用キーワード（5-10個）
11. missing_info: 不足している情報

## カテゴリ判定基準
- INTERVIEW: 社員インタビュー、入社エントリ、人物フォーカス
- EVENT_REPORT: 勉強会、イベント、セミナー報告
- ANNOUNCEMENT: 新サービス、リリース、お知らせ
- CULTURE: 企業文化、制度紹介、カルチャー

## ルール
- 入力にない情報は推測しない
- カテゴリが不明確な場合は最も近いものを選択
- 数値や固有名詞は正確に抽出
- interview_quotesは {{"speaker": "発言者名", "quote": "発言内容"}} 形式

## 出力形式
以下のJSON形式で出力してください：
{format_instructions}"""

USER_PROMPT = """## 入力素材
{input_material}

上記の素材を構造化してください。"""


class InputParserChain:
    """Chain for parsing and structuring input material."""

    def __init__(self, llm: ChatVertexAI | None = None):
        """Initialize the input parser chain.

        Args:
            llm: Optional ChatVertexAI instance. Creates one if not provided.
        """
        # Use lite model for structured extraction (lightweight task)
        self.llm = llm or get_llm(quality="lite", temperature=0.2)
        self.parser = JsonOutputParser(pydantic_object=ParsedInput)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                ("human", USER_PROMPT),
            ]
        )
        self.chain = self.prompt | self.llm | self.parser

    def parse(self, input_material: str) -> ParsedInput:
        """Parse input material into structured format.

        Args:
            input_material: Raw input text from user.

        Returns:
            ParsedInput object with extracted information.
        """
        result = self.chain.invoke(
            {
                "input_material": input_material,
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return ParsedInput(**result)

    async def aparse(self, input_material: str) -> ParsedInput:
        """Async version of parse.

        Args:
            input_material: Raw input text from user.

        Returns:
            ParsedInput object with extracted information.
        """
        result = await self.chain.ainvoke(
            {
                "input_material": input_material,
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return ParsedInput(**result)

    def parse_dict(self, input_material: str) -> dict[str, Any]:
        """Parse input material and return as dictionary.

        Args:
            input_material: Raw input text from user.

        Returns:
            Dictionary with extracted information.
        """
        return self.parse(input_material).model_dump()
