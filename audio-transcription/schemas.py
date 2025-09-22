from __future__ import annotations

from datetime import datetime
from google.cloud.firestore import DocumentSnapshot
from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional

from .models import ChunkStatus, JobStatus


class TranscribeRequest(BaseModel):
    audioChunkPaths: List[str] = Field(..., min_items=1)
    userId: str = Field(..., min_length=1)

    @field_validator("audioChunkPaths")
    def validate_paths(cls, value: List[str]) -> List[str]:
        if any(not path for path in value):
            raise ValueError("audioChunkPaths must not contain empty values")
        return value


class TranscribeResponse(BaseModel):
    jobId: str
    tasks: Dict[str, str]


class TranscriptResult(BaseModel):
    jobId: str
    userId: str
    transcriptText: str
    chunkStatuses: Dict[str, ChunkStatus]
    jobStatus: JobStatus
    completedTime: Optional[datetime]


def build_transcript_result(
    results: List[DocumentSnapshot],
) -> TranscriptResult:
    assert len(results) > 0, "job must contain at least one document"

    path_to_status = {
        row.get("chunkPath"): row.get("chunkPath")
        for row in results
    }

    chunk_status_list = [row.get("chunkStatus") for row in results]
    status = JobStatus.QUEUED.value
    if all(s == ChunkStatus.COMPLETED.value for s in chunk_status_list):
        status = JobStatus.COMPLETED.value
    elif any(
        s in [
            ChunkStatus.IN_PROGRESS.value,
            ChunkStatus.TRANSIENT_ERROR,
            ChunkStatus.PENDING.value,
        ]
        for s in chunk_status_list
    ):
        status = JobStatus.IN_PROGRESS.value
    elif any(s == ChunkStatus.FAILED.value for s in chunk_status_list):
        status = JobStatus.FAILED.value

    all_texts = [row.get("transcriptText") for row in results]

    job_complte_time = None
    if status == JobStatus.COMPLETED.value:
        task_completed_times = [row.get("completedTime") for row in results]
        job_complte_time = max(task_completed_times)      

    return TranscriptResult(
        jobId=results[0].get("jobId"),
        userId=results[0].get("userId"),
        transcriptText="\n".join(all_texts),
        chunkStatuses=path_to_status,
        jobStatus=status,
        completedTime=job_complte_time,
    )
