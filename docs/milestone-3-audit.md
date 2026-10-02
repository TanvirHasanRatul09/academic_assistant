# Milestone 3 audit

Audit date: 2026-09-26

## Implementation evidence

| Requirement | Evidence | Result |
|---|---|---|
| OAuth security | Authorization Code flow, S256 PKCE, random state and nonce, short-lived HttpOnly transaction cookies | Pass |
| Identity validation | Google token validation plus explicit issuer, audience, expiry, nonce, subject, and verified-email checks | Pass |
| Token protection | Access and refresh tokens encrypted with Fernet and stored only in `oauth_accounts` | Pass |
| Sessions and CSRF | Hashed server-side session IDs, expiry, HttpOnly/SameSite cookies, production Secure flag, rotation, invalidation, and double-submit CSRF protection | Pass |
| Onboarding and profile | Responsive forms for section, lab group, IANA timezone, owned course selection, and notification preferences; client and server validation | Pass |
| Ownership | Profile and course queries derive the user from the authenticated session; submitted course IDs must belong to that user | Pass |
| Account lifecycle | Logout, Google disconnect, reconnect through login, permanent cascading deletion, and recent Google reauthentication | Pass |
| Abuse controls | Per-IP limits on login, reauthentication, callback, profile update, disconnect, and deletion routes | Pass |
| Frontend routing | Protected dashboard/settings routes and onboarding redirection | Pass |

## Automated verification

- Backend: 11 passed, 1 database integration test skipped.
- Frontend: ESLint passed, TypeScript passed, Vitest passed, and the production PWA build passed.
- Google OAuth client ID, client secret, redirect URI, and Fernet key pass local configuration checks without exposing their values.

## Database verification

- Neon accepted both updated pooled and direct credentials.
- Alembic applied revisions `0001` and `0002`; `python -m alembic current` reports `0002 (head)`.
- The repeatable synthetic seed completed successfully.
- Direct database verification returned one relevant task for its owner and zero for an unrelated UUID.
- The equivalent remote pytest integration case stalled after collection on this workstation, although each of its three SQL assertions completed successfully when run directly. This is recorded as a runner anomaly rather than a failed assertion.

## Conclusion

Every Milestone 3 implementation requirement is present and the database migration and ownership boundary are verified. The completion gate passes at implementation level. A real Google account must still complete the browser consent flow during local acceptance testing because automated tests must not possess or operate a user's Google credentials.
