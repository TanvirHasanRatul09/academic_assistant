# Milestone 0 threat model

| Threat | Controls | Verification |
|---|---|---|
| Account takeover / forged OAuth callback | Authorization Code + PKCE, state/nonce, issuer/audience/expiry checks, secure HttpOnly SameSite cookies, session rotation, reauthentication for deletion | OAuth/session tests |
| Token theft | Server-only storage, application-layer encryption, no token logs, least-privilege scopes, disconnect revocation | Secret/log scan |
| Cross-user data access | Authenticated user ID injected server-side; ownership predicates and foreign keys on every private query | Two-account authorization tests |
| Malicious post or URL | Sanitize output, allow only trusted schemes, never execute extracted instructions, bounded parsers | XSS/URL regression suite |
| Leaked offline cache / wrong-account write | Minimal IndexedDB projection, no tokens, clear on logout/account switch, account-bound queue | Browser storage/reconnect tests |
| Outage, revoked access, or quota failure | Timeouts, bounded backoff, idempotent sync, safe errors, last-success timestamp, partial-sync UI | Failure-injection tests |
| Database compromise | TLS, pooled runtime connection, restricted app role, separate migration role, encrypted token fields, no production copies in dev | Config/restore review |
| Log leakage | Redact headers, cookies, tokens, raw content, and personal data | Log inspection |

## Security invariants

- A browser never receives a refresh token, database credential, encryption key, or provider error payload.
- Every private read/write is scoped by the authenticated internal user ID.
- Classroom content cannot change authorization, tool policy, or executable behavior.
- Source data and derived/user-corrected data remain separate and traceable.

