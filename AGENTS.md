# CoWork — Agent Guide

## Setup & Run
- **Docker (recommended):** `docker compose up --build` → serves on `:8000`
- **Local:** `pip install -r requirements.txt && uvicorn app.main:app --reload`
- DB auto-creates on first startup (no migrations). Docker volume `cowork-data` mounts at `/app/data/`.
- Env: `JWT_SECRET` (dev default in `docker-compose.yml`), `DATABASE_URL` (default `sqlite:///./cowork.db`)

## Testing
- `pytest` — runs `tests/test_smoke.py` via `TestClient(app)`, no external services needed
- No linter/formatter/typechecker config in repo — no automated style checks

## Architecture
- **Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 / SQLite — single package, single container
- **Entrypoint:** `app/main.py` — calls `Base.metadata.create_all(bind=engine)` on import
- **Routers:** `app/routers/` — one file per domain (`auth.py`, `rooms.py`, `bookings.py`, `admin.py`, `health.py`)
- **Services:** `app/services/` — business logic (refunds, stats, rate limiting, reference codes, export, notifications)
- **Models:** `app/models.py` — ORM: `Organization`, `User`, `Room`, `Booking`, `RefundLog`
- **Auth deps:** `get_current_user` (any auth), `require_admin` (admin-only) — both in `app/auth.py`

## Key Conventions
- **Datetimes:** stored naive UTC in DB. API accepts ISO 8601 (with or without offset), returns UTC with `Z`/`+00:00`.
- **JWTs:** HS256, claims `sub` (str), `org`, `role`, `jti`, `iat`, `exp`, `type`. Access TTL=900s, refresh=7d.
- **Errors:** `AppError` renders as `{"detail": ..., "code": ...}` — never change status codes, error codes, or JSON field names.
- **Imports:** full relative paths (`from ..auth import get_current_user`), no `__init__` re-exports.
- **In-memory state** (lost on restart): token blacklist, rate-limit buckets, stats counters, reference-code counter, response caches.

## Important
- **Grading is black-box** — the grader builds the container and tests the API only. Preserve every path, status code, error code, and JSON field name exactly as documented in the README.
- `bug_report.md` (root, optional) is used as final tie-breaker if submitted.
