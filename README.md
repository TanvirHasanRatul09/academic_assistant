# Academic Assistant

Academic Assistant is a private, course-aware workspace that organizes a student's selected Google Classroom data into a focused dashboard. It helps students review tasks, deadlines, exams, notices, and completion status without changing the original Classroom content.

The application combines deterministic course and assessment matching with an optional Gemini explanation layer. Course selection, record retrieval, completion updates, and user isolation remain deterministic, so AI cannot silently substitute an unrelated course or assessment.

## Features

- Google OAuth sign-in with server-side sessions
- Read-only Google Classroom synchronization
- Student-selected active courses
- Section and lab-group filtering
- Today, tomorrow, weekly, upcoming, deadline, exam, notice, and recent views
- Personal tasks for work announced outside Classroom
- Course-aware assistant with conversation context
- Separate quiz, lab-final, theory-final, midterm, assignment, lab-task, online-assessment, announcement, material, and result types
- Local completion status updates through the dashboard or assistant
- Responsive desktop, tablet, and mobile interface
- Accessible motion with reduced-motion support
- Browser-local dashboard snapshots and limited offline assistant search
- Queued offline dashboard state changes with conflict handling

## Important behavior

### Classroom is read-only

The application cannot submit, edit, grade, or delete Google Classroom content. Marking something **completed** changes only that user's Academic Assistant task state; it does not modify Classroom.

### Assistant accuracy

The assistant searches only the authenticated user's selected, active, synchronized courses. It resolves the course first, the exact academic item second, and the requested property third. If it cannot establish an exact match, it asks for clarification or says the information is unavailable instead of guessing.

Gemini may summarize records already selected by deterministic backend code. It does not choose source records and is not needed for deterministic completion-status queries.

### Offline support

After an online sign-in and successful dashboard load, the same browser profile can retain a cached identity, dashboard snapshot, synchronized tasks, and queued dashboard state changes. Basic assistant searches can run against that snapshot.

Offline data is stored in browser IndexedDB—not the server database. It is device- and browser-specific and may disappear when site data is cleared or private browsing is used. Offline mode cannot fetch new Classroom data or contact Gemini, and its assistant currently supports fewer aliases and conversational actions than the online assistant.

## Technology

| Area | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, React Router |
| PWA/offline | Vite PWA, service worker, IndexedDB |
| Backend | Python 3.12+, FastAPI, SQLAlchemy |
| Database | PostgreSQL with Alembic migrations |
| Authentication | Google OAuth 2.0 and server-side sessions |
| Integration | Google Classroom read-only APIs |
| Optional AI | Gemini |
| Testing | pytest, Ruff, mypy, Vitest, ESLint, Playwright |

## Repository layout

```text
academic_assistant/
├── .github/               # CI and dependency-update configuration
├── backend/
│   ├── app/               # API, models, schemas, repositories, and services
│   ├── migrations/        # Alembic migrations
│   ├── scripts/           # Sync worker, seed, and evaluation commands
│   └── tests/             # Backend tests
├── frontend/
│   ├── public/            # Icons and static assets
│   ├── src/               # Pages, components, API client, and offline logic
│   └── e2e/               # Playwright tests
├── docs/                  # Architecture, security, and behavior documentation
├── docker-compose.yml     # Local PostgreSQL
└── RUNNING.md             # Detailed Windows instructions
```

## Prerequisites

- Python 3.12, 3.13, or 3.14
- Node.js 20 or newer and npm
- PostgreSQL 17, or Docker Desktop
- A Google Cloud project with the Classroom API enabled
- A Google OAuth web application
- Optional Gemini API key

## Google Cloud setup

Enable the Google Classroom API and create an OAuth web client. For local development, register:

```text
http://localhost:8000/api/auth/google/callback
```

If the consent screen is in testing mode, add your account under **Google Auth Platform → Audience → Test users**. Never place the Google client secret in frontend code or a `VITE_*` variable.

## Local installation

### 1. Clone and start PostgreSQL

```powershell
git clone https://github.com/TanvirHasanRatul09/academic_assistant.git
cd academic_assistant
docker compose up -d postgres
```

You may use hosted PostgreSQL instead of Docker.

### 2. Configure the backend

```powershell
Copy-Item backend\.env.example backend\.env
```

Edit `backend/.env`:

```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://academic_app:local-development-only@localhost:5432/academic_assistant
MIGRATION_DATABASE_URL=
SESSION_SECRET=replace-with-a-random-session-secret
TOKEN_ENCRYPTION_KEY=replace-with-a-valid-fernet-key
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
ALLOWED_ORIGINS=http://localhost:5173
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
SYNC_EXECUTION_MODE=in_process
```

Generate independent secrets:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use the first output for `SESSION_SECRET` and the second for `TOKEN_ENCRYPTION_KEY`.

### 3. Configure the frontend

```powershell
Copy-Item frontend\.env.example frontend\.env
```

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your-public-google-client-id
```

Only public values may use the `VITE_*` prefix.

### 4. Install dependencies and migrate the database

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m alembic upgrade head

cd ..\frontend
npm ci
```

## Run locally

Open two terminals.

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Verify <http://localhost:8000/health>.

Frontend:

```powershell
cd frontend
npm run dev
```

Open <http://localhost:5173>.

For durable queued synchronization, set `SYNC_EXECUTION_MODE=worker` and run a third terminal:

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.sync_worker
```

The default `in_process` mode does not require a separate worker for simple local development.

## First-use workflow

1. Select **Continue with Google**.
2. Approve the requested read-only Classroom permissions.
3. Complete the profile, including section, lab group, timezone, and selected courses.
4. Synchronize Classroom.
5. Review extracted items that require confirmation.
6. Use the dashboard or ask the assistant a focused question.

Example questions:

```text
What assignments are due this week?
Is the CSE 3208 lab final marked completed?
Show upcoming exams for CSE 3214.
What is the AI lab-final question pattern?
Mark the CN quiz as completed.
```

If multiple items match a completion command, the assistant asks the user to select the exact item before changing anything.

## Tests and quality checks

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m pytest
```

Frontend:

```powershell
cd frontend
npm run lint
npm run typecheck
npm run test
npm run build
npm run check:budgets
```

Optional end-to-end tests:

```powershell
npm run test:e2e
```

## Deployment overview

This repository contains a frontend, a persistent backend, database migrations, and an optional synchronization worker. A typical setup is:

- **Frontend:** Vercel
- **Backend:** Render, Railway, Fly.io, or another Python host
- **Database:** managed PostgreSQL
- **Worker:** persistent worker process when using worker synchronization mode

Production requires:

- `APP_ENV=production`
- Persistent PostgreSQL URLs
- Stable, strong session and encryption secrets
- Production Google OAuth credentials and callback URL
- Exact frontend origin in `ALLOWED_ORIGINS`
- Deployed backend URL in `VITE_API_BASE_URL`

Using related domains such as `app.example.com` and `api.example.com` is preferable. Test authentication carefully when frontend and backend use unrelated domains because browser cookie policies may block cross-site sessions.

## Security and privacy

- OAuth tokens are encrypted before database storage.
- Production authentication uses secure server-side session cookies.
- State-changing requests require CSRF protection.
- CORS allows exact configured origins; wildcards are rejected.
- Queries are scoped to the authenticated user.
- Classroom permissions are read-only.
- Provider tokens and secrets are not exposed to browser code.
- Sensitive headers and cookies are redacted from logs.
- Cached offline data can be cleared from Settings.

Anyone with access to an unlocked browser profile may be able to view its cached academic data.

## Never commit these files

The included `.gitignore` excludes:

- `backend/.env` and `frontend/.env`
- `.venv/` and `node_modules/`
- Build output, coverage, and tool caches
- Local databases and logs
- OAuth credentials, service-account files, certificates, and private keys

Commit the provided `.env.example` files, but never commit real credentials.

## Documentation

- [Detailed run guide](RUNNING.md)
- [Architecture](docs/architecture.md)
- [Environment variables](docs/environment.md)
- [Classroom access](docs/classroom-access.md)
- [Offline behavior](docs/offline-behavior.md)
- [Offline data](docs/offline-data.md)
- [Assistant security](docs/assistant-security.md)
- [Threat model](docs/threat-model.md)
- [Data governance](docs/data-governance.md)
- [Database design](docs/database.md)
- [Motion system](docs/motion-inventory.md)

## License

No open-source license has been added. Until a license is provided, the repository does not grant permission to copy, modify, or redistribute the project.
