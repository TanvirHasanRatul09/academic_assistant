# Milestone 0 decision log

| Decision | Choice | Reason |
|---|---|---|
| Product boundary | Read-only Classroom MVP | Least privilege and no accidental source changes |
| Identity key | Provider subject/user ID | Email addresses can change |
| Source of truth | Classroom for source; app for derived/local state | Corrections and completion stay non-destructive |
| Time | Store UTC, render in user timezone | Consistent deadlines |
| Database | PostgreSQL everywhere | Avoids SQLite behavior drift |
| Runtime access | Neon pooled TLS URL from backend only | Protects credentials and controls connections |
| Migrations | Separate connection/account | Limits runtime privileges |
| Sync | Scheduled/manual polling first | Reliability and quota control |
| AI | Deferred | Reliable, permissioned data comes first |

## Milestone 0 external verification

On 2026-09-22, the authenticated Neon console confirmed that project `weathered-grass-23170767` is active on the Free Plan. Connection strings were inspected only in password-masked form and were not copied into the repository.
