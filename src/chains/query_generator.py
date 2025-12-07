"""Query generation chain for category-optimized search queries.

Generates search queries optimized for retrieving reference articles
based on the parsed input and article category.
"""

import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_vertexai import ChatVertexAI

from src.chains.input_parser import ParsedInput
from src.llm import get_llm
from src.retriever.article_retriever import ArticleType

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """あなたは検索クエリを最適化する専門家です。

## タスク
以下の情報から、{category}記事の内容検索に最適な検索クエリを生成してください。

## 入力情報
- テーマ: {theme}
- 読者: {audience}
- 目的: {goal}
- キーワード: {keywords}

## クエリ生成ルール
- キーワード列挙形式で出力（スペース区切り）
- 各クエリは簡潔に（1-6単語）
- テーマに関連するクエリ（2-3個）
- {category}記事の構成参考用クエリ（1-2個）

## カテゴリ別最適化
- INTERVIEW: 人物名、役職、キャリア、働き方
- EVENT_REPORT: イベント名、勉強会、学び、参加
- ANNOUNCEMENT: サービス名、リリース、新機能、お知らせ
- CULTURE: 制度名、文化、働き方、チーム

## 出力形式
search_query: "キーワード1 キーワード2 キーワード3 ..."

キーワードのみをスペース区切りで出力してください。"""

USER_PROMPT = """検索クエリを生成してください。"""


class QueryGeneratorChain:
    """Chain for generating category-optimized search queries.

    Corresponds to Dify v3: node_query_gen_*
    """

    def __init__(self, llm: ChatVertexAI | None = None):
        """Initialize the query generator chain.

        Args:
            llm: Optional ChatVertexAI instance. Creates one if not provided.
        """
        # Use lite model for query generation (lightweight task)
        self.llm = llm or get_llm(quality="lite", temperature=0.3)
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYSTEM_PROMPT),
                ("human", USER_PROMPT),
            ]
        )
        self.chain = self.prompt | self.llm | StrOutputParser()

    def generate(
        self,
        parsed_input: ParsedInput,
        category: ArticleType,
    ) -> str:
        """Generate search query optimized for the article category.

        Args:
            parsed_input: Structured input from InputParserChain.
            category: Article category (ArticleType enum).

        Returns:
            Space-separated search query string.
        """
        result = self.chain.invoke(
            {
                "category": category.value,
                "theme": parsed_input.theme,
                "audience": parsed_input.audience or "転職を検討しているエンジニア",
                "goal": parsed_input.goal or "採用広報、企業文化の紹介",
                "keywords": ", ".join(parsed_input.keywords) if parsed_input.keywords else "なし",
            }
        )
        # Clean up the result - extract just the keywords
        return self._clean_query(result)

    async def agenerate(
        self,
        parsed_input: ParsedInput,
        category: ArticleType,
    ) -> str:
        """Async version of generate.

        Args:
            parsed_input: Structured input from InputParserChain.
            category: Article category (ArticleType enum).

        Returns:
            Space-separated search query string.
        """
        result = await self.chain.ainvoke(
            {
                "category": category.value,
                "theme": parsed_input.theme,
                "audience": parsed_input.audience or "転職を検討しているエンジニア",
                "goal": parsed_input.goal or "採用広報、企業文化の紹介",
                "keywords": ", ".join(parsed_input.keywords) if parsed_input.keywords else "なし",
            }
        )
        return self._clean_query(result)

    def _clean_query(self, raw_output: str) -> str:
        """Clean up the LLM output to extract keywords only.

        Args:
            raw_output: Raw output from the LLM.

        Returns:
            Cleaned space-separated keyword string.
        """
        # Remove common prefixes like "search_query:" or "クエリ:"
        cleaned = raw_output.strip()
        for prefix in ["search_query:", "クエリ:", "検索クエリ:", '"', "'"]:
            if cleaned.lower().startswith(prefix.lower()):
                cleaned = cleaned[len(prefix) :].strip()

        # Remove trailing quotes
        cleaned = cleaned.strip("\"'")

        return cleaned
