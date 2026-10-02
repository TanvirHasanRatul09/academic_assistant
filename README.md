# Personal Academic Intelligence Assistant

For complete local setup and copy-paste run commands, see [RUNNING.md](RUNNING.md).

Milestone 0 is complete, including live Neon project and plan verification. The evidence-by-requirement review is in [docs/milestone-0-audit.md](docs/milestone-0-audit.md). Start with [docs/mvp-scope.md](docs/mvp-scope.md), then review [docs/classroom-access.md](docs/classroom-access.md), [docs/offline-behavior.md](docs/offline-behavior.md), [docs/architecture.md](docs/architecture.md), [docs/threat-model.md](docs/threat-model.md), and [docs/data-governance.md](docs/data-governance.md).

The MVP is a read-only student dashboard backed by Google Classroom and PostgreSQL. It will not request teacher/admin Classroom permissions or expose provider tokens to browser code.

## Development foundation

- Backend: Python 3.12+, FastAPI, validated environment settings, structured/redacted logging, exact-origin CORS, and `/health`.
- Frontend: React, TypeScript, Vite, routing, responsive accessible shell, error boundary, and an application-shell-only PWA strategy.
- Local database: PostgreSQL 17 through Docker Compose.
- Quality: Ruff, mypy, pytest, ESLint, TypeScript, Vitest, production builds, Dependabot, and CI secret scanning.

Setup details are in [docs/development.md](docs/development.md) and [docs/environment.md](docs/environment.md).

Milestone 1 verification evidence is recorded in [docs/milestone-1-audit.md](docs/milestone-1-audit.md). Milestone 2 has not started.
