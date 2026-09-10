# Tandem V1 live regression report

## Verdict

**TANDEM V1 RELEASE VALIDATION: FAIL**

The deployed V1 passed all safe live read-only checks and all local/PG18 regression suites. The
one-account authenticated production write/provider suite is implemented but has not been run in
this session because the operator has not supplied a local storage state. A/B/C authorization is
not blocked: it is proven in the exact PG18 production-shaped integration suite. The current FAIL
is therefore pending critical live write-wiring evidence, not caused by the lack of additional
Google accounts.

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
| LOCAL-INTEGRATION | 104 |
| UNIT/COMPONENT | 11 |
| MANUAL | 15 |
| BLOCKED | 0 |
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
| Live one-account write/provider Playwright | not run; operator storage state required |
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
no test-login endpoint or bypass was added. The one-account continuation is implemented in
`single-account-write.spec.ts` and requires the explicit `TANDEM_LIVE_WRITE=true` opt-in.

## Feature-area results

| Area | Result | Evidence / limitation |
|---|---|---|
| Global and scoped navigation | MANUAL | One-account live navigation is implemented; PG18/backend and mocked browser coverage already pass |
| Add Memory categories | MANUAL | One-account live creation is implemented; local category/API coverage passes |
| Movie and place providers | MANUAL | One-account live TMDb/Geoapify search requires the operator storage state and production provider wiring |
| Photos and private media | MANUAL | One-account B2 upload/read/delete is implemented; local private-media coverage passes |
| Memory detail/reflections/reactions | LOCAL-INTEGRATION | Backend and mocked acceptance coverage |
| Recently Deleted | LOCAL-INTEGRATION | Delete/restore/purge logic covered locally; one-account live recovery is implemented |
| Invitations | LOCAL-INTEGRATION | Pending/accepted/declined/revoked/expired/resend and isolation coverage; second-human OAuth remains manual |
| Members/owners | LOCAL-INTEGRATION | A/B/C, owner/member, final-owner, removal and concurrency tests |
| People & settings | LOCAL-INTEGRATION | Preferences, Tandem settings, role controls and defaults covered locally |
| Notifications | LOCAL-INTEGRATION | Read/read-all, invitation/member/anniversary/dedupe logic covered locally |
| Rediscovery | LOCAL-INTEGRATION | Shuffle, year review, collections and eligibility logic covered locally |
| Account lifecycle | MANUAL | Deactivate/reactivate may use the one account if safe; account deletion is prohibited for the available identity |
| Anniversary worker | MANUAL | Candidate/timezone/outbox tests pass; live manual Render trigger requires operator access |
| Browser navigation/visual state | LOCAL-INTEGRATION | Existing desktop mocked acceptance screenshots and history/mode tests |
| Security/RLS | LOCAL-INTEGRATION | PG18 A/B/C and adversarial identifier coverage; unauthenticated live boundary also passed |

## Defects

No product defect was reproduced by the executed suites. There are no P0, P1, P2, or P3 defects
to report from this run.

The initial live browser/API checks exposed no application failure. A direct browser navigation
to a JSON endpoint was blocked by the automation browser client, so the same read-only check was
verified through the HTTP client and Playwright request fixture; this is a test-tool limitation,
not a product defect.

## Manual production cases and operator inputs

1. Capture the available account's local Playwright storage state through normal Google OAuth.
2. Run the write suite with `TANDEM_LIVE_PRODUCTION=true`, `TANDEM_LIVE_WRITE=true`, a unique
   `TANDEM_E2E_NAMESPACE`, and the exact production URL.
3. Confirm the production account can safely create and delete only `[E2E]` Tandems and memories;
   do not delete the Google-backed account.
4. Provide Render operator access for the anniversary worker's safe manual run.
5. Treat second-human invite acceptance/wrong-account continuation and cross-account live B2
   denial as MANUAL; their lower-layer evidence is the PG18 security suite.
6. Keep permanent account deletion and injected B2 failure outside production; use disposable
   staging identities/fixtures if those flows need manual confirmation.

The one-account storage-state and run procedure is documented in [`LIVE_REGRESSION_AUTH.md`](LIVE_REGRESSION_AUTH.md).
Storage state files, cookies, tokens, and provider credentials remain gitignored and were not
printed or committed.

## Artifacts

- Existing local mocked acceptance screenshots remain under `test-results/`.
- Production Playwright configuration retains screenshots, video, and traces on failure under `test-results/live/<run-id>/`.
- The passing live run produced no failure trace/video artifact.

## Validation commit

The validation commit containing these artifacts is reported in the completion response. This
branch is not merged into `main`.
