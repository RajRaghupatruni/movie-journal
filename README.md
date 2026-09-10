# Tandem

Tandem is an invite-only shared-memory application for small groups. PostgreSQL is authoritative
for Tandems, members, invitations, memories, participants, tags, and private media. A Tandem can
have up to five accepted members in v1.

Read the [repository audit](docs/REPOSITORY_AUDIT.md), [target architecture](docs/TARGET_ARCHITECTURE.md), [production runbook](docs/PRODUCTION_RUNBOOK.md), and [verification results](docs/VERIFICATION.md). Desktop is the target; old root planning documents are historical.

**Manual action:** revoke every previously committed provider credential. Previously committed
secrets and old deployed artifacts require separate incident cleanup. Legacy providers have no
active runtime role; Geoapify is the active place provider.

## Full development stack

Requires Docker Desktop with Linux containers and Python 3.12+ for the setup helper:

```powershell
python scripts/dev_setup.py
docker compose --env-file .env.local up --build -d --wait
docker compose --env-file .env.local exec backend alembic upgrade head
docker compose --env-file .env.local ps
```

The helper creates ignored `.env.local` with separate random migration-admin and runtime passwords, without reading or overwriting legacy `.env`. Existing `.env.local` is never overwritten. `.env.example` contains names and empty values only; it is a reference, not runnable configuration. Always supply `--env-file .env.local` to Compose.

- [Frontend](http://localhost:5173), [API health](http://localhost:8000/api/health), [API docs](http://localhost:8000/docs).
- PostgreSQL 18: loopback port 5432; migrations use `tandem_migrator`, the API uses the non-bypass-RLS `tandem_app` role, and RLS authorization helpers use the non-login `tandem_rls_owner` role.

Resolve existing port conflicts before startup. All published ports bind to `127.0.0.1`. Source is copied into images: rebuild after changes. `docker compose --env-file .env.local down` stops the stack and preserves named volumes. Adding `--volumes` erases development data. Changing `.env.local` does not rotate a password in an initialized PostgreSQL role. This Compose file is for local development, not public deployment.

## Local frontend/backend with hot reload

Use Node 22.12+ (current Node 22 LTS preferred), npm and Python 3.12+ (verified on 3.13). Stop the full stack to free application ports, then run from repository root:

```powershell
python scripts/dev_setup.py
  docker compose --env-file .env.local up -d --wait postgres
npm ci
npm run dev
```

In another terminal from repository root:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.lock
backend/.venv/Scripts/python -m pip install --no-deps -e backend
cd backend
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000 --no-access-log
```

On macOS/Linux replace `Scripts` with `bin`. If PowerShell blocks npm, use `npm.cmd`. Backend settings read root `.env.local` independently of working directory; process environment overrides it. Run Alembic from `backend`, or explicitly supply its config path. No migrations run automatically at startup.

`requirements.lock` pins the verified Python dependency set including development tools; `pyproject.toml` declares direct ranges. Update the lock intentionally in an isolated environment and verify the Linux container as well. Never freeze unrelated applications or editable local paths into it.

## Checks

From repository root:

```powershell
npm test
npm run build
python scripts/scan_secrets.py
backend/.venv/Scripts/python -m pytest backend/tests -q
backend/.venv/Scripts/python -m ruff check backend/app backend/tests backend/alembic
```

Build includes strict TypeScript checks; legacy JSX remains JavaScript. Container checks:

```powershell
docker compose --env-file .env.local exec backend python -m pytest -q -p no:cacheprovider
docker compose --env-file .env.local exec backend alembic current
docker compose --env-file .env.local exec backend alembic check
```

The integration tests use both `TEST_DATABASE_URL` (non-bypass-RLS runtime role) and `TEST_DATABASE_OWNER_URL` (migration/admin role). Start a clean disposable PostgreSQL 18 test database in its own Compose project; this does not touch the development volume:

```powershell
$env:POSTGRES_PASSWORD = 'disposable-bootstrap-password'
$env:POSTGRES_MIGRATION_PASSWORD = 'disposable-migration-password'
$env:POSTGRES_RUNTIME_PASSWORD = 'disposable-runtime-password'
docker compose -p tandem-pg-test -f compose.postgres-test.yaml up -d --wait
$env:TEST_DATABASE_URL = 'postgresql+psycopg://tandem_app:disposable-runtime-password@127.0.0.1:55432/tandem_test'
$env:TEST_DATABASE_OWNER_URL = 'postgresql+psycopg://tandem_migrator:disposable-migration-password@127.0.0.1:55432/tandem_test'
$env:DATABASE_RUNTIME_ROLE = 'tandem_app'
$env:DATABASE_RLS_OWNER_ROLE = 'tandem_rls_owner'
python -m pytest backend/tests -q
```

Use throwaway values only. Remove that isolated database after verification with `docker compose -p tandem-pg-test -f compose.postgres-test.yaml down --volumes`; never use `--volumes` on the normal development project unless its data has been backed up and intentionally discarded. The test volume is deliberately separate from `tandem_postgres_data`.

For an existing development volume, changing `.env.local` does not rotate PostgreSQL role passwords or run init scripts again. Stop the stack without data loss, back up anything needed, and use the explicit clean reset only when the volume is disposable:

```powershell
docker compose --env-file .env.local down
docker compose --env-file .env.local down --volumes  # destructive: only after confirming development data may be erased
```

Then rerun `python scripts/dev_setup.py` (which will leave an existing `.env.local` unchanged, so replace it only after preserving any needed values) and start Compose again. A production database must be repaired with an explicit role/password migration; do not apply the disposable reset procedure.

The former one-line shortcut below is retained for an already configured stack, but it is not a substitute for the two-role test setup:

```powershell
docker compose --env-file .env.local exec backend python -c "import os,pytest; os.environ['TEST_DATABASE_OWNER_URL']=os.environ['MIGRATION_DATABASE_URL']; os.environ['TEST_DATABASE_URL']=os.environ['DATABASE_URL']; raise SystemExit(pytest.main(['-q','-p','no:cacheprovider']))"
```

The empty baseline supports `alembic downgrade base` then `alembic upgrade head` on a disposable development database. Review future migrations before downgrade: they may remove real data. Health checks test connectivity, not migration revision.

## Secret scanning

The Python source guard scans tracked and nonignored new source, rejects tracked env files and nonempty example values, and prints filenames/rules only. For a full Gitleaks source scan:

```powershell
python scripts/scan_secrets.py --export
```

Mount the printed snapshot path (ignored local env files are excluded):

```text
docker run --rm -v "<printed-absolute-snapshot-path>:/repo:ro" zricethezav/gitleaks:v8.30.0 dir /repo --config /repo/.gitleaks.toml --redact --no-banner
```

CI gates current source with Gitleaks and the Python guard, runs frontend tests/build, backend tests against PostgreSQL, and Alembic upgrade/check/downgrade/upgrade. Historical scans use Gitleaks `git` with `--log-opts=--all` separately; historical findings remain an incident requiring rotation, not a reason to disable scanning.

## Configuration

| Name | Purpose |
| --- | --- |
| `APP_ENV` | development/test/production; defaults to development |
| `LOG_LEVEL` | DEBUG/INFO/WARNING/ERROR/CRITICAL; defaults to INFO |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Compose bootstrap role and password; local setup uses `tandem_bootstrap` so the migration role can remain a non-superuser |
| `POSTGRES_MIGRATION_USER`, `POSTGRES_MIGRATION_PASSWORD` | Dedicated schema-migration role; normally the same as the Compose bootstrap role; initialized on a fresh PostgreSQL volume |
| `POSTGRES_RUNTIME_USER`, `POSTGRES_RUNTIME_PASSWORD` | Separate API login; initialized as non-superuser and non-`BYPASSRLS` |
| `DATABASE_URL`, `DATABASE_RUNTIME_ROLE` | API runtime URL and expected non-superuser/non-`BYPASSRLS` role |
| `DATABASE_RLS_OWNER_ROLE` | Non-login `BYPASSRLS` role that owns only the bounded RLS authorization helpers |
| `MIGRATION_DATABASE_URL` | Alembic URL for the dedicated migration role |
| `CORS_ORIGINS` | JSON array of local HTTP origins; defaults to localhost and 127.0.0.1 port 5173, enabled in development only |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Google OIDC client configuration; required only when enabling Google login |
| `OAUTH_SESSION_SECRET` | Dedicated production-only secret for Authlib's transient OAuth session cookie; never the application auth/session or database secret |
| `FRONTEND_URL`, `APPLICATION_URL` | Same-origin post-login redirect/application URL; `APPLICATION_URL` is preferred for Render |
| `API_PROXY_TARGET` | Vite **process environment** override; defaults to http://127.0.0.1:8000, Compose uses http://backend:8000 |
| `EMAIL_DELIVERY_ENABLED` | Global outbound email capability; defaults to `false` for the v1 launch |
| `RESEND_API_KEY`, `RESEND_FROM_EMAIL` | Required only when `EMAIL_DELIVERY_ENABLED=true`; `RESEND_FROM_ADDRESS` remains accepted as a compatibility alias |

No `VITE_*` values are exposed. Google login uses server-side sessions and does not store provider
access tokens. A fresh Compose volume creates the migration/runtime role split; an existing volume
must be provisioned manually before the API is run with a non-superuser runtime URL.
