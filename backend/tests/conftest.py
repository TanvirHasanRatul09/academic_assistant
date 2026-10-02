import os

for key, value in {
        "APP_ENV": "test",
        "DATABASE_URL": "postgresql+psycopg://test:test@localhost:5432/test",
        "SESSION_SECRET": "test-session-secret-that-is-long-enough",
        "TOKEN_ENCRYPTION_KEY": "test-encryption-key-that-is-long-enough",
        "GOOGLE_CLIENT_ID": "test-client-id",
        "GOOGLE_CLIENT_SECRET": "test-google-secret-value",
        "GOOGLE_REDIRECT_URI": "http://localhost:8000/api/auth/google/callback",
        "ALLOWED_ORIGINS": "http://localhost:5173",
}.items():
    os.environ.setdefault(key, value)
