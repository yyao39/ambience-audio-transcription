# Audio Transcription Service

This project provides a FastAPI-based backend service that accepts transcription jobs, calls a mocked ASR service, and returns job status and transcripts. Jobs and chunk-level progress are persisted in SQLite so the service can resume in-flight work after a restart.

## Features

- Submit jobs with ordered audio chunk URIs via `POST /transcribe`
- Query job status and transcripts via `GET /transcript/{jobId}`
- Search jobs by status or user via `GET /transcript/search`
- Background processing with retry logic for transient ASR failures
- Concurrency limit enforcement for ASR requests
- Persistence to resume work after service restarts

## Getting Started

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the API server

```bash
uvicorn app.main:app --reload
```

The service stores its SQLite database in `transcriptions.db` by default. To use a different path, set the `TRANSCRIPTION_DATABASE_URL` environment variable to a SQLAlchemy-compatible connection string.

### Example Requests

Create a job:

```bash
curl -X POST http://localhost:8000/transcribe \
  -H "Content-Type: application/json" \
  -d '{"userId": "patient-123", "audioChunkPaths": ["segment1", "segment2"]}'
```

Check job status:

```bash
curl http://localhost:8000/transcript/<jobId>
```

Search jobs for a user:

```bash
curl "http://localhost:8000/transcript/search?userId=patient-123"
```
