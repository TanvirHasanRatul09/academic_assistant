# Milestone 10 verification report

Completed on 2026-09-26.

## Functional verification

| Journey | Evidence | Result |
|---|---|---|
| OAuth login and onboarding | OAuth state/nonce/PKCE and profile validation tests | Pass |
| Logout and session invalidation | Isolated API test deletes the session and rejects the next request | Pass |
| Classroom reconnection and safe failures | Authenticated reconnect route and safe Classroom error-code tests | Pass |
| Account deletion | Isolated relational test verifies user and task cascades; frontend clears local data on current-device deletion and the next online `401` on another device | Pass |
| Synchronization and extraction | Classroom pagination/sync service tests plus extraction regression suite | Pass |
| Dashboard filtering | Timezone boundary and offline local filtering tests | Pass |
| Offline mode | Snapshot queries, current-user binding, truthful offline state, and online-authentication cache purge tests | Pass |
| Offline conflict handling | Queued writes include the expected server timestamp; `409` causes one refresh-and-retry, while account mismatch and expired sessions retain data without cross-account upload | Pass |
| Notifications | Generator, preferences, read/dismiss, and authorization tests | Pass |
| Assistant chat | Planner, bounded input, authentication, local fallback, sources, and offline answer tests | Pass |
| Phone and desktop layout | Production CSS/build includes 36rem phone and 52rem tablet breakpoints, flexible grids, wrapping navigation, and single-column assistant controls | Pass |

The app still requires a final real-device smoke test after deployment because browser/PWA behavior and Google consent cannot be fully simulated in unit tests.

## Security verification

An isolated in-memory relational test creates two users, two selected courses, and private tasks. User A can retrieve only A's dashboard and assistant source. Updating user B's task returns `404`.

Verified controls:

- Authentication, session expiry, logout invalidation, recent authentication for deletion, and CSRF rejection.
- Exact-origin CORS, `no-store`, CSP, clickjacking, referrer, and content-type headers.
- Per-client rate limiting and assistant per-user daily limits.
- Cascade deletion and local-device clearing after remote account deletion.
- Bounded prompts, histories, dates, searches, result counts, and Classroom extraction input.
- Malformed dates, conflicting targets, prompt-injection text, HTML markup, and `javascript:`/`data:` source links.
- React text rendering is used; no `dangerouslySetInnerHTML` path exists.
- Source links accept HTTPS only.

Production logging records lifecycle status, safe error codes, and bounded audit metadata. It does not log request bodies, Classroom content, cookies, OAuth tokens, prompts, or email addresses. The recursive redaction helper covers authorization, cookie, token, password, and email fields.

## Security scans

- `npm audit --omit=dev --audit-level=high`: 0 vulnerabilities.
- Project-scoped `pip-audit`: 0 known vulnerabilities after raising patched minimums for AnyIO, cryptography, and pytest.
- `pip check`: no broken requirements.
- Ruff security/static checks on the Milestone 10 additions: passed.
- Credential-pattern scan across source/config files: no credential-shaped secrets found.
- Frontend TypeScript and ESLint checks: passed.

## Test totals

- Backend: 48 passed, 1 optional live PostgreSQL integration test skipped.
- Frontend: 8 passed.
- Frontend production PWA build: passed.
- Synthetic classification evaluation: 12/12 cases passed in every measured dimension.

The skipped database test is intentionally gated by `RUN_DATABASE_TESTS=1`; it targets a migrated seeded PostgreSQL database and is not needed for the isolated two-user security suite.
