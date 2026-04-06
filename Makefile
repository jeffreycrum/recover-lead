.PHONY: up down migrate seed test lint

# Dev environment
up:
	docker compose up -d postgres redis

down:
	docker compose down

# Backend
install:
	cd backend && pip install -e ".[dev]"

migrate:
	cd backend && alembic upgrade head

migration:
	cd backend && alembic revision --autogenerate -m "$(msg)"

seed:
	cd backend && python -m scripts.seed_counties

# Testing
test:
	cd backend && pytest -v

test-integration:
	docker compose -f docker-compose.test.yml up -d
	cd backend && pytest tests/test_workers/ -v --integration
	docker compose -f docker-compose.test.yml down

# Linting
lint:
	cd backend && ruff check . && mypy app/

lint-fix:
	cd backend && ruff check --fix .

# Frontend
frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-test:
	cd frontend && npm test

# All
dev: up install migrate
	@echo "Dev environment ready. Run 'uvicorn app.main:app --reload' from backend/"
