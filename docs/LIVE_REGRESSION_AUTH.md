# Live regression authentication workflow

V1 uses a hybrid release-validation model. One genuine Google account is sufficient for the
authenticated production journey; A/B/C authorization is proven in the PostgreSQL 18 integration
suite. No test-login endpoint, auth bypass, fake production user, or direct auth-table mutation is
allowed.

## Capture the one-account state

Use the available Google account through the normal OAuth flow. Do not use it for account deletion,
and do not print credentials, OTPs, cookies, storage-state contents, or tokens.

```powershell
New-Item -ItemType Directory -Force playwright/.auth | Out-Null
npx playwright codegen --save-storage=playwright/.auth/production-user.json https://tandem-web-xnih.onrender.com/
```

Complete Google OAuth manually in the browser window, confirm that the Tandem shell loads, then
close the browser. The resulting file is local-only and is ignored by Git.

## Run the live single-user suite

The suite refuses to run unless the hostname, production opt-in, write opt-in, storage state, and
namespace are all present. Every resource is named `[E2E] <namespace> ... <run-id>` and is tracked
for cleanup. Do not point this suite at an existing Tandem or memory.

```powershell
$env:TANDEM_LIVE_PRODUCTION = 'true'
$env:TANDEM_LIVE_WRITE = 'true'
$env:TANDEM_E2E_BASE_URL = 'https://tandem-web-xnih.onrender.com'
$env:TANDEM_E2E_NAMESPACE = 'v1-operator'
$env:TANDEM_E2E_RUN_ID = (Get-Date -Format 'yyyyMMdd-HHmmss')
$env:TANDEM_STORAGE_STATE = 'playwright/.auth/production-user.json'
npx playwright test --config=playwright.production.config.ts --grep '@write'
```

This exercises the one-account Tandem/memory/provider/media journey, preferences, rediscovery,
recovery, scope navigation, confirmation modals, and cleanup. It does not delete the Google-backed
account. If a provider or storage operation fails, retain the Playwright failure artifacts before
reviewing or cleaning up the namespaced resources.

To run the complete production regression directory, keep the same safety variables and use:

```powershell
npx playwright test tests/e2e/production --config=playwright.production.config.ts
```

The production configuration runs with one worker to prevent shared-account state interference.
The final V1 run completed 4/4 tests successfully. The read-only smoke file explicitly overrides
the global authenticated state with empty cookies/origins, so its Login and anonymous-boundary
assertions are genuinely unauthenticated. The write file alone consumes the saved Google-authenticated
state.

State-changing calls deliberately run through the authenticated `page` context with
`fetch(..., credentials: 'same-origin')`. Tandem production same-origin middleware requires a
browser `Origin` or `Referer`; raw APIRequestContext is reserved for read-only calls in this suite.

## Layer boundaries

- **LIVE**: genuine Google OAuth, Render/Neon/B2/provider wiring, one-account writes and reads.
- **PG18 integration**: A/B/C RLS, membership, invitation, reflection, identifier-isolation,
  final-owner, and deactivated-user behavior under production-shaped roles.
- **MANUAL**: second-human invitation acceptance/wrong-account continuation, visual OAuth prompts,
  worker operator action, and irreversible account deletion. These are not release failures when
  the lower-layer security evidence passes.

The read-only suite remains safe to run independently:

```powershell
$env:TANDEM_LIVE_PRODUCTION = 'true'
$env:TANDEM_E2E_BASE_URL = 'https://tandem-web-xnih.onrender.com'
npx playwright test --config=playwright.production.config.ts --grep '@read-only'
```

The read-only tests always use empty storage, even when `TANDEM_STORAGE_STATE` is set for the
production project. No storage-state, cookie, token, or provider credential file is committed.
