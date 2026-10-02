# Run Academic Assistant locally

This guide starts the Neon-backed FastAPI API and React frontend on Windows.

## 1. Prerequisites

Install Python 3.12–3.14 and Node.js 20 or newer. You also need a Neon PostgreSQL database and a Google Cloud OAuth web client with the Classroom API enabled.

The OAuth client must contain this exact redirect URI:

```text
http://localhost:8000/api/auth/google/callback
```

While the app is in testing mode, add your Google account under **Google Auth Platform → Audience → Test users**.

## 2. Configure the backend

```powershell
cd D:\academic_assitant\academic_assistant
Copy-Item backend\.env.example backend\.env
```

Edit `backend\.env` and provide real values:

```env
APP_ENV=development
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@POOLED_NEON_HOST/DATABASE?sslmode=require
MIGRATION_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@DIRECT_NEON_HOST/DATABASE?sslmode=require
SESSION_SECRET=YOUR_RANDOM_SESSION_SECRET
TOKEN_ENCRYPTION_KEY=YOUR_FERNET_KEY
GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET=YOUR_GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
ALLOWED_ORIGINS=http://localhost:5173
GEMINI_API_KEY=
SYNC_EXECUTION_MODE=worker
SYNC_COURSE_CONCURRENCY=5
```

Generate the secrets independently:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Use the first output for `SESSION_SECRET` and the second for `TOKEN_ENCRYPTION_KEY`. Never commit or share `backend\.env`.

## 3. Configure the frontend

Create `frontend\.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=unused-backend-oauth-client
```

OAuth is handled by the backend. Never put the Google client secret in a frontend variable.

## 4. Install dependencies

```powershell
cd D:\academic_assitant\academic_assistant\backend
python -m pip install -e ".[dev]"

cd D:\academic_assitant\academic_assistant\frontend
npm install
```

## 5. Apply database migrations

```powershell
cd D:\academic_assitant\academic_assistant\backend
python -m alembic upgrade head
python -m alembic current
```

The current revision should be `0010 (head)`.

Optional synthetic development data:

```powershell
python -m scripts.seed
```

## 6. Start the application in three terminals

Keep all three PowerShell terminals open while developing. Worker mode prevents Classroom synchronization from blocking Google login and normal API requests.

### Terminal 1 — Backend API

```powershell
cd D:\academic_assitant\academic_assistant\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Verify <http://localhost:8000/health> returns:

```json
{"status":"ok"}
```

### Terminal 2 — Synchronization worker

```powershell
cd D:\academic_assitant\academic_assistant\backend
.\.venv\Scripts\python.exe -m scripts.sync_worker
```

The worker claims queued jobs using PostgreSQL row locks and renewable leases. Multiple worker processes are safe, but only one local worker is needed. Use `.\.venv\Scripts\python.exe -m scripts.sync_worker --once` for a single claim-and-exit pass.

### Terminal 3 — Frontend

```powershell
cd D:\academic_assitant\academic_assistant\frontend
npm run dev
```

Open <http://localhost:5173>. Stop any process with `Ctrl+C` in its terminal.

## 7. Sign in and synchronize Classroom

1. Select **Continue with Google**.
2. Use the account registered as a Google test user.
3. Approve the requested read-only Classroom permissions.
4. Complete the profile onboarding form.
5. Open the dashboard and select **Sync Classroom now**.

If synchronization reports `authorization_revoked`, open **Settings**, select **Reconnect Classroom access**, approve consent once, and synchronize again.

Run one scheduled synchronization pass with:

```powershell
cd D:\academic_assitant\academic_assistant\backend
python -m scripts.sync_all
```

## 8. Run verification checks

Backend:

```powershell
cd D:\academic_assitant\academic_assistant\backend
python -m pytest
```

Frontend:

```powershell
cd D:\academic_assitant\academic_assistant\frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

## Troubleshooting

### `redirect_uri_mismatch`

Add `http://localhost:8000/api/auth/google/callback` as an authorized redirect URI in the Google OAuth web client.

### Google blocks access

Confirm the account is under **Google Auth Platform → Audience → Test users** and that the Google Classroom API is enabled.

### Neon password authentication fails

Copy fresh pooled and direct connection strings from Neon's **Connect** dialog. Use the pooled URL for `DATABASE_URL` and direct URL for `MIGRATION_DATABASE_URL`.

### Port already in use

Find the process using port 8000:

```powershell
netstat -ano | findstr ":8000"
```

Stop only the confirmed stale PID, then run the API command again:

```powershell
Stop-Process -Id PID_NUMBER
```

Use the same commands with port `5173` if the frontend port is occupied.

### Environment changes do not appear

Restart the API, synchronization worker, and frontend after editing their `.env` files.

