# Backend image, used by the Hugging Face Space (Docker SDK). Builds from the
# backend/ folder. Hugging Face runs containers as user 1000 on port 7860.
FROM python:3.13-slim

# Tesseract for OCR of scanned PDFs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

# CPU-only torch first (the default PyPI build pulls in several GB of CUDA
# libraries this server can't use), then everything else as pinned.
# pyreadline3 and win32_setctime are Windows-only leftovers from pip freeze.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user torch==2.12.0 --index-url https://download.pytorch.org/whl/cpu \
    && grep -vE '^(torch|pyreadline3|win32_setctime)==' requirements.txt > /tmp/requirements.txt \
    && pip install --no-cache-dir --user -r /tmp/requirements.txt

COPY --chown=user . .

EXPOSE 7860
# Apply migrations on every start (idempotent), then serve.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 7860"]
