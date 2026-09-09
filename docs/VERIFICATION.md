# Foundation verification — 2026-09-09

## Passed

| Check | Result |
| --- | --- |
| Baseline frontend build | Passed before source edits; baseline lint had 2 errors / 2 warnings |
| Final `npm test` | 7 tests, 2 source test files; malicious stored HTML and disabled provider request boundary |
| Final `npm run build` | Strict TypeScript check and Vite production build passed |
| `npm audit fix` | Compatible dependency fixes; resulting npm audit reported zero vulnerabilities |
| Backend `pytest` | 17 passed with `TEST_DATABASE_URL`, both Windows Python 3.13 and Linux container; ordinary unit run is 16 passed / 1 opt-in skip |
| `ruff check backend/app backend/tests backend/alembic` | Passed |
| `docker compose --env-file .env.local up --build -d --wait` | Frontend, backend, PostgreSQL 16 and Redis all healthy |
| HTTP health | Direct port 8000 and Vite `/api` proxy on port 5173 returned 200 and application/database `ok`; UUID request ID returned |
| Database failure/recovery | Stopped only the new local PostgreSQL container: health returned 503 with generic `database: unavailable`; restarted it: health returned 200 without backend restart |
| Alembic | `upgrade head`, `current`, `check`, `downgrade base`, `upgrade head` all passed; final revision `0001_foundation`; no autogenerate drift |
| Persistence | PostgreSQL restart retained the Alembic revision; named PostgreSQL and Redis volumes configured; Redis uses AOF and returned `PONG` |
| Local backend configuration | Local Alembic connected successfully using generated ignored `.env.local` |
| Source secret guard / Gitleaks | Nonignored current source clean; exact public Firebase client-key exception only |
| Bundle secret check | No matches for the local TMDb/Foursquare provider values in rebuilt `dist`; values were compared in memory, never printed |
| Git hygiene | `.env` and generated Firebase cache staged for removal from tracking, local files preserved; `.env`/`.env.local` ignored; `git diff --check` clean |

Backend tests cover successful/degraded health, database exception redaction, unhandled-error response redaction, structured correlation logs, invalid request IDs, local CORS allow/reject behavior, production CORS disabled, required/invalid environment validation, masked settings, session cleanup and a real PostgreSQL query. No product tables or application records were created.

## Browser and legacy limits

Read-only in-app browser navigation at `http://127.0.0.1:5173` reached Search, Watched, Watchlist and Timeline. The search-disabled notice and existing filter/sort controls rendered. Firebase snapshot listeners returned `permission-denied`; the empty states therefore do **not** establish that the database has no records. No Firestore records were retrieved or mutated, and add/edit/delete persistence was not verified. Deployed Firestore rules were not inspected or modified.

Movie and place provider search is deliberately disabled until separately implemented backend integrations can hold rotated secrets. This limitation is documented rather than bypassed with a browser API key or an unauthenticated provider proxy.

Existing lint debt remains: unused `lastDeleted` in Watchlist, and hook warnings in Edit Movie and Foursquare Search. Build warnings remain for large JavaScript chunks and the redundant Tailwind line-clamp plugin. Python tests report two upstream deprecation warnings (Starlette's httpx test client and AnyIO BlockingPortal alias); assertions pass. No cosmetic cleanup was added to this milestone.

The new GitHub Actions workflow was authored but not run remotely. Its core build/test/migration/scanning commands were run locally. No Firebase deployment, Git commit/push, history rewrite, OAuth, user/group migration, provider revocation, Redis feature or media storage work was performed.

## Historical credential incident

Gitleaks scanned the six locally available Git commits. With the Firebase public-config exception and a corrected provider-assignment rule, it still reports the TMDb credential in `.env` at initial commit `e7c942f`. This expected historical failure is distinct from the clean current-source result. Foursquare and any other previously committed provider secrets must also be treated as compromised regardless of scanner coverage. Revocation, historical/deployed artifact cleanup and deployed Firebase access review remain manual actions.

## Reproduce

Use the exact setup and command sequences in [README.md](../README.md). The four local development containers were left running and healthy, with the database at `0001_foundation`. Stop without erasing volumes using:

```powershell
docker compose --env-file .env.local down
```
