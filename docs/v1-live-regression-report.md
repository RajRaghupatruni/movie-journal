# Tandem V1 live regression report

## Verdict

**TANDEM V1 RELEASE VALIDATION: FAIL**

This verdict is conservative: the deployed V1 passed all safe live read-only checks and all
local/PG18 regression suites, but authenticated production writes, A/B/C production isolation,
live provider/media writes, scheduled-worker execution, and destructive account/resource flows
were not executed because dedicated disposable production identities and storage/provider
fixtures were not available. They are explicitly blocked below.

## Build and database under test

- Production URL: `https://tandem-web-xnih.onrender.com`
- Production surface observed: Login shell, Render health, readiness, liveness, OAuth entry point.
- Production build commit: not exposed by the public application headers/API; the deployed URL was tested directly.
- Production migration head supplied for this validation: `0016_v1_completion`.
- Validation branch: `codex/v1-regression-validation`.
- Repository baseline before validation: `6994fb0 merge: Tandem V1 feature complete`.
- PostgreSQL integration database: PostgreSQL 18.6 with the final V1 migration chain through `0016_v1_completion`.

## Inventory totals

The code-derived matrix in [`v1-regression-matrix.md`](v1-regression-matrix.md) contains **136
regression cases**:

| Classification | Count |
|---|---:|
| LIVE-AUTOMATED | 6 |
| LOCAL-INTEGRATION | 102 |
| UNIT/COMPONENT | 11 |
| MANUAL | 11 |
| BLOCKED | 6 |
| Total | 136 |

Inventory counts:

- Frontend routes/states: 16.
- Backend HTTP routes: 61.
- Forms, modals, drawers, menus, and conditional action surfaces: 20.
- Destructive actions: 8 (delete memory, permanent delete, delete Tandem, leave, remove member, revoke invitation, deactivate account, delete account).
- Role/state branches: 14 explicit A/B/C/D/E/F/G and Tandem-state cases.
- Domain tables: 19.
- RLS/authorization helper and policy families: covered in the database section of the matrix.

## Executed results

| Suite | Result |
|---|---:|
| Frontend Vitest | 31 passed in 8 files |
| Mocked Playwright acceptance | 4 passed |
| Backend + PG18 integration/RLS/security | 77 passed, 3 warnings |
| Ruff check | passed |
| Ruff format check | passed; 80 files formatted |
| Alembic current/check | `0016_v1_completion (head)`; no drift |
| Live read-only Playwright | 2 passed |
| Secret scan | 185 paths scanned, 0 findings |
| Failed tests | 0 |
| Skipped tests | 0 |

## Live production coverage actually executed

The production suite required `TANDEM_LIVE_PRODUCTION=true` and the exact production hostname.
It verified:

- Root shell returns 200 and renders the Login page.
- `/api/health` returns `status=ok`, `application=ok`, `database=ok`.
- `/api/readyz` returns the same readiness payload.
- `/healthz` returns process liveness.
- `/api/me` rejects an unauthenticated request with 401.
- Cross-origin unauthenticated POST to `/api/tandems` is rejected with 403.
- `/auth/google/login` redirects to Google and does not expose a client secret or database URL.
- HSTS, CSP, no-store/cache, frame, referrer, and content-type security headers were present.

Google OAuth itself was not completed automatically. The normal OAuth entry point remains real;
no test-login endpoint or bypass was added.

## Feature-area results

| Area | Result | Evidence / limitation |
|---|---|---|
| Global and scoped navigation | LOCAL-INTEGRATION | Mocked browser acceptance plus frontend/backend tests; live authenticated scope blocked |
| Add Memory categories | LOCAL-INTEGRATION | Form/unit/API coverage for movie/place/trip/activity/custom; live provider writes blocked |
| Movie and place providers | MANUAL | Real TMDb/Geoapify search requires a safe live test namespace and credentials |
| Photos and private media | LOCAL-INTEGRATION | Validation/storage mocks and API coverage; live B2 upload/read/cleanup blocked |
| Memory detail/reflections/reactions | LOCAL-INTEGRATION | Backend and mocked acceptance coverage |
| Recently Deleted | LOCAL-INTEGRATION | Delete/restore/purge logic covered locally; live permanent deletion blocked |
| Invitations | LOCAL-INTEGRATION | Pending/accepted/declined/revoked/expired/resend and isolation coverage; live OAuth continuation blocked |
| Members/owners | LOCAL-INTEGRATION | A/B/C, owner/member, final-owner, removal and concurrency tests |
| People & settings | LOCAL-INTEGRATION | Preferences, Tandem settings, role controls and defaults covered locally |
| Notifications | LOCAL-INTEGRATION | Read/read-all, invitation/member/anniversary/dedupe logic covered locally |
| Rediscovery | LOCAL-INTEGRATION | Shuffle, year review, collections and eligibility logic covered locally |
| Account lifecycle | LOCAL-INTEGRATION | Deactivate/reactivate/session cleanup locally; live irreversible deletion blocked |
| Anniversary worker | LOCAL-INTEGRATION | Candidate, timezone, outbox, retry/cancel tests; live cron trigger blocked |
| Browser navigation/visual state | LOCAL-INTEGRATION | Existing desktop mocked acceptance screenshots and history/mode tests |
| Security/RLS | LOCAL-INTEGRATION + LIVE-AUTOMATED | PG18 A/B/C and adversarial identifier coverage; unauthenticated live boundary passed |

## Defects

No product defect was reproduced by the executed suites. There are no P0, P1, P2, or P3 defects
to report from this run.

The initial live browser/API checks exposed no application failure. A direct browser navigation
to a JSON endpoint was blocked by the automation browser client, so the same read-only check was
verified through the HTTP client and Playwright request fixture; this is a test-tool limitation,
not a product defect.

## Blocked production cases and unblock actions

1. Authenticated owner A smoke and writes: capture a dedicated A storage state through normal Google OAuth.
2. B/C isolation and membership lifecycle: capture dedicated B and C storage states and use a unique `[E2E]` Tandem.
3. TMDb, Geoapify, and B2 live writes: provision an explicit disposable provider/storage namespace and cleanup plan.
4. Permanent deletion, deactivation, and account deletion: use disposable identities and a second destructive opt-in.
5. Anniversary cron/manual execution: obtain Render operator access and a disposable anniversary fixture.
6. B2 cleanup failure/retry: use a disposable object namespace and inject failure outside production.

The storage-state procedure is documented in [`LIVE_REGRESSION_AUTH.md`](LIVE_REGRESSION_AUTH.md).
Storage state files, cookies, tokens, and provider credentials remain gitignored and were not
printed or committed.

## Artifacts

- Existing local mocked acceptance screenshots remain under `test-results/`.
- Production Playwright configuration retains screenshots, video, and traces on failure under `test-results/live/<run-id>/`.
- The passing live run produced no failure trace/video artifact.

## Validation commit

The validation commit containing these artifacts is reported in the completion response. This
branch is not merged into `main`.
