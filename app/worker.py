from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from .asr_client import ASRClient, PermanentASRError, TransientASRError
from .database import AsyncSessionLocal
from .models import AudioChunk, ChunkStatus, Job, JobStatus


class JobProcessor:
    """Background worker that processes transcription jobs."""

    def __init__(
        self,
        asr_client: ASRClient,
        *,
        worker_count: int = 4,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self._asr_client = asr_client
        self._worker_count = worker_count
        self._max_retries = max_retries
        self._retry_backoff_seconds = retry_backoff_seconds
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._pending_jobs: set[str] = set()
        self._workers: List[asyncio.Task[None]] = []
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        self._shutdown_event.clear()
        for _ in range(self._worker_count):
            task = asyncio.create_task(self._worker_loop())
            self._workers.append(task)

    async def stop(self) -> None:
        self._shutdown_event.set()
        for task in self._workers:
            task.cancel()
        for task in self._workers:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._workers.clear()

    async def enqueue_job(self, job_id: str) -> None:
        if job_id in self._pending_jobs:
            return
        self._pending_jobs.add(job_id)
        await self._queue.put(job_id)

    async def resume_incomplete_jobs(self) -> List[str]:
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(AudioChunk)
                .where(AudioChunk.status == ChunkStatus.IN_PROGRESS)
                .values(status=ChunkStatus.PENDING)
            )
            await session.commit()
            result = await session.execute(
                select(Job.id).where(Job.status.in_([JobStatus.QUEUED, JobStatus.IN_PROGRESS]))
            )
            job_ids = [row[0] for row in result.all()]
        return job_ids

    async def process_job(self, job_id: str) -> None:
        await self._process_job(job_id)

    async def _worker_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            try:
                await self._process_job(job_id)
            finally:
                self._pending_jobs.discard(job_id)
                self._queue.task_done()

    async def _process_job(self, job_id: str) -> None:
        chunk_ids = await self._prepare_job(job_id)
        if not chunk_ids:
            return
        job_failed = False
        for chunk_id in chunk_ids:
            success = await self._process_chunk(chunk_id)
            if not success:
                job_failed = True
        await self._finalize_job(job_id, job_failed)

    async def _prepare_job(self, job_id: str) -> Sequence[int]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Job)
                .options(selectinload(Job.chunks))
                .where(Job.id == job_id)
            )
            job = result.scalar_one_or_none()
            if job is None:
                return []
            if job.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
                return []
            job.status = JobStatus.IN_PROGRESS
            job.updated_at = datetime.utcnow()
            await session.commit()
            return [chunk.id for chunk in job.chunks]

    async def _process_chunk(self, chunk_id: int) -> bool:
        while True:
            preparation = await self._prepare_chunk(chunk_id)
            if preparation is None:
                return False
            if preparation["state"] == "completed":
                return True
            if preparation["state"] == "failed":
                return False
            attempt = preparation["attempt"]
            audio_path = preparation["audio_path"]
            try:
                transcript = await self._asr_client.transcribe(audio_path)
            except TransientASRError as exc:
                should_retry = await self._handle_transient_failure(chunk_id, str(exc), attempt)
                if not should_retry:
                    return False
                await asyncio.sleep(self._retry_backoff_seconds * attempt)
                continue
            except PermanentASRError as exc:
                await self._mark_chunk_permanent_failure(chunk_id, str(exc))
                return False
            else:
                await self._mark_chunk_completed(chunk_id, transcript)
                return True

    async def _prepare_chunk(self, chunk_id: int) -> dict | None:
        async with AsyncSessionLocal() as session:
            chunk = await session.get(AudioChunk, chunk_id)
            if chunk is None:
                return None
            if chunk.status == ChunkStatus.COMPLETED:
                return {"state": "completed"}
            if chunk.status == ChunkStatus.PERMANENT_FAILURE:
                return {"state": "failed"}
            chunk.status = ChunkStatus.IN_PROGRESS
            chunk.attempts += 1
            chunk.last_error = None
            chunk.updated_at = datetime.utcnow()
            audio_path = chunk.audio_path
            attempt = chunk.attempts
            await session.commit()
            return {"state": "processing", "audio_path": audio_path, "attempt": attempt}

    async def _handle_transient_failure(self, chunk_id: int, error: str, attempt: int) -> bool:
        async with AsyncSessionLocal() as session:
            chunk = await session.get(AudioChunk, chunk_id)
            if chunk is None:
                return False
            chunk.last_error = error
            if attempt >= self._max_retries:
                chunk.status = ChunkStatus.PERMANENT_FAILURE
                chunk.updated_at = datetime.utcnow()
                await session.commit()
                return False
            chunk.status = ChunkStatus.TRANSIENT_ERROR
            chunk.updated_at = datetime.utcnow()
            await session.commit()
        return True

    async def _mark_chunk_permanent_failure(self, chunk_id: int, error: str) -> None:
        async with AsyncSessionLocal() as session:
            chunk = await session.get(AudioChunk, chunk_id)
            if chunk is None:
                return
            chunk.status = ChunkStatus.PERMANENT_FAILURE
            chunk.last_error = error
            chunk.updated_at = datetime.utcnow()
            await session.commit()

    async def _mark_chunk_completed(self, chunk_id: int, transcript: str) -> None:
        async with AsyncSessionLocal() as session:
            chunk = await session.get(AudioChunk, chunk_id, options=(selectinload(AudioChunk.job),))
            if chunk is None:
                return
            chunk.status = ChunkStatus.COMPLETED
            chunk.transcript_text = transcript
            chunk.updated_at = datetime.utcnow()
            chunk.job.updated_at = datetime.utcnow()
            await session.commit()

    async def _finalize_job(self, job_id: str, job_failed: bool) -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Job)
                .options(selectinload(Job.chunks))
                .where(Job.id == job_id)
            )
            job = result.scalar_one_or_none()
            if job is None:
                return
            has_permanent_failure = any(
                chunk.status == ChunkStatus.PERMANENT_FAILURE for chunk in job.chunks
            )
            all_completed = all(chunk.status == ChunkStatus.COMPLETED for chunk in job.chunks)
            if has_permanent_failure or job_failed:
                job.status = JobStatus.FAILED
            elif all_completed:
                job.status = JobStatus.COMPLETED
            else:
                job.status = JobStatus.IN_PROGRESS
            transcripts = [chunk.transcript_text for chunk in job.chunks if chunk.transcript_text]
            job.transcript_text = "\n".join(transcripts)
            if job.status in {JobStatus.COMPLETED, JobStatus.FAILED}:
                job.completed_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            await session.commit()
