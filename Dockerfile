# Use an official Python runtime as a parent image
FROM python:3.11

# Disable output buffering and set up a working directory
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Install system dependencies (if any future build steps require gcc etc.).
# Keeping this separate allows Docker to cache the layer when requirements don't change.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app ./app

# Expose the port Cloud Run listens on
EXPOSE 8080

# Run the FastAPI application with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
