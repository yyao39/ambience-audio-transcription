from __future__ import annotations

import asyncio
import random
from typing import Iterable, Set


class ASRClientError(Exception):
    """Base class for simulated ASR client errors."""


class TransientASRError(ASRClientError):
    """Raised when the ASR service encounters a transient failure."""


class PermanentASRError(ASRClientError):
    """Raised when the ASR service encounters a permanent failure."""


class ASRClient:
    """Simulated asynchronous ASR client with concurrency and failure characteristics."""

    def __init__(
        self,
        *,
        max_concurrency: int = 100,
        transient_failure_rate: float = 0.05,
        permanent_failures: Iterable[str] | None = None,
        min_latency_seconds: float = 0.1,
        max_latency_seconds: float = 0.2,
    ) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._transient_failure_rate = transient_failure_rate
        self._permanent_failures: Set[str] = set(permanent_failures or [])
        self._min_latency = min_latency_seconds
        self._max_latency = max_latency_seconds

    async def transcribe(self, audio_path: str) -> str:
        """Simulate a transcription call with latency and possible failures."""
        async with self._semaphore:
            await asyncio.sleep(random.uniform(self._min_latency, self._max_latency))
            if audio_path in self._permanent_failures:
                raise PermanentASRError(f"Audio path {audio_path} cannot be transcribed")
            if random.random() < self._transient_failure_rate:
                raise TransientASRError("Transient ASR failure")
            return f"Transcript for {audio_path}"
