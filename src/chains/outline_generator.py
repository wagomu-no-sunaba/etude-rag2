"""Outline generation chain for creating article structure."""

import logging

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, Field

from src.chains.input_parser import ParsedInput
from src.chains.structure_analyzer import StructureAnalysis
from src.config import settings

logger = logging.getLogger(__name__)


class OutlineHeading(BaseModel):
    """A single heading in the article outline."""

    title: str = Field(description="見出しテキスト")
    summary: str = Field(description="このセクションで書く内容の概要")
    key_content: list[str] = Field(
        default_factory=list, description="含めるべき素材からの情報"
    )
    target_length: int = Field(default=300, description="目標文字数")


class Outline(BaseModel):
    """Complete article outline with headings."""

    headings: list[OutlineHeading] = Field(
        min_length=2, max_length=4, description="見出し構成（2-4個）"
    )
    total_target_length: int = Field(default=1500, description="本文全体の目標文字数")


SYSTEM_PROMPT = """あなたは記事構成の専門家です。

## タスク
以下の情報をもとに、記事のアウトライン（骨子）を作成してください。

## 記事情報
テーマ: {theme}
記事タイプ: {article_type}
キーポイント: {key_points}
インタビュー引用: {interview_quotes}

## 構成パターン（過去記事分析結果）
典型的な見出し: {typical_headings}
セクションの流れ: {section_flow}

## 記事タイプ別ガイドライン
- アナウンスメント: 概要→詳細→今後の展開→CTA
- イベントレポート: 導入→イベント概要→学び・気づき→まとめ
- インタビュー: 人物紹介→きっかけ→現在の仕事→今後の展望
- カルチャー: 制度紹介→具体的な運用→社員の声→まとめ

## 制約
- 見出しは2〜4個
- 全体で1,500字程度を想定
- 各見出しに対して、その下に書く内容の概要を記載

## 出力形式
以下のJSON形式で出力してください：
{format_instructions}"""

USER_PROMPT = """アウトラインを作成してください。"""


class OutlineGeneratorChain:
    """Chain for generating article outline from parsed input and structure analysis."""

    def __init__(self, llm: ChatVertexAI | None = None):
        """Initialize the outline generator chain.

        Args:
            llm: Optional ChatVertexAI instance. Creates one if not provided.
        """
        self.llm = llm or ChatVertexAI(
            model_name=settings.llm_model,
            project=settings.google_project_id,
            location=settings.google_location,
            temperature=0.5,  # Moderate temperature for creative outline
        )
        self.parser = JsonOutputParser(pydantic_object=Outline)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                ("human", USER_PROMPT),
            ]
        )
        self.chain = self.prompt | self.llm | self.parser

    def generate(
        self,
        parsed_input: ParsedInput,
        article_type: str,
        structure_analysis: StructureAnalysis,
    ) -> Outline:
        """Generate article outline from input and analysis.

        Args:
            parsed_input: Structured input from InputParserChain.
            article_type: Japanese name of the article type.
            structure_analysis: Structure patterns from StructureAnalyzerChain.

        Returns:
            Outline with headings and target lengths.
        """
        result = self.chain.invoke(
            {
                "theme": parsed_input.theme,
                "article_type": article_type,
                "key_points": ", ".join(parsed_input.key_points),
                "interview_quotes": ", ".join(
                    f"{q.speaker}: {q.quote}" for q in parsed_input.interview_quotes
                ),
                "typical_headings": ", ".join(structure_analysis.typical_headings),
                "section_flow": structure_analysis.section_flow,
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return Outline(**result)

    async def agenerate(
        self,
        parsed_input: ParsedInput,
        article_type: str,
        structure_analysis: StructureAnalysis,
    ) -> Outline:
        """Async version of generate.

        Args:
            parsed_input: Structured input from InputParserChain.
            article_type: Japanese name of the article type.
            structure_analysis: Structure patterns from StructureAnalyzerChain.

        Returns:
            Outline with headings and target lengths.
        """
        result = await self.chain.ainvoke(
            {
                "theme": parsed_input.theme,
                "article_type": article_type,
                "key_points": ", ".join(parsed_input.key_points),
                "interview_quotes": ", ".join(
                    f"{q.speaker}: {q.quote}" for q in parsed_input.interview_quotes
                ),
                "typical_headings": ", ".join(structure_analysis.typical_headings),
                "section_flow": structure_analysis.section_flow,
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return Outline(**result)
