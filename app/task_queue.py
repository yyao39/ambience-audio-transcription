from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

try:  # pragma: no cover - import guard for optional dependency
    from google.api_core import exceptions as google_exceptions
    from google.cloud import tasks_v2
except ImportError as exc:  # pragma: no cover - handled at runtime
    google_exceptions = None
    tasks_v2 = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class TaskQueueError(RuntimeError):
    """Raised when a Cloud Tasks operation fails."""


@dataclass
class TaskQueueConfig:
    project_id: str
    location_id: str
    queue_id: str
    handler_url: str
    service_account_email: Optional[str] = None
    audience: Optional[str] = None

    @classmethod
    def from_env(cls) -> "TaskQueueConfig":
        try:
            project_id = os.environ["TASKS_PROJECT_ID"]
            location_id = os.environ["TASKS_LOCATION_ID"]
            queue_id = os.environ["TASKS_QUEUE_ID"]
            handler_url = os.environ["TASKS_HANDLER_URL"]
        except KeyError as exc:  # pragma: no cover - defensive guard
            missing = exc.args[0]
            raise TaskQueueError(f"Missing required task queue configuration: {missing}") from exc
        return cls(
            project_id=project_id,
            location_id=location_id,
            queue_id=queue_id,
            handler_url=handler_url,
            service_account_email=os.environ.get("TASKS_SERVICE_ACCOUNT_EMAIL"),
            audience=os.environ.get("TASKS_AUDIENCE"),
        )


class TranscriptionTaskQueue:
    """Publish transcription jobs to Google Cloud Tasks."""

    def __init__(
        self,
        *,
        config: Optional[TaskQueueConfig] = None,
        client: Optional[tasks_v2.CloudTasksClient] = None,
    ) -> None:
        if _IMPORT_ERROR is not None:
            raise TaskQueueError(
                "google-cloud-tasks is not installed"
            ) from _IMPORT_ERROR
        self._config = config or TaskQueueConfig.from_env()
        self._client = client or tasks_v2.CloudTasksClient()

    def enqueue(self, job_id: str) -> None:
        payload = json.dumps({"jobId": job_id}).encode("utf-8")
        parent = self._client.queue_path(
            self._config.project_id, self._config.location_id, self._config.queue_id
        )
        task: dict = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": self._config.handler_url,
                "headers": {"Content-Type": "application/json"},
                "body": payload,
            }
        }
        if self._config.service_account_email:
            task["http_request"]["oidc_token"] = {
                "service_account_email": self._config.service_account_email,
                "audience": self._config.audience or self._config.handler_url,
            }
        task_name = self._client.task_path(
            self._config.project_id, self._config.location_id, self._config.queue_id, job_id
        )
        task["name"] = task_name
        try:
            self._client.create_task(parent=parent, task=task)
        except google_exceptions.AlreadyExists:
            # The task is already enqueued; nothing else to do.
            return
        except google_exceptions.GoogleAPICallError as exc:  # pragma: no cover - network failure
            raise TaskQueueError("Failed to enqueue transcription task") from exc
        except google_exceptions.RetryError as exc:  # pragma: no cover - retry exhaustion
            raise TaskQueueError("Failed to enqueue transcription task") from exc
