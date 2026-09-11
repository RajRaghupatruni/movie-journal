# Tandem V1 live regression report

## Verdict

**TANDEM V1 RELEASE VALIDATION: PASS**

The final deployed V1 regression run passed all four production tests with one worker: anonymous
security/readiness smoke, OAuth redirect smoke, authenticated mutation preflight, and the complete
one-account journey. The journey completed provider validation, private media checks, rediscovery,
navigation, recovery, and cleanup. All established frontend, backend, PG18/RLS, security, lint,
Alembic, and mocked acceptance gates are green, with no unresolved P0/P1 product defects.

Every discoverable V1 path in the regression inventory is accounted for; all automated
production/integration/component gates pass; remaining second-human OAuth and irreversible
account-lifecycle scenarios are explicitly manual.

## Build and database under test

- Production URL: `https://tandem-web-xnih.onrender.com`
- Production surface observed: Login shell, Render health, readiness, liveness, OAuth entry point.
- Production build commit: not exposed by the public application headers/API; the deployed URL was tested directly.
- Production migration head supplied for this validation: `0016_v1_completion`.
- Validation branch: `codex/v1-regression-validation`.
- Repository baseline before validation: `6994fb0 merge: Tandem V1 feature complete`.
- Final regression-harness commit: `415deba test: stabilize production regression suite`.
- PostgreSQL integration database: PostgreSQL 18.6 with the final V1 migration chain through `0016_v1_completion`.

## Inventory totals

The code-derived matrix in [`v1-regression-matrix.md`](v1-regression-matrix.md) contains **136
regression cases**:

| Classification | Count |
|---|---:|
| LIVE-AUTOMATED | 8 |
| LOCAL-INTEGRATION | 104 |
| UNIT/COMPONENT | 11 |
| MANUAL | 13 |
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
| Live production Playwright directory | 4 passed, 1 worker; anonymous smoke and authenticated journey both passed |
| Live one-account mutation preflight | Passed; browser-origin create/list/delete cleanup verified |
| Live one-account full journey | Passed; provider, media, rediscovery, navigation, recovery, and cleanup completed |
| Secret scan | 185 paths scanned, 0 findings |
| Failed tests | 0 |
| Skipped tests | 0 |

## Live production coverage actually executed

The production suite required `TANDEM_LIVE_PRODUCTION=true` and the exact production hostname.
The final command was `npx playwright test tests/e2e/production --config=playwright.production.config.ts`
with `TANDEM_LIVE_WRITE=true`, the saved local Google-authenticated state, and a unique E2E
namespace. It ran with one worker and finished **4/4 passed**. It verified:

- Root shell returns 200 and renders the Login page.
- `/api/health` returns `status=ok`, `application=ok`, `database=ok`.
- `/api/readyz` returns the same readiness payload.
- `/healthz` returns process liveness.
- `/api/me` rejects an unauthenticated request with 401.
- Cross-origin unauthenticated POST to `/api/tandems` is rejected with 403.
- `/auth/google/login` redirects to Google and does not expose a client secret or database URL.
- HSTS, CSP, no-store/cache, frame, referrer, and content-type security headers were present.
- The public smoke explicitly used empty cookies/origins despite the global production state.
- The authenticated journey used the saved real Google OAuth state, created only namespaced
  resources, and cleaned them up before completion.

Google OAuth itself remains real and was completed through the supplied local storage state; no
test-login endpoint or bypass was added. The one-account continuation is implemented in
`single-account-write.spec.ts` and requires the explicit `TANDEM_LIVE_WRITE=true` opt-in.

The original 403 was a test-harness mismatch. Production `SameOriginMiddleware` rejects unsafe
methods without an `Origin` or `Referer` resolving to the configured frontend origin. Raw
Playwright `APIRequestContext` supplied cookies but no browser origin. The suite now sends every
production mutation through `page.evaluate(fetch(..., credentials: 'same-origin'))`, matching the
real frontend contract. Product security code was unchanged.

## Feature-area results

| Area | Result | Evidence / limitation |
|---|---|---|
| Global and scoped navigation | MANUAL | One-account live navigation is implemented; PG18/backend and mocked browser coverage already pass |
| Add Memory categories | MANUAL | One-account live creation is implemented; local category/API coverage passes |
| Movie and place providers | LIVE-AUTOMATED | Live TMDb search/artwork and Geoapify search/persistence passed after the response-normalization fix |
| Photos and private media | LIVE-AUTOMATED | Live B2 upload, complete presigned read, unsigned private-object denial, and cleanup passed |
| Memory detail/reflections/reactions | LOCAL-INTEGRATION | Backend and mocked acceptance coverage |
| Recently Deleted | LIVE-AUTOMATED | One-account live delete/restore/permanent-delete journey passed; local purge logic also passes |
| Invitations | LOCAL-INTEGRATION | Pending/accepted/declined/revoked/expired/resend and isolation coverage; second-human OAuth remains manual |
| Members/owners | LOCAL-INTEGRATION | A/B/C, owner/member, final-owner, removal and concurrency tests |
| People & settings | LOCAL-INTEGRATION | Preferences, Tandem settings, role controls and defaults covered locally |
| Notifications | LOCAL-INTEGRATION | Read/read-all, invitation/member/anniversary/dedupe logic covered locally |
| Rediscovery | LIVE-AUTOMATED | Enabled and disabled resurfacing states passed in the one-account journey; local eligibility coverage also passes |
| Account lifecycle | MANUAL | Deactivate/reactivate may use the one account if safe; account deletion is prohibited for the available identity |
| Anniversary worker | MANUAL | Candidate/timezone/outbox tests pass; live manual Render trigger requires operator access |
| Browser navigation/visual state | LOCAL-INTEGRATION | Existing desktop mocked acceptance screenshots and history/mode tests |
| Security/RLS | LOCAL-INTEGRATION | PG18 A/B/C and adversarial identifier coverage; unauthenticated live boundary also passed |

## Defects

- **Product defect, fixed (P2): Geoapify response normalization.** Production requests used
  `format=json`, whose valid payload exposes `results[]`; the parser expected GeoJSON `features[]`.
  Broad valid searches therefore returned `items: []` without surfacing a provider failure. Commit
  `ae97f68a99c96fa26092cecb087ce5142347039` corrected the parser and made malformed provider
  schemas fail explicitly. The fix was deployed and the subsequent live journey successfully
  searched and persisted a place memory. No unresolved product defect remains from this run.

### Test-harness defects fixed

1. Raw `APIRequestContext` mutations lacked the browser origin required by
   `SameOriginMiddleware`; mutations now use authenticated page fetches. Product security was not
   weakened.
2. Unsigned private Backblaze objects returned 401, a valid denial; the harness now proves both
   complete presigned access and unsigned-object denial.
3. Year Review was incorrectly expected to remain populated after resurfacing was disabled; the
   journey now verifies enabled and disabled states separately.
4. The combined run inherited authenticated storage in the anonymous smoke and used a 30-second
   timeout for the long journey; the harness now uses explicit empty anonymous storage, a bounded
   120-second journey timeout, and one production worker.

These were test-only corrections. No backend, product security, authentication, or authorization
behavior was changed.

The initial live browser/API checks exposed no application failure. A direct browser navigation
to a JSON endpoint was blocked by the automation browser client, so the same read-only check was
verified through the HTTP client and Playwright request fixture; this is a test-tool limitation.

## Manual production cases and operator inputs

1. Capture or refresh the available account's local Playwright storage state through normal Google
   OAuth; do not print or commit it.
2. Treat second-human invite acceptance, forwarded/wrong-account continuation, and cross-account
   live B2 denial as MANUAL; their lower-layer evidence is the PG18 security suite.
3. Provide Render operator access for the anniversary worker's safe manual trigger.
4. Keep permanent account deletion, deactivation of the primary identity, and injected B2/provider
   failures outside production; use disposable staging identities/fixtures for those confirmations.

The one-account storage-state and run procedure is documented in [`LIVE_REGRESSION_AUTH.md`](LIVE_REGRESSION_AUTH.md).
Storage state files, cookies, tokens, and provider credentials remain gitignored and were not
printed or committed.

## Artifacts

- Existing local mocked acceptance screenshots remain under `test-results/`.
- Production Playwright configuration retains screenshots, video, and traces on failure under
  `test-results/live/<run-id>/`; the final passing run produced no failure trace/video artifact.
- `playwright/.auth` and `test-results/live` contain no tracked runtime artifacts or secrets.

## Validation commit

The final harness commit is `415deba test: stabilize production regression suite`; this branch is
not merged into `main`.
