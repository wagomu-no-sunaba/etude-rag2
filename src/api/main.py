"""FastAPI application for article generation API."""

import asyncio
import concurrent.futures
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.sessions import SessionMiddleware

from src.api.auth import get_current_user, require_auth
from src.api.auth import router as auth_router
from src.api.job_manager import Job, JobStatus, job_manager
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
from src.config import get_settings
from src.verification.hallucination_detector import HallucinationDetectorChain
from src.verification.style_checker import StyleCheckerChain

# Configure logging for Cloud Run
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
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

# Get settings for middleware configuration
settings = get_settings()

# Session middleware (must be added before CORS)
# Uses signed cookies for OAuth state and user session
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key or "dev-secret-key-change-in-production",
    max_age=86400,  # 24 hours
    same_site="lax",
    https_only=settings.is_production,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include auth router
app.include_router(auth_router)

# Configure templates and static files
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.state.templates = templates


@app.get("/")
async def index(request: Request):
    """Render the main index page (requires authentication)."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    return templates.TemplateResponse(request, "index.html", {"user": user})


@app.get("/ui/history")
async def history_list(request: Request):
    """Render the article history list page (requires authentication).

    Args:
        request: FastAPI request.

    Returns:
        HTML page with list of previously generated articles.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)
    # TODO: Fetch articles from database
    articles: list = []
    context = {"articles": articles, "user": user}
    return templates.TemplateResponse(request, "history_list.html", context)


def get_article_by_id(article_id: UUID) -> dict[str, Any] | None:
    """Get an article by its ID from the database.

    Args:
        article_id: UUID of the article to fetch.

    Returns:
        Article data as dict, or None if not found.
    """
    # TODO: Implement actual database lookup
    return None


@app.get("/ui/history/{article_id}")
async def article_detail(request: Request, article_id: UUID):
    """Render the article detail page (requires authentication).

    Args:
        request: FastAPI request.
        article_id: UUID of the article to display.

    Returns:
        HTML page with full article content.

    Raises:
        HTTPException: 404 if article not found.
    """
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=302)

    article = get_article_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    context = {"article": article, "user": user}
    return templates.TemplateResponse(request, "article_detail.html", context)


def delete_article_by_id(article_id: UUID) -> bool:
    """Delete an article by its ID from the database.

    Args:
        article_id: UUID of the article to delete.

    Returns:
        True if deleted successfully, False if not found.
    """
    # TODO: Implement actual database deletion
    return True


@app.delete("/ui/history/{article_id}")
async def delete_article(request: Request, article_id: UUID):
    """Delete an article from history (requires authentication).

    Args:
        request: FastAPI request.
        article_id: UUID of the article to delete.

    Returns:
        Empty response on success.

    Raises:
        HTTPException: 401 if not authenticated, 404 if article not found.
    """
    require_auth(request)

    success = delete_article_by_id(article_id)
    if not success:
        raise HTTPException(status_code=404, detail="Article not found")

    return {"status": "deleted", "id": str(article_id)}


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/ui/generate/stream")
async def ui_generate_start(request: Request):
    """Start an article generation job and return progress partial with job ID.

    This endpoint (requires authentication):
    1. Creates a new job with the form data
    2. Starts the generation in a background task
    3. Returns HTML partial that connects to the SSE stream

    Args:
        request: FastAPI request with form data.

    Returns:
        HTML partial with progress bar and SSE connection to job stream.
    """
    require_auth(request)

    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")

    form_data = await request.form()
    input_material = str(form_data.get("input_material", ""))
    article_type = form_data.get("article_type")
    article_type_str = str(article_type) if article_type else None

    # Create a new job
    job = await job_manager.create_job(
        input_material=input_material,
        article_type=article_type_str,
    )

    # Start generation in background
    asyncio.create_task(_run_generation_job(job))

    return templates.TemplateResponse(
        request,
        "partials/progress.html",
        {"job_id": str(job.id)},
    )


async def _run_generation_job(job: Job) -> None:
    """Run article generation in background and push events to job queue.

    Args:
        job: The job to execute.
    """
    if pipeline is None:
        error_event = ErrorEvent(error="Pipeline not initialized")
        await job_manager.add_event(job.id, error_event)
        await job_manager.signal_complete(job.id)
        return

    await job_manager.update_status(job.id, JobStatus.RUNNING)
    loop = asyncio.get_running_loop()

    def progress_callback(step: str) -> None:
        """Callback to emit progress events from sync thread."""
        step_enum = GenerationStep(step)
        metadata = STEP_METADATA[step_enum]
        event = ProgressEvent(
            step=step_enum,
            step_name=metadata["name_ja"],
            step_number=metadata["order"],
            percentage=metadata["percentage"],
        )
        asyncio.run_coroutine_threadsafe(
            job_manager.add_event(job.id, event),
            loop,
        )

    def run_generation() -> None:
        """Run generation in a thread."""
        try:
            draft = pipeline.generate_with_progress(
                job.input_material,
                progress_callback=progress_callback,
            )
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
            asyncio.run_coroutine_threadsafe(
                job_manager.add_event(job.id, complete_event),
                loop,
            )
        except Exception as e:
            logger.exception("Error in job generation")
            error_event = ErrorEvent(error=str(e))
            asyncio.run_coroutine_threadsafe(
                job_manager.add_event(job.id, error_event),
                loop,
            )
        finally:
            asyncio.run_coroutine_threadsafe(
                job_manager.signal_complete(job.id),
                loop,
            )

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        await loop.run_in_executor(executor, run_generation)
    finally:
        executor.shutdown(wait=False)


@app.get("/ui/generate/stream/{job_id}")
async def ui_generate_stream(request: Request, job_id: UUID) -> EventSourceResponse:
    """Stream generation progress for a specific job via SSE (requires authentication).

    Args:
        request: FastAPI request for disconnect detection.
        job_id: UUID of the job to stream.

    Returns:
        EventSourceResponse streaming progress and result events.

    Raises:
        HTTPException: 401 if not authenticated, 404 if job not found.
    """
    require_auth(request)

    job = await job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    queue = job_manager.get_queue(job_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="Job queue not found")

    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        # First, replay any existing events for late joiners
        for event in job.events:
            if isinstance(event, ProgressEvent):
                yield {
                    "event": SSEEventType.PROGRESS.value,
                    "data": event.model_dump_json(),
                }
            elif isinstance(event, CompleteEvent):
                yield {
                    "event": SSEEventType.COMPLETE.value,
                    "data": event.model_dump_json(),
                }
            elif isinstance(event, ErrorEvent):
                yield {
                    "event": SSEEventType.ERROR.value,
                    "data": event.model_dump_json(),
                }

        # If job is already completed, we're done
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            return

        # Stream new events as they arrive
        while True:
            if await request.is_disconnected():
                logger.info(f"Client disconnected from job {job_id}")
                break

            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except TimeoutError:
                continue

            if event is None:
                # Generation complete
                break

            if isinstance(event, ProgressEvent):
                yield {
                    "event": SSEEventType.PROGRESS.value,
                    "data": event.model_dump_json(),
                }
            elif isinstance(event, CompleteEvent):
                yield {
                    "event": SSEEventType.COMPLETE.value,
                    "data": event.model_dump_json(),
                }
            elif isinstance(event, ErrorEvent):
                yield {
                    "event": SSEEventType.ERROR.value,
                    "data": event.model_dump_json(),
                }

    return EventSourceResponse(event_generator())


@app.post("/ui/generate")
async def ui_generate(request: Request):
    """Generate article and return HTML partial for HTMX (requires authentication).

    Args:
        request: FastAPI request with form data.

    Returns:
        HTML partial with generated article content.
    """
    require_auth(request)

    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")

    form_data = await request.form()
    input_material = form_data.get("input_material", "")

    try:
        draft = pipeline.generate(str(input_material))

        return templates.TemplateResponse(
            request,
            "partials/result.html",
            {
                "titles": draft.titles,
                "lead": draft.lead,
                "sections": draft.sections,
                "closing": draft.closing,
                "article_type": draft.article_type,
                "article_type_ja": draft.article_type_ja,
                "markdown": draft.to_markdown(),
            },
        )
    except Exception as e:
        logger.exception("Error generating article via UI")
        return templates.TemplateResponse(
            request,
            "partials/result.html",
            {
                "titles": [],
                "lead": f"エラーが発生しました: {e}",
                "sections": [],
                "closing": "",
                "article_type": "",
                "article_type_ja": "",
                "markdown": "",
            },
        )


@app.post(
    "/generate",
    response_model=GenerateResponse,
    responses={500: {"model": ErrorResponse}},
)
async def generate_article(request: Request, body: GenerateRequest) -> GenerateResponse:
    """Generate an article draft from input material (requires authentication).

    Args:
        request: FastAPI request.
        body: Generation request with input material.

    Returns:
        Generated article draft with titles, lead, sections, and closing.
    """
    require_auth(request)

    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")

    try:
        draft = pipeline.generate(body.input_material)

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
async def verify_content(request: Request, body: VerifyRequest) -> VerifyResponse:
    """Verify generated content for hallucinations and style consistency (requires authentication).

    Args:
        request: FastAPI request.
        body: Verification request with content and original input.

    Returns:
        Verification results for hallucination and style checks.
    """
    require_auth(request)

    if input_parser is None or hallucination_detector is None or style_checker is None:
        raise HTTPException(status_code=500, detail="Verifiers not initialized")

    try:
        # Parse input material for fact checking
        parsed_input = input_parser.parse(body.input_material)

        # Run hallucination detection
        hallucination_result = await hallucination_detector.adetect(
            lead=body.lead,
            body=body.body,
            closing=body.closing,
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
            lead=body.lead,
            body=body.body,
            closing=body.closing,
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
async def search_articles(request: Request, body: SearchRequest) -> list[SearchResult]:
    """Search for reference articles (requires authentication).

    Args:
        request: FastAPI request.
        body: Search request with query and filters.

    Returns:
        List of matching articles.
    """
    require_auth(request)

    # Note: This endpoint requires a configured retriever
    # For now, return empty list as retriever setup needs database connection
    logger.warning("Search endpoint called but retriever not configured")
    return []


@app.post("/generate/stream")
async def generate_article_stream(
    request: Request,
    generate_request: GenerateRequest,
) -> EventSourceResponse:
    """Generate an article draft with SSE streaming progress updates (requires authentication).

    Sends progress events as each step completes, then a complete event
    with the final result.

    Args:
        request: FastAPI request for disconnect detection.
        generate_request: Generation request with input material.

    Returns:
        EventSourceResponse streaming progress and result events.
    """
    require_auth(request)

    if pipeline is None:
        raise HTTPException(status_code=500, detail="Pipeline not initialized")

    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        progress_queue: asyncio.Queue[ProgressEvent | None] = asyncio.Queue()
        result_holder: dict[str, Any] = {}
        error_holder: dict[str, Exception | None] = {"error": None}
        current_step_holder: dict[str, str | None] = {"step": None}

        # Capture the event loop reference before entering threads
        loop = asyncio.get_running_loop()

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
            # Thread-safe queue put using captured loop reference
            loop.call_soon_threadsafe(progress_queue.put_nowait, event)

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
                # Signal completion using captured loop reference
                loop.call_soon_threadsafe(progress_queue.put_nowait, None)

        # Start generation in background thread
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
