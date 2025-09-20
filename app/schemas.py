from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .models import ChunkStatus, Job, JobStatus


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


class TranscriptResult(BaseModel):
    jobId: str
    userId: str
    transcriptText: str
    chunkStatuses: Dict[str, ChunkStatus]
    jobStatus: JobStatus
    completedTime: Optional[datetime]


class ProcessTranscriptionTask(BaseModel):
    jobId: str = Field(..., min_length=1)


def build_transcript_result(job: Job) -> TranscriptResult:
    ordered_statuses: "OrderedDict[str, ChunkStatus]" = OrderedDict()
    transcript_parts = []
    for chunk in sorted(job.chunks, key=lambda c: c.sequence):
        ordered_statuses[chunk.audio_path] = chunk.status
        if chunk.transcript_text:
            transcript_parts.append(chunk.transcript_text)
    transcript_text = "\n".join(transcript_parts)
    return TranscriptResult(
        jobId=job.id,
        userId=job.user_id,
        transcriptText=transcript_text,
        chunkStatuses=dict(ordered_statuses),
        jobStatus=job.status,
        completedTime=job.completed_at,
    )
