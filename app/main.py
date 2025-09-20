from __future__ import annotations

import logging
from typing import List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .asr_client import ASRClient
from .database import AsyncSessionLocal, init_db
from .models import AudioChunk, Job, JobStatus
from .schemas import (
    ProcessTranscriptionTask,
    TranscribeRequest,
    TranscribeResponse,
    TranscriptResult,
    build_transcript_result,
)
from .task_queue import TaskQueueError, TranscriptionTaskQueue
from .worker import JobProcessor

app = FastAPI(title="Audio Transcription Service")


asr_client = ASRClient(
    max_concurrency=100,
    transient_failure_rate=0.05,
    permanent_failures={"bad_audio_segment"},
)
job_processor = JobProcessor(asr_client)
task_queue: TranscriptionTaskQueue | None = None


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


def get_task_queue() -> TranscriptionTaskQueue:
    if task_queue is None:
        raise RuntimeError("Task queue is not initialized")
    return task_queue


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    global task_queue
    task_queue = TranscriptionTaskQueue()
    job_ids = await job_processor.resume_incomplete_jobs()
    for job_id in job_ids:
        try:
            await run_in_threadpool(get_task_queue().enqueue, job_id)
        except TaskQueueError:
            logging.exception("Failed to enqueue transcription job %s during startup", job_id)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await job_processor.stop()
    global task_queue
    task_queue = None


@app.post("/transcribe", response_model=TranscribeResponse, status_code=202)
async def create_transcription_job(
    request: TranscribeRequest, session=Depends(get_session)
) -> TranscribeResponse:
    job_id = str(uuid4())
    job = Job(id=job_id, user_id=request.userId, status=JobStatus.QUEUED)
    session.add(job)
    for index, audio_path in enumerate(request.audioChunkPaths):
        chunk = AudioChunk(job_id=job_id, sequence=index, audio_path=audio_path)
        session.add(chunk)
    await session.commit()
    try:
        queue = get_task_queue()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Task queue is not configured",
        ) from exc
    try:
        await run_in_threadpool(queue.enqueue, job_id)
    except TaskQueueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to enqueue transcription task",
        ) from exc
    return TranscribeResponse(jobId=job_id)


@app.post("/tasks/process-transcription", status_code=204)
async def process_transcription_task(payload: ProcessTranscriptionTask) -> Response:
    await job_processor.process_job(payload.jobId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/transcript/{job_id}", response_model=TranscriptResult)
async def get_transcript(job_id: str, session=Depends(get_session)) -> TranscriptResult:
    result = await session.execute(
        select(Job)
        .options(selectinload(Job.chunks))
        .where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return build_transcript_result(job)


@app.get("/transcript/search", response_model=List[TranscriptResult])
async def search_transcripts(
    jobStatus: Optional[JobStatus] = Query(default=None),
    userId: Optional[str] = Query(default=None),
    session=Depends(get_session),
) -> List[TranscriptResult]:
    query = select(Job).options(selectinload(Job.chunks))
    if jobStatus is not None:
        query = query.where(Job.status == jobStatus)
    if userId is not None:
        query = query.where(Job.user_id == userId)
    result = await session.execute(query.order_by(Job.created_at.desc()))
    jobs = result.scalars().unique().all()
    return [build_transcript_result(job) for job in jobs]
