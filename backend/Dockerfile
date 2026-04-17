FROM python:3.12.10-slim-bookworm

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (cached unless pyproject.toml changes)
COPY pyproject.toml .
RUN pip install --no-cache-dir "."

# Install Chromium for Playwright-based scrapers (bot-blocked counties)
RUN playwright install --with-deps chromium

# Application code (changes here don't bust the pip cache)
COPY app/ app/
COPY alembic.ini .
COPY alembic/ alembic/
COPY scripts/ scripts/

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    RUN_PRE_INGEST_ON_STARTUP=0

EXPOSE 8000

CMD sh -c "alembic upgrade head && if [ \"${RUN_PRE_INGEST_ON_STARTUP:-0}\" = \"1\" ]; then python scripts/pre_ingest.py; fi && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
