# Verification — memory-domain vertical slice — 2026-09-09

> Historical verification from before `tandem/product-cleanup`; legacy Firebase/Foursquare
> observations below are retained as audit history only.

## Production-readiness verification — 2026-09-10

The current deployment-preparation result is recorded here; the historical notes below describe an earlier Firebase-era verification pass and are retained for audit context.

| Area | Result |
|---|---|
| Frontend lint | `npm run lint` passed |
| Frontend typecheck/build | `npm run build` passed; Vite emitted only the existing Tailwind plugin warning |
| Frontend tests | 5 files, 17 tests passed |
| Backend lint/format | Ruff check passed; 67 files already formatted |
| Backend PostgreSQL/RLS suite | 51 tests passed in the Linux production image against the disposable PostgreSQL role-separated stack |
| Alembic | `alembic check` reported no new operations; migrations reach `0011_nostalgia_notifications` |
| Secret/dependency scans | Source secret scan: 0 findings; `npm audit --audit-level=high`: 0 vulnerabilities |
| Production image | Docker multi-stage image build passed; non-root container smoke passed for `/healthz`, SPA fallback, hashed asset caching, API 404 behavior, CSP, and request IDs |
| Render config | `render.yaml` parsed successfully; no database or Redis service is provisioned |

Remaining verification is intentionally manual: real Neon/B2/Google/TMDb/Geoapify/Resend credentials, OAuth redirect behavior, real-user A/B/C smoke flows, and the scheduled email path. The documented P0 privacy gap is self-service account export/delete; memory/photo deletion and resurfacing/email controls are already implemented.

---

## Memory-domain milestone

The PostgreSQL-backed memory/media vertical slice is implemented through migration
`0009_private_memory_media`. The backend suite was run against PostgreSQL 16 with a dedicated
`NOSUPERUSER NOBYPASSRLS` `tandem_app` runtime role and separate `tandem_migrator` migration role:
38 tests passed with zero PostgreSQL skips. It covers the A/B/C member boundary, direct RLS
read/update denial, all five categories, strict metadata and field validation, normalized tags,
pagination/filter/search, optimistic concurrency, participant changes, append-only activity
events, and hard deletion. `alembic downgrade base → upgrade head → check` passed. Frontend
Vitest reports 15 tests passed across 5 files; typecheck and production build passed. Compose
backend/frontend rebuild passed and all four local services became healthy.

The frontend's authenticated Keepsake path now reads `/api/me`, `/api/me/tandems`, members, and
memory endpoints. Today, timeline, memory detail, add/edit/delete, Explore, and Calendar no
longer use fixture data. Photo/anniversary enrichment remains intentionally deferred.

The two frontend lint warnings below remain pre-existing warnings in legacy components; there
are no lint errors. The backend suite reports only upstream Starlette/AnyIO deprecation warnings.

## Passed

| Check | Result |
| --- | --- |
| Baseline frontend build | Passed before source edits; baseline lint had 2 errors / 2 warnings |
| Final `npm test` | 17 tests across 6 files; provider/media validation and UI boundary coverage |
| Final `npm run build` | Strict TypeScript check and Vite production build passed |
| `npm audit fix` | Compatible dependency fixes; resulting npm audit reported zero vulnerabilities |
| Backend `pytest` | 38 passed with `TEST_DATABASE_URL` and `TEST_DATABASE_OWNER_URL`; zero PostgreSQL-related skips |
| `ruff check backend/app backend/tests backend/alembic` | Passed |
| `docker compose --env-file .env.local up --build -d --wait` | Frontend, backend, PostgreSQL 16 and Redis all healthy |
| HTTP health | Direct port 8000 and Vite `/api` proxy on port 5173 returned 200 and application/database `ok`; UUID request ID returned |
| Database failure/recovery | Stopped only the new local PostgreSQL container: health returned 503 with generic `database: unavailable`; restarted it: health returned 200 without backend restart |
| Alembic | Exact `0001_foundation` through `0009_private_memory_media` upgrade chain, downgrade-to-base/re-upgrade, `current`, and `check` all passed; no autogenerate drift |
| Persistence | PostgreSQL restart retained the Alembic revision; named PostgreSQL and Redis volumes configured; Redis uses AOF and returned `PONG` |
| Local backend configuration | Local Alembic connected successfully using generated ignored `.env.local` |
| Source secret guard / Gitleaks | Nonignored current source clean; exact public Firebase client-key exception only |
| Bundle secret check | No matches for the local TMDb/Foursquare provider values in rebuilt `dist`; values were compared in memory, never printed |
| Git hygiene | `.env` and generated Firebase cache staged for removal from tracking, local files preserved; `.env`/`.env.local` ignored; `git diff --check` clean |

Backend tests cover successful/degraded health, database exception redaction, unhandled-error response redaction, structured correlation logs, invalid request IDs, local CORS allow/reject behavior, production CORS disabled, required/invalid environment validation, masked settings, session cleanup, provider normalization/error handling, image processing, deterministic fake storage, and real PostgreSQL authorization across auth/Tandem/memory/media tables.

## Browser and legacy limits

Read-only in-app browser navigation at `http://127.0.0.1:5173` reached Search, Watched, Watchlist and Timeline. The search-disabled notice and existing filter/sort controls rendered. Firebase snapshot listeners returned `permission-denied`; the empty states therefore do **not** establish that the database has no records. No Firestore records were retrieved or mutated, and add/edit/delete persistence was not verified. Deployed Firestore rules were not inspected or modified.

Movie and place provider tests use deterministic fakes; no live TMDb, Geoapify, or hosted S3 credentials are required for automated verification. Production provider configuration remains a manual deployment step.

Existing lint debt remains: unused `lastDeleted` in Watchlist, and hook warnings in Edit Movie and Foursquare Search. Build warnings remain for large JavaScript chunks and the redundant Tailwind line-clamp plugin. Python tests report two upstream deprecation warnings (Starlette's httpx test client and AnyIO BlockingPortal alias); assertions pass. No cosmetic cleanup was added to this milestone.

The new GitHub Actions workflow was authored but not run remotely. Its core build/test/migration/scanning commands were run locally. No Firebase deployment, Git commit/push, history rewrite, OAuth, user/group migration, provider revocation, Redis feature, or hosted storage operation was performed.

## Historical credential incident

Gitleaks scanned the six locally available Git commits. With the Firebase public-config exception and a corrected provider-assignment rule, it still reports the TMDb credential in `.env` at initial commit `e7c942f`. This expected historical failure is distinct from the clean current-source result. Foursquare and any other previously committed provider secrets must also be treated as compromised regardless of scanner coverage. Revocation, historical/deployed artifact cleanup and deployed Firebase access review remain manual actions.

## Reproduce

Use the exact setup and command sequences in [README.md](../README.md). Verification used the separate disposable PostgreSQL test project; the pre-existing development volume was not reset. Stop without erasing development volumes using:

```powershell
docker compose --env-file .env.local down
```
