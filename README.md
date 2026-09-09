# Tandem

The existing React movie journal is evolving into a private shared-memory application. This milestone adds FastAPI/PostgreSQL infrastructure and security cleanup. The UI still uses legacy Firestore; authentication, application-data migration and new product features are not implemented.

Read the [repository audit](docs/REPOSITORY_AUDIT.md), [target architecture](docs/TARGET_ARCHITECTURE.md), and [verification results](docs/VERIFICATION.md). Desktop is the target; old root planning documents are historical.

**Manual action:** revoke every previously committed TMDb/Foursquare credential. Local `.env` was preserved but untracked; old Git history and deployed bundles still require incident cleanup. Live movie/place search is temporarily disabled to remove browser secrets. Saved records and existing Firestore workflows are retained.

The read-only browser smoke check received Firestore `permission-denied` errors. Saved-data access cannot be verified until the project owner reviews the existing deployed rules/access configuration. No rules were changed and no records were written.

## Full development stack

Requires Docker Desktop with Linux containers and Python 3.12+ for the setup helper:

```powershell
python scripts/dev_setup.py
docker compose --env-file .env.local up --build -d --wait
docker compose --env-file .env.local exec backend alembic upgrade head
docker compose --env-file .env.local ps
```

The helper creates ignored `.env.local` with a random **local database** password, without reading or overwriting legacy `.env`. Existing `.env.local` is never overwritten. `.env.example` contains names and empty values only; it is a reference, not runnable configuration. Always supply `--env-file .env.local` to Compose.

- [Frontend](http://localhost:5173), [API health](http://localhost:8000/api/health), [API docs](http://localhost:8000/docs).
- PostgreSQL 16: loopback port 5432; migrations use `tandem_migrator` and the API uses the non-bypass-RLS `tandem` role by default.
- Redis 7: loopback port 6379, AOF persistence, currently unused by the backend.

Resolve existing port conflicts before startup. All published ports bind to `127.0.0.1`. Source is copied into images: rebuild after changes. `docker compose --env-file .env.local down` stops the stack and preserves named volumes. Adding `--volumes` erases development data. Changing `.env.local` does not rotate a password in an initialized PostgreSQL role. This Compose file is for local development, not public deployment.

## Local frontend/backend with hot reload

Use Node 22.12+ (current Node 22 LTS preferred), npm and Python 3.12+ (verified on 3.13). Stop the full stack to free application ports, then run from repository root:

```powershell
python scripts/dev_setup.py
docker compose --env-file .env.local up -d --wait postgres redis
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

Build includes strict TypeScript checks; legacy JSX remains JavaScript. `npm run lint` still reports documented pre-existing issues. Container checks:

```powershell
docker compose --env-file .env.local exec backend python -m pytest -q -p no:cacheprovider
docker compose --env-file .env.local exec backend alembic current
docker compose --env-file .env.local exec backend alembic check
docker compose --env-file .env.local exec redis redis-cli ping
```

The integration test skips unless both `TEST_DATABASE_URL` and `TEST_DATABASE_OWNER_URL` are set. The former must use the non-bypass-RLS runtime role; the latter is used only to migrate and provision deterministic test identities. To use the isolated local Compose database without printing credentials:

```powershell
docker compose --env-file .env.local exec backend python -c "import os,pytest; os.environ['TEST_DATABASE_OWNER_URL']=os.environ['DATABASE_URL']; os.environ['TEST_DATABASE_URL']='postgresql+psycopg://tandem_runtime:fixture@postgres:5432/tandem'; raise SystemExit(pytest.main(['-q','-p','no:cacheprovider']))"
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
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Compose bootstrap; password required and generated locally |
| `POSTGRES_MIGRATION_USER`, `POSTGRES_MIGRATION_PASSWORD` | Dedicated schema-migration role; initialized on a fresh PostgreSQL volume |
| `DATABASE_URL`, `DATABASE_RUNTIME_ROLE` | API runtime URL and expected non-superuser/non-`BYPASSRLS` role |
| `MIGRATION_DATABASE_URL` | Alembic URL for the dedicated migration role |
| `CORS_ORIGINS` | JSON array of local HTTP origins; defaults to localhost and 127.0.0.1 port 5173, enabled in development only |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Google OIDC client configuration; required only when enabling Google login |
| `FRONTEND_URL` | Post-login redirect origin |
| `API_PROXY_TARGET` | Vite **process environment** override; defaults to http://127.0.0.1:8000, Compose uses http://backend:8000 |
| `REDIS_URL` | Reserved future name, not currently read or required |

No `VITE_*` values are exposed. Firebase client identifiers remain public config pending migration. Google login uses server-side sessions and does not store provider access tokens. A fresh Compose volume creates the migration/runtime role split; an existing volume must be provisioned manually before the API is run with a non-superuser runtime URL. Follow the audit's ordered migration plan before feature development or deployment.
