"""Article generation orchestration chain."""

import logging
from collections.abc import Callable
from typing import Any

from langchain_core.documents import Document
from pydantic import BaseModel, Field

from src.chains.article_classifier import ArticleClassifierChain, ClassificationResult
from src.chains.content_generators import (
    ClosingGeneratorChain,
    LeadGeneratorChain,
    SectionGeneratorChain,
    TitleGeneratorChain,
)
from src.chains.input_parser import InputParserChain, ParsedInput
from src.chains.outline_generator import Outline, OutlineGeneratorChain
from src.chains.structure_analyzer import StructureAnalysis, StructureAnalyzerChain
from src.chains.style_analyzer import StyleAnalysis, StyleAnalyzerChain
from src.retriever.article_retriever import ArticleRetriever

logger = logging.getLogger(__name__)


class ArticleDraft(BaseModel):
    """Complete article draft output."""

    titles: list[str] = Field(description="タイトル案（3つ）")
    lead: str = Field(description="リード文")
    sections: list[dict[str, str]] = Field(description="本文セクション")
    closing: str = Field(description="締めの文章")
    article_type: str = Field(description="記事タイプ")
    article_type_ja: str = Field(description="記事タイプ（日本語）")
    metadata: dict[str, Any] = Field(default_factory=dict, description="メタデータ")

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
        total_length = (
            len(self.lead) + sum(len(s["body"]) for s in self.sections) + len(self.closing)
        )
        lines.append(f"**総文字数**: 約{total_length}字")

        return "\n".join(lines)


class ArticleGenerationPipeline:
    """Full pipeline for generating article drafts.

    This pipeline orchestrates all chains:
    1. Input parsing
    2. Article type classification
    3. Reference article retrieval
    4. Style and structure analysis
    5. Outline generation
    6. Content generation (title, lead, sections, closing)
    """

    def __init__(
        self,
        retriever: ArticleRetriever | None = None,
        input_parser: InputParserChain | None = None,
        classifier: ArticleClassifierChain | None = None,
        style_analyzer: StyleAnalyzerChain | None = None,
        structure_analyzer: StructureAnalyzerChain | None = None,
        outline_generator: OutlineGeneratorChain | None = None,
        title_generator: TitleGeneratorChain | None = None,
        lead_generator: LeadGeneratorChain | None = None,
        section_generator: SectionGeneratorChain | None = None,
        closing_generator: ClosingGeneratorChain | None = None,
    ):
        """Initialize the pipeline with optional custom components."""
        self.retriever = retriever
        self.input_parser = input_parser or InputParserChain()
        self.classifier = classifier or ArticleClassifierChain()
        self.style_analyzer = style_analyzer or StyleAnalyzerChain()
        self.structure_analyzer = structure_analyzer or StructureAnalyzerChain()
        self.outline_generator = outline_generator or OutlineGeneratorChain()
        self.title_generator = title_generator or TitleGeneratorChain()
        self.lead_generator = lead_generator or LeadGeneratorChain()
        self.section_generator = section_generator or SectionGeneratorChain()
        self.closing_generator = closing_generator or ClosingGeneratorChain()

    def generate(
        self,
        input_material: str,
        reference_articles: list[Document] | None = None,
    ) -> ArticleDraft:
        """Generate a complete article draft.

        Args:
            input_material: Raw input material from user.
            reference_articles: Optional pre-fetched reference articles.
                If None and retriever is configured, articles will be retrieved.

        Returns:
            ArticleDraft with all generated content.
        """
        # Step 1: Parse input material
        logger.info("Step 1: Parsing input material")
        parsed_input = self.input_parser.parse(input_material)

        # Step 2: Classify article type
        logger.info("Step 2: Classifying article type")
        classification = self.classifier.classify(parsed_input)

        # Step 3: Retrieve reference articles if not provided
        if reference_articles is None and self.retriever:
            logger.info("Step 3: Retrieving reference articles")
            reference_articles = self._retrieve_references(parsed_input, classification)
        elif reference_articles is None:
            reference_articles = []

        # Step 4: Analyze style and structure
        logger.info("Step 4: Analyzing style and structure")
        style_analysis, structure_analysis = self._analyze_references(
            reference_articles, classification.article_type_ja
        )

        # Step 5: Generate outline
        logger.info("Step 5: Generating outline")
        outline = self.outline_generator.generate(
            parsed_input, classification.article_type_ja, structure_analysis
        )

        # Step 6: Generate content
        logger.info("Step 6: Generating content")
        draft = self._generate_content(
            parsed_input,
            classification,
            outline,
            style_analysis,
            structure_analysis,
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
    ) -> list[Document]:
        """Retrieve reference articles based on classification."""
        if not self.retriever:
            return []

        # Generate search queries from keywords
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
