# Sync Performance Fix — 10–15 Second Target

## Objective

Redesign Google Classroom synchronization so that a normal user-visible sync completes in 10–15 seconds under healthy network and provider conditions. The UI must respond immediately, show real progress, remain usable during synchronization, and never display an indefinite spinner.

This work must preserve data correctness, course selection, extraction, targeting, notification behavior, authentication, and existing user task state.

## Current problem

The current `POST /api/sync` request performs the entire operation synchronously. It discovers courses, downloads submissions, announcements, coursework, and materials for every selected course, walks all historical pages, writes progress repeatedly to the remote database, extracts events, and generates notifications before returning to the browser.

Courses and resource types are processed serially. Provider retries and remote database latency therefore accumulate. A sync can remain in the foreground for 7–8 minutes while the UI only says “Synchronizing.”

## Required outcome

- `POST /api/sync` creates a sync run and responds in less than one second with HTTP `202` and the run identifier.
- Synchronization continues outside the request lifecycle.
- The application remains navigable while sync is running.
- The UI displays phase, courses processed, courses total, elapsed time, and partial failures.
- A routine incremental sync finishes within 10–15 seconds at p95 under healthy Google API and database conditions.
- A first-time full import should target 15 seconds when the bounded import fits within configured limits. If it cannot, it must continue safely in the background with visible progress and a defined maximum runtime.
- No sync may appear stuck. If no heartbeat is recorded for 30 seconds, report it as stalled and offer a safe retry.
- One inaccessible or slow course must not prevent other courses from completing.

## Implementation requirements

### 1. Database readiness

Before performance work, apply and verify all migrations through Alembic head. The application currently requires migration `0007`. Add a startup/readiness check that clearly reports schema mismatch instead of allowing endpoints to fail indirectly.

### 2. Background execution

Separate sync creation from sync execution.

- `POST /api/sync` creates a `running` `SyncRun`, queues work, and returns immediately.
- `GET /api/sync/status` exposes the latest run and progress.
- Prefer a durable worker and queue for production. A FastAPI in-process background task may be used only as a documented development fallback.
- Jobs must be idempotent and safe to retry.
- Preserve the per-user duplicate-sync guard across processes using the database, not only an in-memory thread lock.
- Recover runs left in `running` state after worker or server failure.

### 3. Incremental synchronization

Store a per-user, per-course checkpoint containing at least:

- last successful sync time;
- newest provider `updateTime` seen for each resource type;
- pagination or resume information when appropriate;
- last successful submission refresh time.

For announcements, coursework, and materials ordered by `updateTime desc`, stop paging after reaching records already covered by the successful checkpoint. Do not treat unvisited historical records as deleted during incremental runs.

Use periodic full reconciliation separately to detect old deletions. Do not scan all historical pages during every manual sync.

Fetch student submissions only when needed for coursework state, and avoid repeatedly downloading unchanged historical submissions.

### 4. Bounded first import

To make the 10–15 second target credible, define a bounded initial import policy, for example:

- selected active courses only;
- the newest configurable number of items or pages per resource type;
- a configurable history window such as the current academic term;
- deeper history imported later in the background if required.

The product must clearly state the active policy. It must not silently claim that unlimited Google Classroom history can always be imported within 15 seconds.

### 5. Limited concurrency

Process independent courses concurrently with a small configurable limit, initially three workers.

- Do not share a SQLAlchemy `Session` across threads or tasks.
- Each worker must use its own database session and transaction boundary.
- Respect Google API quotas and handle HTTP 429 using bounded exponential backoff with jitter.
- Do not create unbounded tasks or parallelize every course at once.

### 6. Database efficiency

- Remove per-item flushes where generated UUIDs allow batching.
- Load existing records using the smallest required columns and indexed lookup keys.
- Upsert changed items in batches.
- Update progress at phase transitions or throttled intervals rather than committing excessively.
- Add or verify indexes supporting `(course_id, source_type, source_id)`, update-time comparisons, user sync lookups, and extraction lookup paths.
- Keep user task state intact when academic content is updated.

### 7. Time budgets and partial success

Set explicit budgets rather than allowing an endless sync:

- per provider request timeout;
- per course timeout;
- total job soft deadline;
- bounded retry count and delay.

If a course exceeds its budget, record a safe course-level error, continue the remaining courses, and finish the run as `partial`. Never expose tokens, private Classroom response bodies, or raw internal exceptions.

### 8. Progress and UX

Expose and render:

- run status;
- current phase;
- courses processed and total;
- items seen and changed;
- elapsed time;
- successful and failed course counts;
- safe error summaries;
- last successful synchronization time.

The Sync button should change to a compact progress indicator. Navigation must remain enabled. Provide a completion toast and a partial-success warning listing affected course names. A page refresh must reconnect to the active run.

### 9. Observability

Persist timing metrics for:

- authorization or token refresh;
- course discovery;
- each resource type;
- Google request count and total latency;
- database read and write time;
- extraction;
- notification generation;
- total runtime.

Log structured run and course identifiers without access tokens or sensitive Classroom content. Add a development-only diagnostic view showing where sync time was spent.

## Acceptance tests

1. `POST /api/sync` returns `202` with a run ID in less than one second while the job continues.
2. A second sync for the same user is rejected without starting duplicate work, including when requests reach different server processes.
3. With ten selected courses and no provider changes, incremental sync completes within 10 seconds in the controlled performance fixture.
4. With ten selected courses and a small number of changed items, it completes within 15 seconds in the controlled performance fixture.
5. Only changed or new items are extracted; unchanged items are not reprocessed.
6. Incremental sync does not delete historical content that was intentionally not revisited.
7. A slow or inaccessible course produces `partial` status while other courses complete.
8. Progress survives page refresh and accurately reaches the terminal state.
9. A worker interruption does not leave the user permanently stuck in `running`.
10. Existing authentication, targeting, dashboard, review, notification, and offline tests continue to pass.
11. Migration-head and database integration tests run against PostgreSQL rather than being silently skipped in the release verification workflow.

## Verification procedure

- Build deterministic fake Google Classroom responses representing 1, 5, 10, and 25 courses with configurable page counts and latency.
- Measure cold initial import separately from warm incremental sync.
- Record p50, p95, provider request count, pages fetched, database time, and total runtime.
- Test healthy, throttled, timeout, revoked-authorization, partial-course, worker-restart, and duplicate-click scenarios.
- Confirm correctness by comparing the optimized result with the existing full reconciliation result on the same fixture.

## Definition of done

The work is complete only when synchronization is asynchronous, incremental, observable, recoverable, and verified by correctness and performance tests. A faster spinner, a larger timeout, or hiding the running state does not satisfy this issue.

## Implementation status

### Phase 1 implemented — 2026-09-28

- Live database upgraded through migration `0008`.
- `POST /api/sync` now creates a persistent run and returns HTTP `202` before executing synchronization in a background task.
- Background work uses an independent SQLAlchemy session.
- A PostgreSQL partial unique index prevents more than one running job per user across server processes.
- Per-course JSON checkpoints record provider update times for submissions, announcements, coursework, and materials.
- Incremental resource lists stop after reaching their checkpoint and do not delete unseen historical records.
- Initial imports are bounded to two pages per resource; warm incremental checks are bounded to three pages and normally stop on the first checkpoint page.
- Sync runs persist heartbeat, phase, live item/course counts, timing metrics, and safe failed-course details.
- Stalled and crashed jobs transition to explicit failed states instead of spinning forever.
- Frontend sync actions return immediately, remain navigable, poll persistent progress, display course/phase progress, and refresh dashboard data after terminal status.
- Submission metadata is included in content hashing so changed submission state is no longer silently skipped.
- Backend suite passes with one PostgreSQL integration test intentionally skipped by the default unit environment.
- Frontend typecheck, lint, 40 tests, and production build pass.

### Phase 2 implemented — 2026-09-28

- Selected courses synchronize concurrently with a strict three-worker ceiling.
- Every course worker owns an independent SQLAlchemy session and Classroom HTTP client; sessions are never shared across threads.
- Course results are merged centrally, including changed IDs, request counts, provider latency, page counts, failures, and live progress.
- Authorization revocation cancels pending work and fails safely; ordinary course failures produce partial success without blocking other courses.
- The UI now shows elapsed seconds, current phase, completed-course count, and the number of unavailable courses after partial completion.
- Controlled 10-course and 25-course concurrency performance fixtures verify the worker ceiling and scaled time budgets.
- The full backend suite passes with 63 tests passing and one environment-gated PostgreSQL test skipped locally.
- The frontend passes typecheck, lint, all 40 tests, and the production/PWA build.

Phase 2 is code-complete. Final real-world acceptance requires recording one cold and one warm synchronization against the connected Google Classroom account after the backend restarts. The warm run is the release measurement for the 10–15 second objective.

### Phase 3 started — 2026-09-28

Implemented safely:

- PostgreSQL-backed durable queue semantics using the existing `sync_runs` table.
- Atomic `FOR UPDATE SKIP LOCKED` job claiming for multiple worker processes.
- Renewable two-minute worker leases with ownership checks at every persisted progress update.
- Expired leases return to the queue instead of leaving an endless running state.
- Crash retry is capped at three attempts before a safe terminal failure.
- Migration `0009` adds worker identity, lease expiry, attempt count, and a claim-path index.
- `SYNC_EXECUTION_MODE=in_process` preserves simple local development.
- `SYNC_EXECUTION_MODE=worker` queues API requests for the standalone `python -m scripts.sync_worker` process.
- Worker dispatch and empty-queue paths have automated regression tests.
- Live Neon schema is at `0009 (head)`.

Not enabled yet:

- Automatic deep deletion reconciliation. Removing records absent from a provider scan is destructive and needs an explicit retention, tombstone, and recovery policy. Fast incremental sync remains non-destructive.

Phase 3 validation: 65 backend tests pass, one environment-gated integration test is skipped locally, and changed-file lint passes.


### Phase 4 completed — 2026-09-28

Assistant correctness:

- Added day-of-month interpretation for imperfect phrases such as `on 29 of CSE 3208`.
- Generic words such as `exam` no longer become mandatory text filters when the selected tool already filters event type.
- Overlapping terms such as `lab final` and `final` are deduplicated.
- Extraction rules advanced to `rules-v3-dates`.
- Existing academic events are upgraded in place instead of creating duplicate versioned events.
- Unchanged items with stale extraction rules are eligible for reprocessing, bounded to 50 per sync to protect latency.
- The exact live CSE 3208 Lab Final was reprocessed and verified as an exam on September 29, 2026 at 4:20 PM Asia/Dhaka with no review flag.
- The exact screenshot question now returns the Lab Final source in an end-to-end live database check.

Synchronization corrections:

- Bounded course concurrency increased from three to five after the real run showed 41 provider requests and a 36.75-second processing time.
- Reclaimed jobs reset progress counters, preventing misleading results such as `20/10 courses` after a retry.
- Rule upgrades are processed in bounded batches instead of forcing an unlimited re-extraction pass during one sync.
- Exact planner, extraction, concurrency, and full backend regression tests pass.

Phase 4 validation: 66 backend tests pass, one environment-gated PostgreSQL integration test is skipped locally, changed-file lint passes, and the corrected answer was verified against the live synchronized record.

The 10–15 second sync objective still requires one new warm-sync measurement after restarting the backend. The previous 36.75-second measurement predates the five-worker Phase 4 optimization.
