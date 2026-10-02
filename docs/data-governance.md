# Data retention, deletion, and Neon operating constraints

## Retention

Keep the minimum data needed: identity/profile and encrypted OAuth tokens while connected; normalized source items and derived events while active under a configurable rolling period; local task state while the account exists or until cleared; and limited sync/security metadata without secrets or full post bodies. The production retention period must be approved before real data is collected.

## Account deletion

Deletion requires reauthentication, revokes the Google connection where possible, deletes profile, sessions, tokens, courses, source items, derived events, tasks, notifications, sync records, and user-owned audit records, and instructs clients to clear IndexedDB/cache/queues. Backups follow the provider expiry window and are never restored into development.

## Neon decision record

Verified in the authenticated Neon console on 2026-09-22:

- Project `weathered-grass-23170767` exists on the Free Plan in AWS US East 2 (Ohio), with PostgreSQL 18 and a non-expiring `production` branch.
- The Free Plan currently includes 0.5 GB storage, 100 compute hours per month, autoscaling up to 2 CU, and 10 branches per project.
- The primary compute autoscales from 0.25 CU (about 1 GB RAM) to 2 CU (about 8 GB RAM), allows 894 direct or 10,000 pooled connections, and scales to zero after five minutes of inactivity. The free-plan inactivity delay is not configurable.
- Point-in-time restore history is six hours. Manual snapshots are available, while scheduled snapshots require an upgrade.
- The connection dialog provides pooled and direct endpoints. Both generated formats require TLS with `sslmode=require` and `channel_binding=require`; no password or complete connection string was copied into this repository.

Runtime traffic will use the pooled TLS endpoint. Alembic will use the direct TLS endpoint with a separately restricted migration credential once application roles are created in Milestone 2. The frontend must never receive either connection string. Provider limits must still be rechecked before production deployment because plans can change.

Reference: [Neon compute and scale-to-zero documentation](https://neon.com/docs/manage/endpoints/).
