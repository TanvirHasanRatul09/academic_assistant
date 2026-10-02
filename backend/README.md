# Backend

Requires Python 3.12–3.14 and PostgreSQL.

1. Copy `.env.example` to `.env` and replace every required placeholder.
2. Create a virtual environment and install `pip install -e ".[dev]"`.
3. Run `uvicorn app.main:app --reload`.

Create or update the local schema with `python -m alembic upgrade head`. Add synthetic
development data with `python -m scripts.seed`; the command is safe to run repeatedly.

Quality commands: `ruff format --check .`, `ruff check .`, `mypy app`, and `pytest`.
