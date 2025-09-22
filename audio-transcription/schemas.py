from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional
from google.cloud.firestore import DocumentSnapshot

from pydantic import BaseModel, Field, validator

from .models import ChunkStatus, JobStatus


class TranscribeRequest(BaseModel):
    audioChunkPaths: List[str] = Field(..., min_items=1)
    userId: str = Field(..., min_length=1)

    @validator("audioChunkPaths")
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


def build_transcript_result(job: List[DocumentSnapshot]) -> TranscriptResult:
    # ordered_statuses: "OrderedDict[str, ChunkStatus]" = OrderedDict()
    # chunk_status_map = job.get("chunkStatuses", {}) or {}
    # audio_paths = job.get("audioChunkPaths") or []

    # if audio_paths:
    #     for audio_path in audio_paths:
    #         status_value = chunk_status_map.get(audio_path, ChunkStatus.PENDING.value)
    #         ordered_statuses[audio_path] = ChunkStatus(status_value)
    # else:
    #     for audio_path, status_value in sorted(chunk_status_map.items()):
    #         ordered_statuses[audio_path] = ChunkStatus(status_value)

    # transcript_text = job.get("transcriptText", "") or ""
    # job_status = JobStatus(job.get("jobStatus", JobStatus.QUEUED.value))
    # completed_time = job.get("completedTime")

    return TranscriptResult(
        jobId="jobid",
        userId="yaoy",
        transcriptText="sdfasd",
        chunkStatuses={},
        jobStatus=JobStatus.QUEUED.value,
        completedTime=None,
    )
