# Online, offline, stale-data, and sync-failure behavior

| State | Data shown | User actions | Status shown |
|---|---|---|---|
| Online, synchronized | Latest successfully committed server data | Read/filter; local task changes save immediately; manual sync is subject to cooldown | Online and exact last successful sync time |
| Online, sync running | Last committed data remains visible | Reading remains available; duplicate sync requests are prevented | Syncing, start time, and previous successful sync time |
| Offline | Only the current account's bounded IndexedDB projection | Read/filter supported data; safe local task changes may queue against that account | Offline and exact last successful sync time |
| Stale | Last committed server or device data | Reading remains available; source links may require connectivity | Stale warning with age and reason |
| Partial sync failure | Successfully validated pages from the run plus prior unaffected records | Reading remains available; retry is bounded and manual sync observes cooldown | Partial-sync warning, safe error code, counts, and last full success |
| Permission revoked | Previously committed data is treated as stale; no provider calls continue with invalid credentials | Reconnect or delete account; queued writes do not upload | Permission-revoked message without raw provider errors |
| Session expired/account switched | No private data for the previous account is displayed | Reauthenticate; previous-account queues are blocked and local data is cleared | Signed-out/account-changed state |

OAuth tokens and account-management responses are never cached. Logout, disconnect, deletion, and account switching clear local academic data and queued changes. A queued change carries an internal account binding and cannot upload after session revocation or under another account.

