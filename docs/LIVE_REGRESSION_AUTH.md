# Live regression authentication workflow

Production regression does not add a test-login endpoint, auth bypass, or special cookie. Use
dedicated disposable Google identities A, B, and C through the normal OAuth flow.

1. Create or obtain dedicated Google test identities. Do not use a primary account.
2. Save each Playwright storage state locally, outside Git:

```powershell
New-Item -ItemType Directory -Force playwright/.auth | Out-Null
npx playwright codegen --save-storage=playwright/.auth/user-a.json https://tandem-web-xnih.onrender.com/
npx playwright codegen --save-storage=playwright/.auth/user-b.json https://tandem-web-xnih.onrender.com/
npx playwright codegen --save-storage=playwright/.auth/user-c.json https://tandem-web-xnih.onrender.com/
```

Complete Google OAuth manually in each browser window. Never paste credentials, OTPs, cookies,
or storage-state contents into the terminal or logs. Close the browser after the state is saved.

3. Run the explicitly production-safe suite first:

```powershell
$env:TANDEM_LIVE_PRODUCTION = 'true'
$env:TANDEM_E2E_BASE_URL = 'https://tandem-web-xnih.onrender.com'
$env:TANDEM_E2E_RUN_ID = (Get-Date -Format 'yyyyMMdd-HHmmss')
$env:TANDEM_STORAGE_STATE = 'playwright/.auth/user-a.json'
npx playwright test --config=playwright.production.config.ts --grep '@read-only'
```

Authenticated write, multi-user, provider, and destructive suites must use the same explicit
hostname/opt-in checks plus a unique `[E2E]` namespace and tracked resource IDs. Account deletion
requires a second explicit opt-in and a disposable identity. No production suite should delete
or mutate arbitrary pre-existing Tandems, memories, members, or invitations.
