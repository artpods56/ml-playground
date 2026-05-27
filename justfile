set dotenv-load

# Default recipe shown when running `just` with no arguments
default:
    @just --list

# ── Install ──────────────────────────────────────────────────────────────────

# Install Python dependencies
install:
    uv sync

# Install Node.js dependencies
install-node:
    npm install

# Install everything (Python + Node)
install-all: install install-node

# ── Infrastructure ──────────────────────────────────────────────────────────

# Start Redis (required for Celery)
infra-up:
    brew services start redis

# Stop Redis
infra-down:
    brew services stop redis

# ── Backend (FastAPI) ────────────────────────────────────────────────────────

# Run the FastAPI backend server
run-backend:
    uv run backend-server

# Stop the FastAPI backend server
stop-backend:
    @pkill -f "uvicorn.*backend.main:app" 2>/dev/null; pkill -f "backend-server" 2>/dev/null; echo "Backend stopped."

# Create database tables
init-db:
    uv run python -c "from core.adapters.database.orm import metadata; from core.config import get_app_config; from sqlalchemy import create_engine; c = get_app_config(); e = create_engine(c.database_uri); metadata.create_all(e); print('Tables created.')"

# ── Worker (Celery) ──────────────────────────────────────────────────────────

# Run the Celery worker
run-worker:
    uv run celery -A apps.worker.src.worker.main.app worker --loglevel=info

# Stop the Celery worker
stop-worker:
    @pkill -f "celery.*worker" 2>/dev/null; echo "Worker stopped."

# Run the Celery beat scheduler
run-beat:
    uv run celery -A apps.worker.src.worker.main.app beat --loglevel=info

# Stop the Celery beat scheduler
stop-beat:
    @pkill -f "celery.*beat" 2>/dev/null && echo "Beat stopped." || echo "Beat not running."

# ── Webapp (Django) ─────────────────────────────────────────────────────────

# Build CSS (Tailwind)
css-build:
    npm run webapp:css:build

# Watch CSS and rebuild on changes
css-watch:
    npm run webapp:css:watch

# Run Django management commands (pass args, e.g. `just manage migrate`)
manage *args:
    uv run webapp-manage {{ args }}

# Run Django migrations
migrate:
    uv run webapp-manage migrate

# Create new Django migrations
makemigrations *args:
    uv run webapp-manage makemigrations {{ args }}

# Run the Django webapp server
webapp:
    uv run webapp-server

# ── Testing ──────────────────────────────────────────────────────────────────

# Run all tests
test:
    uv run pytest

# Run tests with verbose output
test-v:
    uv run pytest -v

# ── Lint / Format ────────────────────────────────────────────────────────────

# Run ruff check
lint:
    uv run ruff check .

# Run ruff format check
fmt-check:
    uv run ruff format --check .

# Auto-fix lint and format issues
fmt:
    uv run ruff check --fix .
    uv run ruff format .

# ── Dev ──────────────────────────────────────────────────────────────────────

# Run backend + worker + beat + webapp together
dev:
    @echo "Starting all services..."
    @uv run backend-server &
    @uv run celery -A apps.worker.src.worker.main.app worker --loglevel=info &
    @uv run celery -A apps.worker.src.worker.main.app beat --loglevel=info &
    @uv run webapp-server

# Stop all running services (backend, worker, beat)
stop-all: stop-backend stop-worker stop-beat

# ── Clean ────────────────────────────────────────────────────────────────────

# Remove build artifacts and caches
clean:
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
