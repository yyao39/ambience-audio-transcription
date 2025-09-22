from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

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
    collection = AudioTranscriptions.get_collection()

    for index, audio_path in enumerate(request.audioChunkPaths):
        now = datetime.now()
        task_id = str(uuid4())
        write_result = collection.document(task_id).set(
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
        logging.info("AudioTranscript at {}".format(write_result.update_time))
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
    collection = AudioTranscriptions.get_collection()
    query = collection.where(filter=FieldFilter("jobId", "==", job_id))
    query = query.order_by("createdAt", direction=firestore.Query.DESCENDING)
    results = query.get()
    for row in results:
        logging.info("Fetched job data: {}".format(row.to_dict()))
    if len(results) == 0:
        raise HTTPException(status_code=404, detail="Job not found")
    return build_transcript_result(results)


@app.get("/transcript/search", response_model=List[TranscriptResult])
async def search_transcripts(
    jobStatus: Optional[JobStatus] = Query(default=None),
    userId: Optional[str] = Query(default=None)
) -> List[TranscriptResult]:
    query = AudioTranscriptions.get_collection()
    if jobStatus is not None:
        query = query.where(filter=FieldFilter("jobStatus", "==", jobStatus.value))
    if userId is not None:
        query = query.where(filter=FieldFilter("userId", "==", userId))

    results = (
        query.order_by(
            "createdAt",
            direction=firestore.Query.DESCENDING
        ).get()
    )

    jobs: List[TranscriptResult] = []
    logging.info("search_transcripts returns: {}".format(results))
    for snapshot in results:
        jobs.append(build_transcript_result(snapshot))
    return jobs
