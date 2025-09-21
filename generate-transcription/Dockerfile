FROM python:3.11

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY generate_transcript.py ./main.py

EXPOSE 8080

CMD ["functions-framework", "--target", "main", "--host", "0.0.0.0", "--port", "8080"]