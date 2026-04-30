# Use official Python runtime as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run sets PORT (often 8080); local Docker defaults to 8000.
EXPOSE 8080

# Health check (honours PORT when set)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os,urllib.request; p=os.environ.get('PORT','8000'); urllib.request.urlopen(f'http://127.0.0.1:{p}/health')" || exit 1

# Runtime: FAISS index + metadata must exist under paths in settings (default app/scm_index_v2.faiss,
# app/scm_metadata_v2.pkl). Set OPENAI_API_KEY (Secret Manager on Cloud Run). No database required.
ENV PRELOAD_FAISS=true
ENV UVICORN_WORKERS=2

# Run application (shell form so ${PORT} works on Cloud Run)
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${UVICORN_WORKERS:-2}"]
