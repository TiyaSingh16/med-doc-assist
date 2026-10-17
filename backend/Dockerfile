# Backend image (used by Render; works on any Docker host). Build context: backend/.
FROM python:3.13-slim

# Tesseract for OCR of scanned PDFs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 app
WORKDIR /home/app/app

# pyreadline3 and win32_setctime are Windows-only; skipped if present.
COPY --chown=app requirements.txt .
RUN grep -vE '^(pyreadline3|win32_setctime)==' requirements.txt > /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt

COPY --chown=app . .
USER app
ENV PYTHONUNBUFFERED=1

# Render provides PORT; 8000 locally. Migrations are applied on every start
# (idempotent), then the API starts.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
