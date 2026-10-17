# ClaimPilot FastAPI backend image.
# Build context: insurance-pro/backend
# Example: gcloud builds submit --region=asia-south1 --tag=IMAGE ./insurance-pro/backend

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OpenCV used by Ultralytics requires these runtime libraries on slim Debian.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# app/ includes the inference code and the committed model weights.
COPY app/ ./app/

# Cloud Run supplies PORT (normally 8080); retaining the fallback keeps local
# container runs straightforward.
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
