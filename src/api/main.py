"""FastAPI application for article generation API."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.api.models import (
    ErrorResponse,
    GenerateRequest,
    GenerateResponse,
    HallucinationResult,
    SearchRequest,
    SearchResult,
    StyleResult,
    VerifyRequest,
    VerifyResponse,
)
from src.chains.article_chain import ArticleGenerationPipeline
from src.chains.input_parser import InputParserChain
from src.verification.hallucination_detector import HallucinationDetectorChain
from src.verification.style_checker import StyleCheckerChain

logger = logging.getLogger(__name__)

# Global instances (initialized on startup)
pipeline: ArticleGenerationPipeline | None = None
input_parser: InputParserChain | None = None
hallucination_detector: HallucinationDetectorChain | None = None
style_checker: StyleCheckerChain | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize and cleanup resources."""
    global pipeline, input_parser, hallucination_detector, style_checker

    logger.info("Initializing API resources...")
    pipeline = ArticleGenerationPipeline()
    input_parser = InputParserChain()
    hallucination_detector = HallucinationDetectorChain()
    style_checker = StyleCheckerChain()

    yield

    logger.info("Cleaning up API resources...")


app = FastAPI(
    title="Note Article Draft Generator API",
    description="RAG-based article draft generation for recruiting note articles",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post(
    "/generate",
    response_model=GenerateResponse,
    responses={500: {"model": ErrorResponse}},
)
async def generate_article(request: GenerateRequest) -> GenerateResponse:
    """Generate an article draft from input material.

    Args:
        request: Generation request with input material.

    Returns:
        Generated article draft with titles, lead, sections, and closing.
    """
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")

    try:
        draft = pipeline.generate(request.input_material)

        return GenerateResponse(
            titles=draft.titles,
            lead=draft.lead,
            sections=draft.sections,
            closing=draft.closing,
            article_type=draft.article_type,
            article_type_ja=draft.article_type_ja,
            markdown=draft.to_markdown(),
        )
    except Exception as e:
        logger.exception("Error generating article")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post(
    "/verify",
    response_model=VerifyResponse,
    responses={500: {"model": ErrorResponse}},
)
async def verify_content(request: VerifyRequest) -> VerifyResponse:
    """Verify generated content for hallucinations and style consistency.

    Args:
        request: Verification request with content and original input.

    Returns:
        Verification results for hallucination and style checks.
    """
    if input_parser is None or hallucination_detector is None or style_checker is None:
        raise HTTPException(status_code=500, detail="Verifiers not initialized")

    try:
        # Parse input material for fact checking
        parsed_input = input_parser.parse(request.input_material)

        # Run hallucination detection
        hallucination_result = await hallucination_detector.adetect(
            lead=request.lead,
            body=request.body,
            closing=request.closing,
            parsed_input=parsed_input,
        )

        # For style checking, we need style analysis - use defaults for now
        from src.chains.style_analyzer import StyleAnalysis

        default_style = StyleAnalysis(
            sentence_endings=["です", "ます"],
            tone="フォーマル",
            characteristic_phrases=[],
        )

        style_result = await style_checker.acheck(
            lead=request.lead,
            body=request.body,
            closing=request.closing,
            style_analysis=default_style,
        )

        return VerifyResponse(
            hallucination=HallucinationResult(
                has_hallucination=hallucination_result.has_hallucination,
                confidence=hallucination_result.confidence,
                verified_facts=hallucination_result.verified_facts,
                unverified_claims=[
                    {
                        "claim": c.claim,
                        "location": c.location,
                        "tag": c.suggested_tag,
                    }
                    for c in hallucination_result.unverified_claims
                ],
            ),
            style=StyleResult(
                is_consistent=style_result.is_consistent,
                consistency_score=style_result.consistency_score,
                issues=[
                    {
                        "location": i.location,
                        "issue": i.issue,
                        "suggestion": i.suggestion,
                    }
                    for i in style_result.issues
                ],
            ),
        )
    except Exception as e:
        logger.exception("Error verifying content")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post(
    "/search",
    response_model=list[SearchResult],
    responses={500: {"model": ErrorResponse}},
)
async def search_articles(request: SearchRequest) -> list[SearchResult]:
    """Search for reference articles.

    Args:
        request: Search request with query and filters.

    Returns:
        List of matching articles.
    """
    # Note: This endpoint requires a configured retriever
    # For now, return empty list as retriever setup needs database connection
    logger.warning("Search endpoint called but retriever not configured")
    return []
