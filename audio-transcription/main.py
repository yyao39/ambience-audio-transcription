from __future__ import annotations

import logging
from typing import List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .asr_client import ASRClient
from .database import AsyncSessionLocal, init_db
from .models import AudioChunk, Job, JobStatus
from .schemas import (
    TranscribeRequest,
    TranscribeResponse,
    TranscriptResult,
    build_transcript_result,
)
from .task_queue import create_http_task

# Imports the Cloud Logging client library
import google.cloud.logging

# Instantiates a client
client = google.cloud.logging.Client()

# Retrieves a Cloud Logging handler based on the environment
# you're running in and integrates the handler with the
# Python logging module. By default this captures all logs
# at INFO level and higher
client.setup_logging()

app = FastAPI(title="Audio Transcription Service")


asr_client = ASRClient(
    max_concurrency=100,
    transient_failure_rate=0.05,
    permanent_failures={"bad_audio_segment"},
)


async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    # await job_processor.start()
    # await job_processor.resume_incomplete_jobs()
    pass


@app.on_event("shutdown")
async def on_shutdown() -> None:
    # await job_processor.stop()
    pass


@app.post("/transcribe", response_model=TranscribeResponse, status_code=202)
async def create_transcription_job(
    request: TranscribeRequest
) -> TranscribeResponse:
    job_id = str(uuid4())

    for index, audio_path in enumerate(request.audioChunkPaths):
        task = create_http_task(
            project="ambience-audio-transcription",
            location="us-west1",
            queue="speech-recognition-task-queue",
            url="https://asr-test-847346105312.us-west1.run.app",
            json_payload={
                "audio_path": audio_path
            }
        )
        logging.info("ASR task for {}: {}".format(audio_path, task.name))

    return TranscribeResponse(jobId=job_id, taskName=task.name)


@app.get("/transcript/{job_id}", response_model=TranscriptResult)
async def get_transcript(
    job_id: str,
    session=Depends(get_session)
) -> TranscriptResult:
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
