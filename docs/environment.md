# Environment configuration

Use separate Google OAuth clients, callback URLs, databases, and secrets for development, test, preview, and production. Real values belong in local ignored environment files or the encrypted environment settings of the hosting provider.

| Variable | Exposure | Required | Source |
|---|---|---|---|
| `APP_ENV` | Backend configuration | Yes | Environment name: development, test, preview, or production |
| `DATABASE_URL` | Secret | Yes | Local Compose PostgreSQL or Neon; pooled TLS for normal production traffic |
| `SESSION_SECRET` | Secret | Yes | Cryptographically secure random generator; at least 32 characters |
| `TOKEN_ENCRYPTION_KEY` | Secret | Yes | Independent cryptographically secure generator |
| `GOOGLE_CLIENT_ID` | Identifier | Yes | Environment-specific Google Cloud OAuth client |
| `GOOGLE_CLIENT_SECRET` | Secret | Yes | Google Cloud OAuth client; backend only |
| `GOOGLE_REDIRECT_URI` | Public URL | Yes | Exact callback registered for that environment |
| `ALLOWED_ORIGINS` | Public configuration | Yes | Exact comma-separated frontend origins; no wildcard |
| `GEMINI_API_KEY` | Secret | No before AI milestone | AI provider; backend only |
| `VITE_API_BASE_URL` | Public | Yes | Browser-facing API origin |
| `VITE_GOOGLE_CLIENT_ID` | Public identifier | Yes | Public OAuth client identifier only |

Generate independent secrets, for example with Python's `secrets.token_urlsafe(48)`. Never copy example values into a deployment. Every bundled `VITE_*` value is readable by users.

## Rotation and incident procedure

1. Create a replacement credential in the provider without deleting the active one when overlap is supported.
2. Update the backend hosting environment, deploy, and verify authentication/database health.
3. Revoke the old credential and invalidate affected sessions or tokens.
4. For encryption-key rotation, support decrypt-with-old/encrypt-with-new during a controlled migration; never discard the old key before all ciphertext is migrated.
5. If a secret enters Git, revoke it immediately, rotate dependent sessions, remove it from history with an approved history-rewrite procedure, notify collaborators to re-clone, and document only identifiers/timestamps—not the secret.

GitHub Dependabot configuration supplies dependency update alerts, and CI secret scanning blocks detected credentials. Repository-host security settings should additionally enable native secret scanning when available.

