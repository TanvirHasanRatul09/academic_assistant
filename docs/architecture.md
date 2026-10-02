# System architecture and data flow

```text
Browser/PWA --HTTPS + secure session cookie--> FastAPI backend
                                             |-- repositories/services --> PostgreSQL
                                             |-- server-side OAuth/Classroom client --> Google
```

The frontend never connects to PostgreSQL or Classroom directly. The backend enforces authentication, authorization, provider calls, parsing, relevance, and persistence.

## Main flow

1. The browser starts Authorization Code + PKCE with server-validated state/nonce.
2. The backend validates the callback, rotates the application session, and stores minimum identity/profile data.
3. A sync job loads selected courses, then paginates permitted announcements, coursework, materials, topics, and own-submission metadata.
4. It validates sizes and URLs, hashes source content, idempotently upserts source records, and records a `sync_run`.
5. Deterministic extraction creates versioned academic events and user-scoped relevance/task records without altering source content.
6. API queries return only records owned by the authenticated user. The browser stores a bounded offline projection, never credentials or tokens.

## Failure model

Partial syncs preserve successful data, record a safe error code, and expose the last successful sync time. The UI distinguishes offline, stale, permission-revoked, and provider-failure states. Logout, disconnect, deletion, account switching, and session expiry clear or invalidate local queued state safely.

Source content is untrusted input: sanitize HTML, allowlist link schemes, bound parser input, and treat extracted text as data rather than instructions. Raw source retention is time-bounded and configurable.

