from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from google.cloud import firestore

from .database import AudioTranscriptions, init_db
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
collection = AudioTranscriptions.get_collection()


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    pass


@app.on_event("shutdown")
async def on_shutdown() -> None:
    pass


@app.post("/transcribe", response_model=TranscribeResponse, status_code=202)
async def create_transcription_job(
    request: TranscribeRequest
) -> TranscribeResponse:
    tasks = {}
    job_id = str(uuid4())
    for index, audio_path in enumerate(request.audioChunkPaths):
        now = datetime.now()
        task_id = str(uuid4())
        await collection.document(task_id).set(
            {
                "jobId": job_id,
                "userId": request.userId,
                "jobStatus": JobStatus.QUEUED.value,
                "transcriptText": "",
                "chunkStatuses": ChunkStatus.PENDING.value,
                "audioChunkPath": audio_path,
                "completedTime": None,
                "createdAt": now,
                "updatedAt": now,
            }
        )
        task = create_http_task(
            project="ambience-audio-transcription",
            location="us-west1",
            queue="speech-recognition-task-queue",
            url="https://asr-test-847346105312.us-west1.run.app",
            json_payload={
                "audio_path": audio_path,
                "task_id": task_id
            }
        )
        logging.info("ASR task for {}: {}".format(audio_path, task.name))
        tasks[task_id] = task.name

    return TranscribeResponse(jobId=job_id, tasks=tasks)


@app.get("/transcript/{job_id}", response_model=TranscriptResult)
async def get_transcript(
    job_id: str
) -> TranscriptResult:
    snapshot = await (
        collection.where("jobId", "==", job_id)
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
    )
    if not snapshot.exists:
        raise HTTPException(status_code=404, detail="Job not found")
    job_data = snapshot.to_dict()
    logging.info("Fetched job data: {}".format(snapshot))
    return build_transcript_result(job_data)


@app.get("/transcript/search", response_model=List[TranscriptResult])
async def search_transcripts(
    jobStatus: Optional[JobStatus] = Query(default=None),
    userId: Optional[str] = Query(default=None)
) -> List[TranscriptResult]:
    if jobStatus is not None:
        query = collection.where("jobStatus", "==", jobStatus.value)
    if userId is not None:
        query = collection.where("userId", "==", userId)
    results = query.order_by("createdAt", direction=firestore.Query.DESCENDING)

    jobs: List[TranscriptResult] = []
    logging.info("search_transcripts returns: {}".format(results))
    async for snapshot in results.stream():
        job_data = snapshot.to_dict() or {}
        job_data.setdefault("jobId", snapshot.id)
        jobs.append(build_transcript_result(job_data))
    return jobs
