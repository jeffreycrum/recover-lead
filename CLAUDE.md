# RecoverLead

AI-powered surplus funds recovery platform for agents, attorneys, and heir search firms.

**Domain**: recoverlead.com
**Stack**: FastAPI (Python) + React 18 (TypeScript) + PostgreSQL (pgvector) + Redis + Celery
**Auth**: Clerk (not custom JWT)
**Deployment**: Railway

## Before You Start

1. Read `TASKS.md` for current priorities and progress
2. Read the Phase 2 plan at `~/.claude/plans/phase2-retention-polish.md`
3. Read relevant source files before making changes
4. One task, one focus — no unrelated changes

## Project Structure

```
recover-lead/
├── backend/           # FastAPI + Celery
│   ├── app/
│   │   ├── api/v1/    # Route handlers
│   │   ├── models/    # SQLAlchemy ORM
│   │   ├── schemas/   # Pydantic request/response
│   │   ├── services/  # Business logic
│   │   ├── rag/       # pgvector + embeddings + LLM
│   │   ├── ingestion/ # County scrapers
│   │   ├── workers/   # Celery tasks
│   │   ├── templates/ # Jinja2 letter templates
│   │   └── core/      # Auth, rate limiting, logging
│   └── tests/
├── frontend/          # React + Vite + shadcn/ui
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       ├── lib/
│       └── providers/
└── scripts/
```

## Build & Run

```bash
# Dev environment
docker compose up -d
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev

# Tests
pytest                                    # Backend unit tests
docker compose -f docker-compose.test.yml up -d
pytest tests/test_workers/ --integration  # Celery integration tests
cd frontend && npm test                   # Frontend tests

# Linting
ruff check backend/
mypy backend/app/
cd frontend && npx eslint src/ && npx tsc --noEmit
```

## Conventions

### Python (Backend)

- **Python >= 3.12**
- **Pydantic v2**: use `model_dump()`, not `.dict()`
- **SQLAlchemy 2.0**: async sessions, `select()` syntax, not legacy Query API
- **Alembic**: every schema change gets a migration. Never modify the database directly.
- **Type hints**: all function signatures must have type annotations
- **Imports**: stdlib → third-party → local, separated by blank lines
- **Naming**: snake_case for functions/variables, PascalCase for classes, UPPER_CASE for constants

### TypeScript (Frontend)

- **React 18** with functional components only
- **shadcn/ui** for all UI primitives — do not install alternative component libraries
- **@tanstack/react-query** for all server state — no raw useEffect for data fetching
- **@tanstack/react-table** for all data tables
- **react-router-dom v6** for routing
- **Clerk**: use `@clerk/clerk-react` components for auth UI. Never build custom auth forms.
- **Naming**: camelCase for functions/variables, PascalCase for components, kebab-case for file names

### Both

- **Conventional commits**: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`
- **Feature branches**: never commit directly to main
- **No scope creep**: do not refactor adjacent code, add docstrings to unchanged functions, or "improve" code outside the current task

## Security Rules (NEVER violate these)

### Authentication & Authorization
- **Clerk only**: all auth flows go through Clerk. Never store passwords or issue JWTs.
- **Clerk webhooks**: always verify via `svix`. Never trust unverified webhook payloads.
- **Row-level isolation**: every query for user-specific data (user_leads, letters, contacts, activities) MUST include `WHERE user_id = current_user.id`. No exceptions.
- **Stripe webhooks**: always verify via `stripe.Webhook.construct_event()`. Never trust unverified payloads.

### Data Protection
- **No PII in logs**: structlog PII filter must strip email, phone, address from all log output
- **No secrets in code**: all credentials via environment variables. Never hardcode API keys, webhook secrets, or database URLs.
- **No plaintext PII storage**: skip trace contact data (phone, email, address) stored as-is for now but flagged for encryption in Phase 2.
- **Input sanitization**: all scraper-sourced data must be sanitized before storage (strip control chars, limit length, validate format)
- **LLM output validation**: always validate Claude responses (quality_score 1-10, letter content patterns). Never trust raw LLM output.

### Financial Operations
- **Atomic credit deduction**: `UPDATE ... SET credits_remaining = credits_remaining - 1 WHERE credits_remaining > 0 RETURNING credits_remaining`. Never read-then-write.
- **Atomic lead claiming**: `UPDATE ... SET user_id = $1 WHERE id = $2 AND (user_id IS NULL OR user_id = $1) RETURNING id`. Never read-then-write.
- **Idempotency keys**: required on all POST endpoints with side effects. Store in Redis with 24h TTL.

## Celery Tasks

- **Async bridge**: Celery workers are synchronous. Use `asyncio.run()` inside tasks for batch LLM calls.
- **Retry policy**: exponential backoff, `max_retries=3`, failed tasks go to `failed_tasks` table (DLQ)
- **Timeouts**: `task_time_limit=600`, `task_soft_time_limit=540`
- **Concurrency**: `rag` queue limited to `worker_concurrency=4`. Redis semaphore for Anthropic API rate limiting.
- **Never call Anthropic API from the FastAPI process** — always via Celery task.

## Database Rules

- **pgvector**: HNSW index with `(m=16, ef_construction=64)` on `leads.embedding`
- **CHECK constraints**: required on all bounded fields (surplus_amount >= 0, quality_score 1-10, confidence 0-1)
- **Dedup**: unique index on `(county_id, case_number)`. Hash on normalized business keys.
- **Connection pooling**: API `pool_size=5, max_overflow=10`. Celery workers `pool_size=2, max_overflow=3`.
- **Migrations**: always use `alembic revision --autogenerate -m "description"`. Review generated migration before applying.
- **UTC timestamps**: all datetime columns are timezone-aware UTC. Use `func.now()` for defaults.

## Testing Requirements

- All new API endpoints MUST have tests
- All tests MUST verify tenant isolation (user A cannot access user B's data)
- Scraper tests: fixture-based (saved HTML/PDF). Never hit real county websites in tests.
- Celery unit tests: `CELERY_ALWAYS_EAGER=True`
- Celery integration tests: use `docker-compose.test.yml` with real Redis
- Concurrency tests: credit deduction and lead claiming under parallel requests
- Mock all external services: Anthropic API, Stripe, Clerk, skip trace providers
- **Error messages**: use generic messages in API responses. Never expose internal details, stack traces, or SQL.

## API Design

- **REST**: nouns for resources, not verbs. `/leads`, not `/getLeads`
- **Cursor pagination**: on all list endpoints. Never use offset pagination.
- **Status codes**: 200 success, 201 created, 202 accepted (async), 400 bad request, 401 unauthorized, 403 forbidden, 404 not found, 409 conflict, 422 validation error, 429 rate limited, 500 server error
- **Error format**: `{"error": {"code": "MACHINE_READABLE", "message": "Human readable"}}`
- **Versioning**: URL-based `/api/v1/`
- **Rate limiting headers**: always include `X-RateLimit-*` headers on responses

## What NOT to Do

- Do not install alternative UI libraries (Material UI, Ant Design, Chakra) — use shadcn/ui
- Do not build custom auth — use Clerk
- Do not add LlamaIndex without evaluating if raw pgvector queries suffice
- Do not call external APIs (Anthropic, Stripe, Clerk) in tests without mocking
- Do not store secrets in code, config files, or Docker images
- Do not add features not in TASKS.md without discussing first
- Do not use `git add -A` or `git add .` — stage specific files
- Do not amend commits — create new commits
- Do not push to main without CI passing
- Do not add comments to code you didn't change
- Do not add type annotations to functions you didn't change
- Do not refactor code outside the scope of your current task
