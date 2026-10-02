# Local development

## PostgreSQL

Install Docker Desktop, then run `docker compose up -d postgres`. The database is bound to localhost only and uses development-only credentials. Do not reuse them outside local development.

From `backend/`, run `python -m alembic upgrade head` and then `python -m scripts.seed`.
Use `python -m alembic downgrade base` only against disposable development data.

## Backend

Follow `backend/README.md`. Configuration is validated when the application is imported and started; missing values, placeholders, weak secrets, non-PostgreSQL URLs, malformed callback URLs, and wildcard CORS origins fail startup.

## Frontend

Follow `frontend/README.md`. The Vite app validates its required public environment variables during startup/build. The generated service worker precaches only the application shell and static assets; authenticated API responses are not runtime-cached.
