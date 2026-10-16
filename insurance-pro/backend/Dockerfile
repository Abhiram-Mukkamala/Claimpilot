# Dockerfile for claimbot AI backend
# Build: docker build -t claimbot-backend -f insurance-pro\backend\Dockerfile .
# Run: docker run -p 8000:8000 --env-file .env claimbot-backend

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (excluding weights for now)
COPY insurance-pro/backend/app app/
COPY insurance-pro/backend/*.py ./
COPY insurance-pro/backend/*.sql ./
COPY insurance-pro/backend/*.md ./

# Copy everything else except weights
COPY insurance-pro/backend/package-lock.json ./
COPY insurance-pro/backend/package.json ./

# Copy weights LAST to avoid image layer ordering problem
# This ensures weights are in a separate layer that doesn't invalidate
# the entire image when weights change
COPY insurance-pro/backend/app/models/weights app/models/weights/

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
