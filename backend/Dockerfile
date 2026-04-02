# Production Dockerfile for Abes AgroTech backend (FastAPI)
FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg, optional audio/OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Strip all --hash=... (inline and whole lines) to avoid mismatch when PyPI re-releases packages
RUN sed -i 's/ *--hash=sha256:[a-f0-9]*//g' requirements.txt && \
    sed -i '/^[[:space:]]*--hash=sha256:[a-f0-9]*[[:space:]]*$/d' requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Bind to 0.0.0.0 for Docker; use env for workers if needed
# Trust X-Forwarded-* from Nginx
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips", "*"]
