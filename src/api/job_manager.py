"""Job manager for async article generation."""

import asyncio
import time
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from src.api.sse_models import CompleteEvent, ErrorEvent, ProgressEvent


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    """Represents an article generation job."""

    id: UUID = Field(default_factory=uuid4)
    status: JobStatus = Field(default=JobStatus.PENDING)
    input_material: str = Field(description="Input material for generation")
    article_type: str | None = Field(default=None, description="Optional article type override")
    created_at: float = Field(default_factory=time.time)
    events: list[ProgressEvent | CompleteEvent | ErrorEvent] = Field(default_factory=list)
    result: dict[str, Any] | None = Field(default=None)
    error: str | None = Field(default=None)

    class Config:
        arbitrary_types_allowed = True


class JobManager:
    """Manages article generation jobs.

    Stores jobs in memory with their event queues for SSE streaming.
    Jobs are automatically cleaned up after TTL expires.
    """

    TTL_SECONDS = 3600  # 1 hour

    # Type alias for event queue
    _EventQueue = asyncio.Queue[ProgressEvent | CompleteEvent | ErrorEvent | None]

    def __init__(self) -> None:
        self._jobs: dict[UUID, Job] = {}
        self._queues: dict[UUID, JobManager._EventQueue] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, input_material: str, article_type: str | None = None) -> Job:
        """Create a new job and return it.

        Args:
            input_material: The input text for article generation.
            article_type: Optional article type override.

        Returns:
            The created Job instance.
        """
        async with self._lock:
            job = Job(input_material=input_material, article_type=article_type)
            self._jobs[job.id] = job
            self._queues[job.id] = asyncio.Queue()
            return job

    async def get_job(self, job_id: UUID) -> Job | None:
        """Get a job by ID.

        Args:
            job_id: The job UUID.

        Returns:
            The Job if found, None otherwise.
        """
        self._cleanup_old_jobs()
        return self._jobs.get(job_id)

    def get_queue(self, job_id: UUID) -> asyncio.Queue | None:
        """Get the event queue for a job.

        Args:
            job_id: The job UUID.

        Returns:
            The asyncio.Queue for SSE events, or None if not found.
        """
        return self._queues.get(job_id)

    async def update_status(self, job_id: UUID, status: JobStatus) -> None:
        """Update job status.

        Args:
            job_id: The job UUID.
            status: The new status.
        """
        if job := self._jobs.get(job_id):
            job.status = status

    async def add_event(
        self,
        job_id: UUID,
        event: ProgressEvent | CompleteEvent | ErrorEvent,
    ) -> None:
        """Add an event to the job and push to queue.

        Args:
            job_id: The job UUID.
            event: The event to add.
        """
        if job := self._jobs.get(job_id):
            job.events.append(event)

            if isinstance(event, CompleteEvent):
                job.status = JobStatus.COMPLETED
                job.result = event.result
            elif isinstance(event, ErrorEvent):
                job.status = JobStatus.FAILED
                job.error = event.error

        if queue := self._queues.get(job_id):
            await queue.put(event)

    async def signal_complete(self, job_id: UUID) -> None:
        """Signal that job streaming is complete.

        Args:
            job_id: The job UUID.
        """
        if queue := self._queues.get(job_id):
            await queue.put(None)

    def _cleanup_old_jobs(self) -> None:
        """Remove jobs older than TTL."""
        now = time.time()
        expired = [
            job_id for job_id, job in self._jobs.items() if now - job.created_at > self.TTL_SECONDS
        ]
        for job_id in expired:
            self._jobs.pop(job_id, None)
            self._queues.pop(job_id, None)


# Global job manager instance
job_manager = JobManager()
