"""Content generation chains for article parts (title, lead, section, closing)."""

import logging

from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, Field

from src.chains.input_parser import ParsedInput
from src.chains.outline_generator import Outline, OutlineHeading
from src.chains.structure_analyzer import StructureAnalysis
from src.chains.style_analyzer import StyleAnalysis
from src.llm import get_llm

logger = logging.getLogger(__name__)


# ============== Output Models ==============


class TitleGeneratorOutput(BaseModel):
    """Output of title generation."""

    titles: list[str] = Field(min_length=3, max_length=3, description="タイトル案（3つ）")


class SectionContent(BaseModel):
    """Content of a single section."""

    heading: str = Field(description="見出しテキスト")
    body: str = Field(description="本文内容")


# ============== Title Generator ==============


TITLE_SYSTEM_PROMPT = """あなたはnote記事のタイトルを考える専門家です。

## タスク
以下の情報をもとに、魅力的なタイトル案を3つ作成してください。

## 記事情報
テーマ: {theme}
記事タイプ: {article_type}
アウトライン: {outline_summary}

## 記事タイプ別タイトル傾向
- アナウンスメント: 「〇〇をリリースしました」「〇〇のお知らせ」
- イベントレポート: 「〇〇勉強会レポート」「〇〇に参加してきました」
- インタビュー: 「〇〇さんに聞いてみた」「入社N年目の本音」
- カルチャー: 「ギグーの〇〇制度を紹介」「こんな働き方しています」

## タイトル作成のポイント
- ターゲット読者: 転職を検討しているエンジニア
- 目的: 採用広報、企業文化の紹介
- クリックしたくなる魅力的な表現
- 30文字前後を目安

## 出力形式
{format_instructions}"""

TITLE_USER_PROMPT = """タイトル案を3つ作成してください。"""


class TitleGeneratorChain:
    """Chain for generating article title options."""

    def __init__(self, llm: ChatVertexAI | None = None):
        # Use high quality model for creative title generation
        self.llm = llm or get_llm(quality="high", temperature=0.7)
        self.parser = JsonOutputParser(pydantic_object=TitleGeneratorOutput)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", TITLE_SYSTEM_PROMPT),
                ("human", TITLE_USER_PROMPT),
            ]
        )
        self.chain = self.prompt | self.llm | self.parser

    def generate(
        self,
        parsed_input: ParsedInput,
        article_type: str,
        outline: Outline,
    ) -> TitleGeneratorOutput:
        result = self.chain.invoke(
            {
                "theme": parsed_input.theme,
                "article_type": article_type,
                "outline_summary": ", ".join(h.title for h in outline.headings),
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return TitleGeneratorOutput(**result)


# ============== Lead Generator ==============


LEAD_SYSTEM_PROMPT = """あなたは株式会社ギグーのnote記事ライターです。

## タスク
記事の冒頭を飾るリード文を作成してください。

## 記事情報
テーマ: {theme}
記事タイプ: {article_type}
アウトライン: {outline_summary}

## 文体ガイド
トーン: {tone}
語尾パターン: {sentence_endings}
特徴的フレーズ: {characteristic_phrases}

## 過去記事のリード文パターン
{intro_pattern}

## 制約
- 100〜150字
- 記事を読みたくなる魅力的な書き出し
- 文体ガイドに従う
- ターゲット読者（転職検討中のエンジニア）を意識"""

LEAD_USER_PROMPT = """リード文を作成してください。"""


class LeadGeneratorChain:
    """Chain for generating article lead paragraph."""

    def __init__(self, llm: ChatVertexAI | None = None):
        # Use high quality model for lead paragraph generation
        self.llm = llm or get_llm(quality="high", temperature=0.5)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", LEAD_SYSTEM_PROMPT),
                ("human", LEAD_USER_PROMPT),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def generate(
        self,
        parsed_input: ParsedInput,
        article_type: str,
        outline: Outline,
        style_analysis: StyleAnalysis,
        structure_analysis: StructureAnalysis,
    ) -> str:
        return self.chain.invoke(
            {
                "theme": parsed_input.theme,
                "article_type": article_type,
                "outline_summary": ", ".join(h.title for h in outline.headings),
                "tone": style_analysis.tone,
                "sentence_endings": ", ".join(style_analysis.sentence_endings),
                "characteristic_phrases": ", ".join(style_analysis.characteristic_phrases),
                "intro_pattern": structure_analysis.intro_pattern,
            }
        )


# ============== Section Generator ==============


SECTION_SYSTEM_PROMPT = """あなたは株式会社ギグーのnote記事ライターです。

## タスク
指定された見出しの本文を執筆してください。

## 見出し情報
見出し: {heading_title}
概要: {heading_summary}
含めるべき情報: {key_content}
目標文字数: {target_length}字

## 記事タイプ
{article_type}

## 入力素材
テーマ: {theme}
キーポイント: {key_points}
インタビュー引用: {interview_quotes}
データ・数値: {data_facts}
登場人物: {people}

## 文体ガイド（必ず従うこと）
トーン: {tone}
語尾パターン: {sentence_endings}
一人称: {first_person}
読者への呼びかけ: {reader_address}
特徴的フレーズ: {characteristic_phrases}

## 絶対ルール
1. 入力素材に含まれない具体的な数値・固有名詞は補完しない
2. 不明な情報は [要確認: 〇〇] と記載
3. インタビュー引用は「」で括って使用
4. 文体ガイドの語尾パターンを使用
5. 事実と異なる情報を創作しない

## 出力
見出しの本文のみを出力（見出し自体は含めない）"""

SECTION_USER_PROMPT = """この見出しの本文を執筆してください。"""


class SectionGeneratorChain:
    """Chain for generating section content."""

    def __init__(self, llm: ChatVertexAI | None = None):
        # Use high quality model for section content generation
        self.llm = llm or get_llm(quality="high", temperature=0.5)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SECTION_SYSTEM_PROMPT),
                ("human", SECTION_USER_PROMPT),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def generate(
        self,
        heading: OutlineHeading,
        parsed_input: ParsedInput,
        article_type: str,
        style_analysis: StyleAnalysis,
    ) -> SectionContent:
        body = self.chain.invoke(
            {
                "heading_title": heading.title,
                "heading_summary": heading.summary,
                "key_content": ", ".join(heading.key_content),
                "target_length": heading.target_length,
                "article_type": article_type,
                "theme": parsed_input.theme,
                "key_points": ", ".join(parsed_input.key_points),
                "interview_quotes": ", ".join(
                    f"{q.speaker}: 「{q.quote}」" for q in parsed_input.interview_quotes
                ),
                "data_facts": ", ".join(parsed_input.data_facts),
                "people": ", ".join(f"{p.name}({p.role})" for p in parsed_input.people),
                "tone": style_analysis.tone,
                "sentence_endings": ", ".join(style_analysis.sentence_endings),
                "first_person": style_analysis.first_person,
                "reader_address": style_analysis.reader_address,
                "characteristic_phrases": ", ".join(style_analysis.characteristic_phrases),
            }
        )
        return SectionContent(heading=heading.title, body=body)

    def generate_all(
        self,
        outline: Outline,
        parsed_input: ParsedInput,
        article_type: str,
        style_analysis: StyleAnalysis,
    ) -> list[SectionContent]:
        """Generate content for all sections in the outline."""
        return [
            self.generate(heading, parsed_input, article_type, style_analysis)
            for heading in outline.headings
        ]


# ============== Closing Generator ==============


CLOSING_SYSTEM_PROMPT = """あなたは株式会社ギグーのnote記事ライターです。

## タスク
記事の締めの文章を作成してください。

## 記事情報
テーマ: {theme}
記事タイプ: {article_type}

## 文体ガイド
トーン: {tone}
語尾パターン: {sentence_endings}

## 過去記事の締めパターン
{closing_pattern}

## 記事タイプ別締め方
- アナウンスメント: サービスへの誘導、今後の展開
- イベントレポート: 次回予告、参加募集
- インタビュー: 応募への誘導、SNSフォロー促進
- カルチャー: 採用サイトへの誘導、問い合わせ案内

## 制約
- 3〜5文程度
- 読後感の良い締めくくり
- 適切なCTA（Call To Action）を含める
- 文体ガイドに従う"""

CLOSING_USER_PROMPT = """締めの文章を作成してください。"""


class ClosingGeneratorChain:
    """Chain for generating article closing."""

    def __init__(self, llm: ChatVertexAI | None = None):
        # Use high quality model for closing paragraph generation
        self.llm = llm or get_llm(quality="high", temperature=0.5)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", CLOSING_SYSTEM_PROMPT),
                ("human", CLOSING_USER_PROMPT),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def generate(
        self,
        parsed_input: ParsedInput,
        article_type: str,
        style_analysis: StyleAnalysis,
        structure_analysis: StructureAnalysis,
    ) -> str:
        return self.chain.invoke(
            {
                "theme": parsed_input.theme,
                "article_type": article_type,
                "tone": style_analysis.tone,
                "sentence_endings": ", ".join(style_analysis.sentence_endings),
                "closing_pattern": structure_analysis.closing_pattern,
            }
        )
