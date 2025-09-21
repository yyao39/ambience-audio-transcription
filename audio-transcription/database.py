"""Utilities for interacting with the Firestore persistence layer."""

from __future__ import annotations
from typing import Self

from google.cloud import firestore


_firestore_client: firestore.AsyncClient | None = None


def get_firestore_client() -> firestore.AsyncClient:
    """Return a singleton Firestore async client instance."""

    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.AsyncClient()
    return _firestore_client


async def init_db() -> None:
    """Initialise the Firestore client.

    Firestore does not require schema creation, but we instantiate the client to
    fail fast if credentials are misconfigured.
    """

    get_firestore_client()


class AudioTranscriptions:
    @staticmethod
    def get_collection() -> firestore.AsyncCollectionReference:
        """Return the collection used to store transcription jobs."""

        client = get_firestore_client()
        return client.collection(Self.__name__)
