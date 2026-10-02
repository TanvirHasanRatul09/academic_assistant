# Milestone 2 completion audit

Audit date: 2026-09-24

| Requirement | Evidence |
|---|---|
| ER design and core tables | `docs/database.md`; SQLAlchemy models in `backend/app/db/models/` |
| Ownership and foreign keys | User-owned tables have cascading `users.id` keys; private queries require `user_id` |
| Idempotency and indexes | Migration `0001` contains source/extraction/task uniqueness and query indexes |
| UTC-aware timestamps | Every temporal model column uses timezone-aware PostgreSQL timestamps |
| Migration and seed | `python -m alembic upgrade head`; repeatable `python -m scripts.seed` |
| OAuth token encryption | Fernet service stores ciphertext bytes and rejects invalid keys |
| Safe failures and backups | Generic API errors and provider-only encrypted backup policy are documented |
| Cross-user isolation | Integration test queries seeded tasks as the owner and an unrelated UUID |

## Verification result

Pass. Against PostgreSQL 17 on 2026-09-24, Alembic successfully downgraded to an empty schema,
rebuilt the database from revision `0001`, reported no model/migration drift, and loaded the
synthetic seed twice without duplication. Ruff and strict mypy passed; pytest passed all eight
tests, including the database-backed cross-user isolation check.

The isolated Neon `dev/local` branch was also verified on 2026-09-24 using a pooled TLS runtime
endpoint and a separate direct TLS migration endpoint. Revision `0001`, schema-drift detection,
synthetic seeding, and the cross-user isolation test all passed. Credentials remain only in the
Git-ignored backend environment file.
