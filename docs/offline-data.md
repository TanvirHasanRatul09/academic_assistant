# Offline data and privacy

Academic Assistant can save a limited academic snapshot in the browser so the installed PWA remains useful without internet.

## What is stored

IndexedDB database `academic-assistant-offline`, schema version 1, contains:

- the active application's user ID and the minimum session display fields needed to open the offline UI;
- selected course names and IDs;
- relevant derived dashboard tasks/events and their Classroom source links;
- the exact last successful synchronization time;
- safe local task-state changes waiting to upload.

The local query layer supports today, tomorrow, this week, upcoming deadlines, unfinished tasks, exams, and course filtering using the saved user's timezone.

## What is never stored offline

- Google access or refresh tokens;
- session cookies or CSRF tokens;
- Google client secrets or API keys;
- OAuth callbacks, account-management responses, or authentication API responses;
- another account's academic snapshot.

The service worker precaches only the application shell and versioned static assets. It has no API runtime cache, and `/api/` navigation is excluded from the application-shell fallback.

## Account and queue safety

A queued change contains only the task ID, changed local-state fields, expected server update time, queue time, and owning application user ID.

Before replay, the app must obtain a current server session and confirm that its user ID matches the cached user ID. Expired sessions stop replay. Account switching clears the previous snapshot and queue. Server timestamps detect concurrent changes; on conflict, the app retrieves the newest task and reapplies only the fields changed locally.

Logout, Google disconnect, account deletion, and the Settings “Clear offline data” action clear the local stores.

## Device risk

Anyone who can unlock the device and use the same browser profile may be able to read locally saved academic data. Users should clear offline data before sharing a browser profile or device.

## Schema changes

Increase `DATABASE_VERSION` in `frontend/src/offline.ts` and add migration logic inside `onupgradeneeded`. Never silently reuse a store with an incompatible shape.
