import functions_framework
import logging
from datetime import datetime

from firebase_admin import firestore
import firebase_admin
import google.cloud.logging

# Instantiates a client
client = google.cloud.logging.Client()

# Retrieves a Cloud Logging handler based on the environment
# you're running in and integrates the handler with the
# Python logging module. By default this captures all logs
# at INFO level and higher
client.setup_logging()

app = firebase_admin.initialize_app()
db = firestore.client(database_id="ambience-ai-standard")


@functions_framework.http
def generate_transcript(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """
    request_json = request.get_json(silent=True)
    task_id = request_json.get("task_id")
    audio_path = request_json.get("audio_path")

    if not request_json:
        logging.info("request json is empty")
        return "request json is empty"

    logging.info(
        "request task_id: {} audio_path: {}".format(task_id, audio_path)
    )

    # Update DB when ASR succeeds
    now = datetime.now()
    db.collection("AudioTranscriptions").document(task_id).update({
        "chunkStatus": "completed",
        "transcriptText": "Transcript pending ...",
        "completedTime": now,
        "updatedAt": now,
    })

    return 'echo {}'.format(request_json)
