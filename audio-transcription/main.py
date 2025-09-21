from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from google.cloud import firestore

from .asr_client import ASRClient
from .database import get_collection, init_db
from .models import ChunkStatus, JobStatus
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
logging_client = google.cloud.logging.Client()

# Retrieves a Cloud Logging handler based on the environment
# you're running in and integrates the handler with the
# Python logging module. By default this captures all logs
# at INFO level and higher
logging_client.setup_logging()

app = FastAPI(title="Audio Transcription Service")


asr_client = ASRClient(
    max_concurrency=100,
    transient_failure_rate=0.05,
    permanent_failures={"bad_audio_segment"},
)


async def get_transcription_collection():
    """Dependency that yields the Firestore collection for transcripts."""

    yield get_collection()


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
    request: TranscribeRequest,
    collection=Depends(get_transcription_collection),
) -> TranscribeResponse:
    job_id = str(uuid4())
    now = datetime.utcnow()
    chunk_statuses = {
        audio_path: ChunkStatus.PENDING.value for audio_path in request.audioChunkPaths
    }

    await collection.document(job_id).set(
        {
            "jobId": job_id,
            "userId": request.userId,
            "jobStatus": JobStatus.QUEUED.value,
            "transcriptText": "",
            "chunkStatuses": chunk_statuses,
            "audioChunkPaths": request.audioChunkPaths,
            "completedTime": None,
            "createdAt": now,
            "updatedAt": now,
        }
    )

    task_name = ""
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
        task_name = task.name

    return TranscribeResponse(jobId=job_id, taskName=task_name)


@app.get("/transcript/{job_id}", response_model=TranscriptResult)
async def get_transcript(
    job_id: str,
    collection=Depends(get_transcription_collection),
) -> TranscriptResult:
    snapshot = await collection.document(job_id).get()
    if not snapshot.exists:
        raise HTTPException(status_code=404, detail="Job not found")
    job_data = snapshot.to_dict() or {}
    job_data.setdefault("jobId", job_id)
    return build_transcript_result(job_data)


@app.get("/transcript/search", response_model=List[TranscriptResult])
async def search_transcripts(
    jobStatus: Optional[JobStatus] = Query(default=None),
    userId: Optional[str] = Query(default=None),
    collection=Depends(get_transcription_collection),
) -> List[TranscriptResult]:
    query = collection
    if jobStatus is not None:
        query = query.where("jobStatus", "==", jobStatus.value)
    if userId is not None:
        query = query.where("userId", "==", userId)
    query = query.order_by("createdAt", direction=firestore.Query.DESCENDING)

    jobs: List[TranscriptResult] = []
    async for snapshot in query.stream():
        job_data = snapshot.to_dict() or {}
        job_data.setdefault("jobId", snapshot.id)
        jobs.append(build_transcript_result(job_data))
    return jobs
