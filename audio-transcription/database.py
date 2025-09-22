"""Utilities for interacting with the Firestore persistence layer."""

from __future__ import annotations

from google.cloud import firestore


firestore_client = firestore.Client(
    project="ambience-audio-transcription",
    database="ambience"
)


def get_firestore_client() -> firestore.Client:
    """Return a singleton Firestore async client instance."""
    return firestore_client


async def init_db() -> None:
    """Initialise the Firestore client.

    Firestore does not require schema creation, but we instantiate the client to
    fail fast if credentials are misconfigured.
    """

    get_firestore_client()


class AudioTranscriptions:
    @classmethod
    def get_collection(cls) -> firestore.CollectionReference:
        """Return the collection used to store transcription jobs."""

        client = get_firestore_client()
        return client.collection(cls.__name__)
