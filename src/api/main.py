"""FastAPI application for article generation API."""

import asyncio
import concurrent.futures
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

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
from src.api.sse_models import (
    STEP_METADATA,
    CompleteEvent,
    ErrorEvent,
    GenerationStep,
    ProgressEvent,
    SSEEventType,
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


@app.post("/generate/stream")
async def generate_article_stream(
    request: Request,
    generate_request: GenerateRequest,
) -> EventSourceResponse:
    """Generate an article draft with SSE streaming progress updates.

    Sends progress events as each step completes, then a complete event
    with the final result.

    Args:
        request: FastAPI request for disconnect detection.
        generate_request: Generation request with input material.

    Returns:
        EventSourceResponse streaming progress and result events.
    """
    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")

    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        progress_queue: asyncio.Queue[ProgressEvent | None] = asyncio.Queue()
        result_holder: dict[str, Any] = {}
        error_holder: dict[str, Exception | None] = {"error": None}
        current_step_holder: dict[str, str | None] = {"step": None}

        def progress_callback(step: str) -> None:
            """Callback to emit progress events from sync thread."""
            current_step_holder["step"] = step
            step_enum = GenerationStep(step)
            metadata = STEP_METADATA[step_enum]
            event = ProgressEvent(
                step=step_enum,
                step_name=metadata["name_ja"],
                step_number=metadata["order"],
                percentage=metadata["percentage"],
            )
            # Thread-safe queue put
            asyncio.get_event_loop().call_soon_threadsafe(
                progress_queue.put_nowait, event
            )

        def run_generation() -> None:
            """Run generation in a thread."""
            try:
                draft = pipeline.generate_with_progress(
                    generate_request.input_material,
                    progress_callback=progress_callback,
                )
                result_holder["draft"] = draft
            except Exception as e:
                logger.exception("Error in streaming generation")
                error_holder["error"] = e
            finally:
                # Signal completion
                asyncio.get_event_loop().call_soon_threadsafe(
                    progress_queue.put_nowait, None
                )

        # Start generation in background thread
        loop = asyncio.get_event_loop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        loop.run_in_executor(executor, run_generation)

        try:
            # Stream progress events
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    logger.info("Client disconnected, stopping generation stream")
                    break

                try:
                    event = await asyncio.wait_for(
                        progress_queue.get(),
                        timeout=1.0,
                    )
                except TimeoutError:
                    continue

                if event is None:
                    # Generation complete
                    break

                yield {
                    "event": SSEEventType.PROGRESS.value,
                    "data": event.model_dump_json(),
                }

            # Check for errors
            if error_holder["error"]:
                error_event = ErrorEvent(
                    error=str(error_holder["error"]),
                    step=GenerationStep(current_step_holder["step"])
                    if current_step_holder["step"]
                    else None,
                )
                yield {
                    "event": SSEEventType.ERROR.value,
                    "data": error_event.model_dump_json(),
                }
                return

            # Send complete event with result
            if "draft" in result_holder:
                draft = result_holder["draft"]
                complete_event = CompleteEvent(
                    result={
                        "titles": draft.titles,
                        "lead": draft.lead,
                        "sections": draft.sections,
                        "closing": draft.closing,
                        "article_type": draft.article_type,
                        "article_type_ja": draft.article_type_ja,
                        "markdown": draft.to_markdown(),
                    }
                )
                yield {
                    "event": SSEEventType.COMPLETE.value,
                    "data": complete_event.model_dump_json(),
                }
        finally:
            executor.shutdown(wait=False)

    return EventSourceResponse(event_generator())
