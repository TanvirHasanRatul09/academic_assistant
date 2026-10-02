# Milestone 9 audit

Completed on 2026-09-26.

## Delivered

- Four narrow, validated, read-only academic query tools.
- Authenticated-user scoping in every SQL query and selected-course ownership checks.
- Deterministic intent planning and answers when Gemini is absent or unavailable.
- Optional Gemini structured summarization with bounded context and an eight-second timeout.
- Source links, last successful sync time, and explicit missing-data responses.
- Per-IP minute limiting, per-user daily usage limiting, CSRF protection, and safe audit metadata.
- In-memory-only bounded chat history and no server-side prompt retention.
- Offline answers from the current user's IndexedDB snapshot.
- Responsive Assistant page, navigation entry, suggestions, sources, and clear-chat action.

## Verification

- Backend: 30 passed, 1 optional database integration test skipped.
- Frontend: 5 passed.
- Frontend TypeScript typecheck: passed.
- Frontend ESLint: passed.
- Frontend production/PWA build: passed.
- Focused Ruff checks for all new Python files: passed.
- Focused mypy checks for the assistant service and schema: passed.

The completion gate is satisfied: supported questions are answered only from authenticated synchronized data, and absent information produces a clear no-data response instead of a guess.

