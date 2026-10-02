# i3 relevance targeting audit

Date: 2026-09-27

## Root cause

The previous extractor recognized only explicitly labelled sections and groups, retained punctuation variants literally, and compared them using basic case folding. This made `A-1` and `A1` different values. Ambiguous multi-target announcements were marked relevant to every user, and relevance decisions had no stored explanation. Academic year/program targeting was not represented.

## Resolution

- Explicit labels (`Section`, `Sec`, `Group`, `Lab group`, `Year`, `Level`, `Department`, and `Program`) are parsed; unrelated bare letters are ignored.
- Values are canonicalized for comparison, including `A-1`, `A1`, `Section A`, `Sec A`, and `Group A1`.
- Relevance evaluates section, lab group, academic level, and program independently and requires every explicit dimension to match.
- General/course-wide content remains relevant.
- Conflicting or multi-valued targeting is excluded from dashboards/notifications and placed in the review queue.
- Every user task stores a safe relevance explanation.
- Profile updates reprocess relevance immediately.
- `/api/dashboard/relevance-debug` is scoped to the authenticated user's selected courses and returns 404 in production. `/dev/relevance` presents it in development.

## Verification

Regression tests cover general notices, Section A/Lab A1 variants, B/B1/C1 exclusion, bare-letter false positives, academic-level/program mismatch, conflicting targets, and timezone handling. Backend tests pass, focused Ruff checks pass, and frontend tests, TypeScript, ESLint, and production build pass. Migration graph resolves to `0007 (head)`.
