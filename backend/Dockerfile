FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (cached unless pyproject.toml changes)
COPY pyproject.toml .
RUN pip install --no-cache-dir "."

# Application code (changes here don't bust the pip cache)
COPY app/ app/
COPY alembic.ini .
COPY alembic/ alembic/
COPY scripts/ scripts/

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD sh -c "alembic upgrade head; python scripts/pre_ingest.py || echo 'pre_ingest failed, continuing...'; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
