FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (cached unless pyproject.toml changes)
COPY backend/pyproject.toml .
RUN pip install --no-cache-dir ".[prod]" 2>/dev/null || pip install --no-cache-dir "."

# Application code (changes here don't bust the pip cache)
COPY backend/app/ app/
COPY backend/alembic.ini .
COPY backend/alembic/ alembic/

EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
