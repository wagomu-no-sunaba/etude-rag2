"""Hallucination detection for generated articles."""

import logging

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, Field

from src.chains.input_parser import ParsedInput
from src.llm import get_llm

logger = logging.getLogger(__name__)


class UnverifiedClaim(BaseModel):
    """An unverified claim found in the generated text."""

    claim: str = Field(description="入力素材で確認できなかった主張")
    location: str = Field(description="主張の場所（リード文、本文N段落目など）")
    suggested_tag: str = Field(description="[要確認]タグに付けるラベル")


class HallucinationCheckResult(BaseModel):
    """Result of hallucination detection."""

    has_hallucination: bool = Field(description="ハルシネーションがあるか")
    confidence: float = Field(ge=0, le=1, description="検証の信頼度（0-1）")
    verified_facts: list[str] = Field(default_factory=list, description="入力素材で確認できた事実")
    unverified_claims: list[UnverifiedClaim] = Field(
        default_factory=list, description="入力素材で確認できなかった主張"
    )
    missing_citations: list[str] = Field(default_factory=list, description="引用元が不明な発言")


SYSTEM_PROMPT = """あなたは事実確認の専門家です。

## タスク
生成された記事に、入力素材にない情報（ハルシネーション）が含まれていないか検証してください。

## 入力素材（これが事実の根拠）
テーマ: {theme}
キーポイント: {key_points}
インタビュー引用: {interview_quotes}
データ・数値: {data_facts}
登場人物: {people}

## 検証ルール
1. 記事内の具体的な事実（数値、日付、固有名詞、発言）を抽出
2. 各事実が入力素材に存在するか照合
3. 存在しない事実を「要確認候補」としてマーク
4. 一般的な表現（感想、形容詞など）は許容

## 重点チェック項目
- 数値（年数、金額、人数など）
- 固有名詞（製品名、サービス名、人名など）
- 具体的な日付・期間
- インタビュー発言（「」内）

## 出力形式
{format_instructions}"""

USER_PROMPT = """## 生成された記事

リード文:
{lead}

本文:
{body}

締め:
{closing}

ハルシネーションを検出してください。"""


class HallucinationDetectorChain:
    """Chain for detecting hallucinations in generated articles."""

    def __init__(self, llm: ChatVertexAI | None = None):
        """Initialize the hallucination detector chain.

        Args:
            llm: Optional ChatVertexAI instance. Creates one if not provided.
        """
        # Use lite model for fact-checking verification (lightweight)
        self.llm = llm or get_llm(quality="lite", temperature=0)
        self.parser = JsonOutputParser(pydantic_object=HallucinationCheckResult)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                ("human", USER_PROMPT),
            ]
        )
        self.chain = self.prompt | self.llm | self.parser

    def detect(
        self,
        lead: str,
        body: str,
        closing: str,
        parsed_input: ParsedInput,
    ) -> HallucinationCheckResult:
        """Detect hallucinations in generated content.

        Args:
            lead: Lead paragraph text.
            body: Main body text.
            closing: Closing paragraph text.
            parsed_input: Original parsed input for fact checking.

        Returns:
            HallucinationCheckResult with detected issues.
        """
        result = self.chain.invoke(
            {
                "lead": lead,
                "body": body,
                "closing": closing,
                "theme": parsed_input.theme,
                "key_points": ", ".join(parsed_input.key_points),
                "interview_quotes": ", ".join(
                    f"{q.speaker}: 「{q.quote}」" for q in parsed_input.interview_quotes
                ),
                "data_facts": ", ".join(parsed_input.data_facts),
                "people": ", ".join(f"{p.name}({p.role})" for p in parsed_input.people),
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return HallucinationCheckResult(**result)

    async def adetect(
        self,
        lead: str,
        body: str,
        closing: str,
        parsed_input: ParsedInput,
    ) -> HallucinationCheckResult:
        """Async version of detect."""
        result = await self.chain.ainvoke(
            {
                "lead": lead,
                "body": body,
                "closing": closing,
                "theme": parsed_input.theme,
                "key_points": ", ".join(parsed_input.key_points),
                "interview_quotes": ", ".join(
                    f"{q.speaker}: 「{q.quote}」" for q in parsed_input.interview_quotes
                ),
                "data_facts": ", ".join(parsed_input.data_facts),
                "people": ", ".join(f"{p.name}({p.role})" for p in parsed_input.people),
                "format_instructions": self.parser.get_format_instructions(),
            }
        )
        return HallucinationCheckResult(**result)

    @staticmethod
    def apply_tags(text: str, claims: list[UnverifiedClaim]) -> str:
        """Apply [要確認] tags to text for unverified claims.

        Args:
            text: Original text.
            claims: List of unverified claims to tag.

        Returns:
            Text with [要確認] tags inserted.
        """
        result = text
        for claim in claims:
            if claim.claim in result:
                tag = f"[要確認: {claim.suggested_tag}]"
                result = result.replace(claim.claim, f"{claim.claim} {tag}")
        return result
