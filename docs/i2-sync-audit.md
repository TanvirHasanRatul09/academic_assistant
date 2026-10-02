# i2 synchronization performance audit

Date: 2026-09-27

## Evidence and root cause

Before this change, each synchronization discovered both active and archived courses and then fetched submissions, announcements, coursework, and materials for every discovered course, whether the user selected it or not. Course and membership lookups were repeated inside the discovery loop. Every synchronized Classroom item was passed through event extraction after every run, even when its content hash was unchanged. Progress was represented only by a terminal item count, and no phase or request timing was persisted. The in-process user lock prevented simultaneous work in one process, but a persisted running job was not checked.

The dominant expected cost was therefore Google API pagination: one course listing plus up to four paginated resource streams per course. The second avoidable cost was repeated extraction over unchanged records. Database work was amplified by per-course lookups and repeated progress-independent processing. Live timings could not safely be collected without a connected user's Google credentials, so migration 0006 adds per-run measurements for Google request time/count, pages fetched, reconciliation/database time, extraction, notification generation, total time, and processed event/notification counts. These measurements establish a private-content-free production baseline on the next real synchronization.

## Implemented changes

- Course discovery is student-scoped and active-only (`studentId=me`, `courseStates=ACTIVE`).
- Content synchronization runs only for courses selected by the user.
- Existing memberships are preloaded, reducing repeated database lookups.
- Content hashes now short-circuit writes and extraction for unchanged items.
- Event extraction receives only changed item IDs; no changed items means no extraction pass.
- Notification uniqueness remains database-enforced and generation checks existing notifications.
- Per-user in-process locking is supplemented by a recent persisted `RUNNING` check and stale-job allowance.
- Provider timeouts/retries remain bounded; course-level non-auth failures produce a partial result while successful course updates remain usable.
- Progress persists the current phase and courses processed/total, and the shell polls every three seconds during a manual sync.
- Structured timing logs include only user ID, safe status/error codes, counts, and durations—never Classroom content or credentials.

Controlled concurrency was intentionally not added: the current synchronous SQLAlchemy session cannot be safely shared across worker threads, and parallel Google requests would increase quota pressure. The eliminated unnecessary course and extraction work provides a safer improvement; future concurrency should use isolated sessions and an explicit quota-aware worker pool.

## Verification

- Backend suite: 53 passed, 1 skipped.
- Added pagination/request timing, timeout/retry, and duplicate-sync tests.
- Frontend: 40 tests passed; TypeScript, ESLint, and production build passed.
- Focused Ruff validation passed for all synchronization files.
- Alembic migration graph resolves to `0006 (head)`.
