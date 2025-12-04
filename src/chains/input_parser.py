"""Input material parsing and structuring chain."""

import logging
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, Field

from src.config import settings

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
    """Structured representation of input material."""

    theme: str = Field(description="記事のテーマ・主旨（1文で要約）")
    key_points: list[str] = Field(
        default_factory=list, description="記事に含めるべき重要ポイント"
    )
    interview_quotes: list[InterviewQuote] = Field(
        default_factory=list, description="引用可能なインタビュー発言"
    )
    data_facts: list[str] = Field(
        default_factory=list, description="具体的な数値やデータ"
    )
    people: list[Person] = Field(default_factory=list, description="登場人物")
    keywords: list[str] = Field(
        default_factory=list, description="検索用キーワード（5-10個）"
    )
    missing_info: list[str] = Field(
        default_factory=list, description="記事作成に不足していそうな情報"
    )


SYSTEM_PROMPT = """あなたは入力素材を構造化するエキスパートです。

## タスク
ユーザーから提供された記事素材を分析し、構造化データに変換してください。

## 抽出項目
1. theme: 記事のテーマ・主旨（1文で要約）
2. key_points: 記事に含めるべき重要ポイント（箇条書きから抽出）
3. interview_quotes: インタビュー内容（そのまま引用可能な発言）
4. data_facts: 具体的な数値やデータ
5. people: 登場人物（名前、役職）
6. keywords: 検索に使えるキーワード（5-10個）
7. missing_info: 記事作成に不足していそうな情報

## ルール
- 入力にない情報は推測しない
- 曖昧な表現はそのまま保持
- 数値や固有名詞は正確に抽出

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
        self.llm = llm or ChatVertexAI(
            model_name=settings.llm_model,
            project=settings.google_project_id,
            location=settings.google_location,
            temperature=0.2,  # Low temperature for structured extraction
        )
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
