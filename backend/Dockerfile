# Production Dockerfile for Abes AgroTech backend (FastAPI)
FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg + invoice OCR (align with Dockerfile.dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-eng \
    tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Bind to 0.0.0.0 for Docker; use env for workers if needed
# Trust X-Forwarded-* from Nginx
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--forwarded-allow-ips", "*"]
