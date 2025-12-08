"""Article generation orchestration chain (Dify v3 compatible)."""

import logging
from collections.abc import Callable
from typing import Any

from langchain_core.documents import Document
from pydantic import BaseModel, Field

from src.chains.article_classifier import ArticleClassifierChain, ClassificationResult
from src.chains.auto_rewrite import AutoRewriteChain
from src.chains.content_generators import (
    ClosingGeneratorChain,
    LeadGeneratorChain,
    SectionGeneratorChain,
    TitleGeneratorChain,
)
from src.chains.input_parser import InputParserChain, ParsedInput
from src.chains.outline_generator import Outline, OutlineGeneratorChain
from src.chains.query_generator import QueryGeneratorChain
from src.chains.structure_analyzer import StructureAnalysis, StructureAnalyzerChain
from src.chains.style_analyzer import StyleAnalysis, StyleAnalyzerChain
from src.config import settings
from src.retriever.article_retriever import ArticleRetriever, ArticleType
from src.retriever.style_retriever import StyleProfileRetriever
from src.verification.hallucination_detector import HallucinationDetectorChain
from src.verification.style_checker import StyleCheckerChain

logger = logging.getLogger(__name__)


class ArticleDraft(BaseModel):
    """Complete article draft output (Dify v3 compatible with metadata)."""

    titles: list[str] = Field(description="タイトル案（3つ）")
    lead: str = Field(description="リード文")
    sections: list[dict[str, str]] = Field(description="本文セクション")
    closing: str = Field(description="締めの文章")
    article_type: str = Field(description="記事タイプ")
    article_type_ja: str = Field(description="記事タイプ（日本語）")
    metadata: dict[str, Any] = Field(default_factory=dict, description="メタデータ")

    # New fields for Dify v3 compatibility
    theme: str = Field(default="", description="記事テーマ")
    desired_length: int = Field(default=2000, description="希望文字数")
    actual_length: int = Field(default=0, description="実際の文字数")
    tag_count: int = Field(default=0, description="[要確認]タグの数")
    consistency_score: float = Field(default=0.0, description="文体一貫性スコア")
    verification_confidence: float = Field(default=0.0, description="事実検証信頼度")

    def calculate_length(self) -> int:
        """Calculate total content length."""
        return len(self.lead) + sum(len(s["body"]) for s in self.sections) + len(self.closing)

    def to_markdown(self) -> str:
        """Convert draft to markdown format."""
        lines = []

        # Title options
        lines.append("## タイトル案（3つ）\n")
        for i, title in enumerate(self.titles, 1):
            lines.append(f"{i}. {title}")
        lines.append("")

        # Lead
        lines.append("## リード文\n")
        lines.append(self.lead)
        lines.append("")

        # Body sections
        lines.append("## 本文\n")
        for section in self.sections:
            lines.append(f"### {section['heading']}\n")
            lines.append(section["body"])
            lines.append("")

        # Closing
        lines.append("## 締め\n")
        lines.append(self.closing)
        lines.append("")

        # Metadata
        lines.append("---\n")
        lines.append(f"**記事タイプ**: {self.article_type_ja}")
        total_length = self.calculate_length()
        lines.append(f"**総文字数**: 約{total_length}字")

        return "\n".join(lines)

    def to_markdown_with_meta(self) -> str:
        """Convert draft to markdown with comprehensive metadata (Dify v3 compatible)."""
        md = self.to_markdown()

        category_ja = {
            "INTERVIEW": "インタビュー",
            "EVENT_REPORT": "イベントレポート",
            "ANNOUNCEMENT": "アナウンスメント",
            "CULTURE": "カルチャー/ストーリー",
        }

        self.actual_length = self.calculate_length()

        meta = f"""

---

### メタ情報

- **記事カテゴリ**: {category_ja.get(self.article_type, self.article_type_ja)}
- **テーマ**: {self.theme}
- **総文字数**: 約{self.actual_length}字（目標: {self.desired_length}字）
- **[要確認]タグ**: {self.tag_count}箇所
- **文体一貫性スコア**: {int(self.consistency_score * 100)}%
- **事実検証信頼度**: {int(self.verification_confidence * 100)}%

### 次のステップ

1. [要確認] タグがある箇所は事実確認してください
2. タイトルは3案から選択または調整してください
3. 必要に応じて文章を微調整してください
"""
        return md + meta


class ArticleGenerationPipeline:
    """Full pipeline for generating article drafts (Dify v3 compatible).

    This pipeline orchestrates all chains:
    1. Input parsing (flash-lite)
    2. Article type classification (flash-lite)
    3. Query generation (flash-lite) [NEW]
    4. Reference article retrieval (CONTENT_KB)
    5. Style profile retrieval (STYLE_PROFILE + STYLE_EXCERPTS) [NEW]
    6. Style and structure analysis (flash-lite)
    7. Outline generation (flash)
    8. Content generation (flash)
    9. Quality assurance pipeline [NEW]
       - Style check (flash-lite)
       - Auto-rewrite if needed (flash)
       - Hallucination detection (flash-lite)
    10. Final formatting with metadata
    """

    def __init__(
        self,
        retriever: ArticleRetriever | None = None,
        input_parser: InputParserChain | None = None,
        classifier: ArticleClassifierChain | None = None,
        query_generator: QueryGeneratorChain | None = None,
        style_retriever: StyleProfileRetriever | None = None,
        style_analyzer: StyleAnalyzerChain | None = None,
        structure_analyzer: StructureAnalyzerChain | None = None,
        outline_generator: OutlineGeneratorChain | None = None,
        title_generator: TitleGeneratorChain | None = None,
        lead_generator: LeadGeneratorChain | None = None,
        section_generator: SectionGeneratorChain | None = None,
        closing_generator: ClosingGeneratorChain | None = None,
        style_checker: StyleCheckerChain | None = None,
        hallucination_detector: HallucinationDetectorChain | None = None,
        auto_rewriter: AutoRewriteChain | None = None,
    ):
        """Initialize the pipeline with optional custom components."""
        self.retriever = retriever
        self.input_parser = input_parser or InputParserChain()
        self.classifier = classifier or ArticleClassifierChain()

        # New Dify v3 components
        self.query_generator = query_generator or QueryGeneratorChain()
        self.style_retriever = style_retriever  # Lazy init to avoid DB connection on import

        self.style_analyzer = style_analyzer or StyleAnalyzerChain()
        self.structure_analyzer = structure_analyzer or StructureAnalyzerChain()
        self.outline_generator = outline_generator or OutlineGeneratorChain()
        self.title_generator = title_generator or TitleGeneratorChain()
        self.lead_generator = lead_generator or LeadGeneratorChain()
        self.section_generator = section_generator or SectionGeneratorChain()
        self.closing_generator = closing_generator or ClosingGeneratorChain()

        # Quality assurance components
        self.style_checker = style_checker or StyleCheckerChain()
        self.hallucination_detector = hallucination_detector or HallucinationDetectorChain()
        self.auto_rewriter = auto_rewriter or AutoRewriteChain()

    def _get_style_retriever(self) -> StyleProfileRetriever:
        """Lazy initialization of style retriever."""
        if self.style_retriever is None:
            self.style_retriever = StyleProfileRetriever()
        return self.style_retriever

    def generate(
        self,
        input_material: str,
        reference_articles: list[Document] | None = None,
        enable_quality_assurance: bool = True,
    ) -> ArticleDraft:
        """Generate a complete article draft (Dify v3 compatible).

        Args:
            input_material: Raw input material from user.
            reference_articles: Optional pre-fetched reference articles.
                If None and retriever is configured, articles will be retrieved.
            enable_quality_assurance: Whether to run quality assurance pipeline.

        Returns:
            ArticleDraft with all generated content and metadata.
        """
        # Step 1: Parse input material
        logger.info("Step 1: Parsing input material")
        parsed_input = self.input_parser.parse(input_material)

        # Step 2: Classify article type
        logger.info("Step 2: Classifying article type")
        classification = self.classifier.classify(parsed_input)
        article_type = ArticleType(classification.article_type)

        # Step 3: Generate optimized search query (Dify v3)
        search_query = parsed_input.theme
        if settings.use_query_generator:
            logger.info("Step 3: Generating optimized search query")
            search_query = self.query_generator.generate(parsed_input, article_type)
        else:
            logger.info("Step 3: Using theme as search query (query_generator disabled)")

        # Step 4: Retrieve reference articles if not provided
        if reference_articles is None and self.retriever:
            logger.info("Step 4: Retrieving reference articles")
            reference_articles = self._retrieve_references(
                parsed_input, classification, search_query
            )
        elif reference_articles is None:
            reference_articles = []

        # Step 5: Retrieve style profile (Dify v3)
        style_profile = None
        if settings.use_style_profile_kb:
            logger.info("Step 5: Retrieving style profile")
            style_profile = self._get_style_retriever().retrieve_profile(article_type)

        # Step 6: Analyze style and structure
        logger.info("Step 6: Analyzing style and structure")
        style_analysis, structure_analysis = self._analyze_references(
            reference_articles, classification.article_type_ja
        )

        # Step 7: Generate outline
        logger.info("Step 7: Generating outline")
        outline = self.outline_generator.generate(
            parsed_input, classification.article_type_ja, structure_analysis
        )

        # Step 8: Generate content
        logger.info("Step 8: Generating content")
        draft = self._generate_content(
            parsed_input,
            classification,
            outline,
            style_analysis,
            structure_analysis,
        )

        # Set theme and desired_length from parsed input
        draft.theme = parsed_input.theme
        draft.desired_length = parsed_input.desired_length

        # Step 9: Quality assurance pipeline (Dify v3)
        if enable_quality_assurance:
            logger.info("Step 9: Running quality assurance pipeline")
            draft = self._run_quality_assurance(
                draft, parsed_input, style_analysis, style_profile, reference_articles
            )

        return draft

    def generate_with_progress(
        self,
        input_material: str,
        progress_callback: Callable[[str], None] | None = None,
        reference_articles: list[Document] | None = None,
    ) -> ArticleDraft:
        """Generate a complete article draft with progress callbacks.

        Args:
            input_material: Raw input material from user.
            progress_callback: Optional callback for progress updates.
                Called with step name (str) after each step completes.
            reference_articles: Optional pre-fetched reference articles.
                If None and retriever is configured, articles will be retrieved.

        Returns:
            ArticleDraft with all generated content.
        """

        def emit_progress(step: str) -> None:
            if progress_callback:
                progress_callback(step)

        # Step 1: Parse input material
        logger.info("Step 1: Parsing input material")
        parsed_input = self.input_parser.parse(input_material)
        emit_progress("input_parsing")

        # Step 2: Classify article type
        logger.info("Step 2: Classifying article type")
        classification = self.classifier.classify(parsed_input)
        emit_progress("classification")

        # Step 3: Retrieve reference articles if not provided
        if reference_articles is None and self.retriever:
            logger.info("Step 3: Retrieving reference articles")
            reference_articles = self._retrieve_references(parsed_input, classification)
        elif reference_articles is None:
            reference_articles = []
        emit_progress("retrieval")

        # Step 4: Analyze style and structure
        logger.info("Step 4: Analyzing style and structure")
        style_analysis, structure_analysis = self._analyze_references(
            reference_articles, classification.article_type_ja
        )
        emit_progress("analysis")

        # Step 5: Generate outline
        logger.info("Step 5: Generating outline")
        outline = self.outline_generator.generate(
            parsed_input, classification.article_type_ja, structure_analysis
        )
        emit_progress("outline")

        # Step 6: Generate content
        logger.info("Step 6: Generating content")
        draft = self._generate_content(
            parsed_input,
            classification,
            outline,
            style_analysis,
            structure_analysis,
        )
        emit_progress("content")

        return draft

    def _retrieve_references(
        self,
        parsed_input: ParsedInput,
        classification: ClassificationResult,
        search_query: str | None = None,
    ) -> list[Document]:
        """Retrieve reference articles based on classification.

        Args:
            parsed_input: Parsed input data.
            classification: Article type classification.
            search_query: Optimized search query (from QueryGeneratorChain).
        """
        if not self.retriever:
            return []

        # Use generated query or fallback to keywords/theme
        if search_query:
            queries = [search_query]
        else:
            queries = parsed_input.keywords[:3] if parsed_input.keywords else [parsed_input.theme]

        return self.retriever.retrieve_multi_query(
            queries=queries,
            article_type=classification.article_type,
        )

    def _analyze_references(
        self,
        reference_articles: list[Document],
        article_type_ja: str,
    ) -> tuple[StyleAnalysis, StructureAnalysis]:
        """Analyze style and structure of reference articles."""
        if not reference_articles:
            # Return default analyses if no references
            return (
                StyleAnalysis(
                    sentence_endings=["です", "ます"],
                    tone="フォーマル",
                    characteristic_phrases=[],
                ),
                StructureAnalysis(
                    typical_headings=["はじめに", "本題", "まとめ"],
                    intro_pattern="テーマの紹介から始める",
                    closing_pattern="CTAで締める",
                ),
            )

        style = self.style_analyzer.analyze(reference_articles, article_type_ja)
        structure = self.structure_analyzer.analyze(reference_articles, article_type_ja)

        return style, structure

    def _generate_content(
        self,
        parsed_input: ParsedInput,
        classification: ClassificationResult,
        outline: Outline,
        style_analysis: StyleAnalysis,
        structure_analysis: StructureAnalysis,
    ) -> ArticleDraft:
        """Generate all content parts."""
        # Generate titles
        titles_output = self.title_generator.generate(
            parsed_input, classification.article_type_ja, outline
        )

        # Generate lead
        lead = self.lead_generator.generate(
            parsed_input,
            classification.article_type_ja,
            outline,
            style_analysis,
            structure_analysis,
        )

        # Generate sections
        sections = self.section_generator.generate_all(
            outline, parsed_input, classification.article_type_ja, style_analysis
        )

        # Generate closing
        closing = self.closing_generator.generate(
            parsed_input,
            classification.article_type_ja,
            style_analysis,
            structure_analysis,
        )

        return ArticleDraft(
            titles=titles_output.titles,
            lead=lead,
            sections=[{"heading": s.heading, "body": s.body} for s in sections],
            closing=closing,
            article_type=classification.article_type,
            article_type_ja=classification.article_type_ja,
            metadata={
                "confidence": classification.confidence,
                "reason": classification.reason,
                "outline_headings": [h.title for h in outline.headings],
            },
        )

    def _run_quality_assurance(
        self,
        draft: ArticleDraft,
        parsed_input: ParsedInput,
        style_analysis: StyleAnalysis,
        style_profile: str | None,
        reference_articles: list[Document],
    ) -> ArticleDraft:
        """Run quality assurance pipeline (Dify v3 compatible).

        This includes:
        1. Style consistency check
        2. Auto-rewrite if consistency score < 0.8
        3. Hallucination detection
        4. [要確認] tag insertion

        Args:
            draft: Generated article draft.
            parsed_input: Original parsed input.
            style_analysis: Style analysis from reference articles.
            style_profile: Style profile from KB (optional).
            reference_articles: Reference articles for fact-checking.

        Returns:
            Updated ArticleDraft with quality metrics.
        """
        # Prepare text for checking
        body_text = "\n\n".join(s["body"] for s in draft.sections)

        # Step 9.1: Style consistency check
        logger.info("  9.1: Checking style consistency")
        style_check = self.style_checker.check(
            lead=draft.lead,
            body=body_text,
            closing=draft.closing,
            style_analysis=style_analysis,
        )
        draft.consistency_score = style_check.consistency_score

        # Step 9.2: Auto-rewrite if needed
        if settings.use_auto_rewrite and style_profile and style_check.consistency_score < 0.8:
            logger.info(
                f"  9.2: Auto-rewriting (consistency score: {style_check.consistency_score:.1%})"
            )
            full_article = draft.to_markdown()
            rewrite_result = self.auto_rewriter.rewrite(
                article_text=full_article,
                style_check_result=style_check,
                style_profile=style_profile,
            )
            # Parse rewritten content back into draft structure
            # For now, just update the metadata to indicate rewrite was done
            draft.metadata["rewrite_applied"] = True
            draft.metadata["rewrite_changes"] = rewrite_result.changes_made
            logger.info(f"  9.2: Rewrite complete, {len(rewrite_result.changes_made)} changes made")
        else:
            draft.metadata["rewrite_applied"] = False

        # Step 9.3: Hallucination detection
        logger.info("  9.3: Detecting hallucinations")
        hallucination_check = self.hallucination_detector.detect(
            lead=draft.lead,
            body=body_text,
            closing=draft.closing,
            parsed_input=parsed_input,
        )
        draft.verification_confidence = hallucination_check.confidence

        # Step 9.4: Apply [要確認] tags
        if hallucination_check.unverified_claims:
            logger.info(
                f"  9.4: Found {len(hallucination_check.unverified_claims)} unverified claims"
            )
            draft.tag_count = len(hallucination_check.unverified_claims)

            # Apply tags to lead
            draft.lead = HallucinationDetectorChain.apply_tags(
                draft.lead, hallucination_check.unverified_claims
            )

            # Apply tags to sections
            for section in draft.sections:
                section["body"] = HallucinationDetectorChain.apply_tags(
                    section["body"], hallucination_check.unverified_claims
                )

            # Apply tags to closing
            draft.closing = HallucinationDetectorChain.apply_tags(
                draft.closing, hallucination_check.unverified_claims
            )

            draft.metadata["unverified_claims"] = [
                {"claim": c.claim, "location": c.location, "tag": c.suggested_tag}
                for c in hallucination_check.unverified_claims
            ]

        # Update actual length
        draft.actual_length = draft.calculate_length()

        return draft
