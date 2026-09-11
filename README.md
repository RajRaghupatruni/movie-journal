# Tandem

Tandem is an invite-only shared-memory application for small groups. PostgreSQL is authoritative
for Tandems, members, invitations, memories, participants, tags, and private media. A Tandem can
have up to five accepted members in v1.

Read the [repository audit](docs/REPOSITORY_AUDIT.md), [target architecture](docs/TARGET_ARCHITECTURE.md), [production runbook](docs/PRODUCTION_RUNBOOK.md), and [verification results](docs/VERIFICATION.md). Desktop is the target; old root planning documents are historical.

**Manual action:** revoke every previously committed provider credential. Previously committed
secrets and old deployed artifacts require separate incident cleanup. Legacy providers have no
active runtime role; Geoapify is the active place provider.

## What Tandem is

Tandem is a private, invite-only shared-memory application for small groups. It gives a group one
place to keep the moments that are easy to lose: movies, places, trips, activities, photos, notes,
ratings, reactions, and personal reflections. A Tandem is deliberately small, with a maximum of
five accepted members in V1, so the product can prioritize trust, context, and quiet rediscovery
over public social features.

V1 is feature frozen. This repository contains the working React application, the FastAPI service,
the PostgreSQL schema and RLS policies, the provider adapters, the private-media path, the bounded
anniversary worker, and the regression evidence for the deployed V1.

## V1 capabilities

- Create and manage multiple private Tandems with owner/member roles, invitations, promotion and
  demotion, member removal, leaving, and final-owner protection.
- Add memories as movies, places, trips, activities, or custom moments, with dates, trip ranges,
  participants, tags, ratings, notes, reflections, reactions, provider snapshots, and private
  photos.
- Browse a global Today and Calendar view, or focus on one Tandem through Timeline and Gallery
  views with search, category, year, and sort controls.
- Recover soft-deleted memories through Recently Deleted, then permanently purge eligible records
  with an explicit confirmation.
- Rediscover older memories through On This Day, deterministic Shuffle, Year Review, and Throwback
  Collections. Resurfacing and routine-notification preferences are scoped to each Tandem/user
  relationship.
- Receive in-app notifications for invitations, membership changes, ownership changes, and shared
  activity. Anniversary delivery is represented by a transactional outbox; outbound email remains
  disabled for V1.
- Search TMDb movies and Geoapify places through the backend, then store normalized snapshots so
  saved memories remain readable when a provider is unavailable.
- Upload private media through an S3-compatible interface such as Backblaze B2. The API stores
  metadata and issues short-lived signed URLs; raw object paths remain private.

## System design

```mermaid
flowchart LR
  Browser[React 19 / TypeScript boundaries / Vite]
    -->|same-origin JSON + session cookie| API[FastAPI application]
  API --> Auth[Google OAuth + opaque server sessions]
  API --> Domain[API routes + Pydantic schemas + services]
  Domain --> ORM[SQLAlchemy 2 + transaction boundaries]
  ORM --> DB[(PostgreSQL 18)]
  DB --> RLS[FORCE RLS + authorization helpers]
  API --> Providers[TMDb / Geoapify adapters]
  API --> Media[S3-compatible private storage]
  Scheduler[Hosted cron] --> Worker[Bounded anniversary worker]
  Worker --> DB
  Worker -. EMAIL_DELIVERY_ENABLED=false in V1 .-> Resend[Resend later]
  Compose[Docker Compose] --> API
  Compose --> DB
  Compose --> Redis[(Redis, reserved for later bounded uses)]
```

The browser is a presentation client. It calls purpose-specific FastAPI endpoints and never talks
directly to PostgreSQL, TMDb, Geoapify, or object storage credentials. The backend authenticates
the request, resolves the current user, sets a transaction-local PostgreSQL user context, applies
service-level authorization, and lets database RLS provide a second tenant boundary. PostgreSQL
is the source of truth for identity, membership, invitations, memories, notifications, and media
metadata.

The application is intentionally one deployable FastAPI service rather than a collection of
microservices. HTTP concerns live under `backend/app/api`, validation under `schemas`, domain
operations under `services`, persistence under `models` and `db`, and provider clients under
`integrations`. This keeps transaction ownership visible and makes a small private product easier
to operate. The anniversary worker is a bounded process over PostgreSQL; it does not require a
queue, Celery, or a separate worker service.

## Engineering decisions

### PostgreSQL is authoritative

Firebase was the legacy application's persistence layer. Tandem V1 does not add Firebase or a
dual-write bridge. PostgreSQL 18 owns the relational model, constraints, membership boundaries,
notifications, outbox state, soft deletion, and provider snapshots. Alembic is the only schema
change mechanism, and migrations run explicitly during deployment or development.

### Authorization is enforced in layers

FastAPI dependencies reject unauthenticated, non-member, and non-owner operations early. PostgreSQL
then enforces tenant isolation with `FORCE ROW LEVEL SECURITY`, including for table owners. The
runtime role `tandem_app` is `NOSUPERUSER` and `NOBYPASSRLS`. Narrow `SECURITY DEFINER` helpers are
owned by a separate `NOLOGIN BYPASSRLS` role, use a fixed safe `search_path`, expose only the
minimum membership fact, and grant `EXECUTE` only to the runtime role. This structure avoids the
recursive policy evaluation that caused the original production Tandem-creation failure.

### Sessions are server-side and same-origin

Google OAuth establishes identity, but Google tokens are not stored as application credentials.
The backend stores only a hash of a random opaque session token and sends the raw token in a
bounded `HttpOnly`, `Secure`, `SameSite=Lax` cookie. Unsafe browser requests must carry the expected
same-origin `Origin` or `Referer`. The production regression suite uses the same browser request
contract; it does not add a login endpoint or bypass.

### Transactions are explicit and short

Create Tandem plus owner membership is one transaction. Invitation acceptance, final-owner checks,
member capacity, memory mutations, notification creation, and outbox changes use explicit
transaction boundaries and row locks where needed. Optimistic versions protect shared memory edits.
The current-user RLS setting is transaction-local so a pooled connection cannot retain one user's
identity for the next request.

### Providers are adapters, not sources of truth

TMDb and Geoapify credentials stay in backend runtime configuration. Adapters validate and
normalize bounded responses, apply timeouts, and return controlled errors. Selecting a provider
result copies a snapshot into PostgreSQL; Timeline and Memory Detail do not depend on a later live
provider request. This also made the Geoapify `results[]` response-shape defect observable and
fixable rather than silently storing empty search results.

### Private media uses capabilities with an expiry

Media objects are private. The API validates uploads, stores metadata in PostgreSQL, and returns
short-lived signed URLs. Tests prove both sides of the contract: a complete signed URL can read the
object, while an unsigned object path is denied. Media cleanup is part of Tandem/memory deletion;
failures are recorded for operator retry.

### Preserve working UI while adding typed boundaries

Vite and npm remain in place. Existing JSX screens were preserved to avoid a cosmetic rewrite;
new API contracts and meaningful boundaries use strict TypeScript where practical. The target is
desktop-first. No PWA, mobile application, UI redesign, or broad JSX conversion was needed for V1.

## Engineering concepts used

- **Tenant isolation:** every private resource is scoped through memberships and Tandem IDs, with
  both API authorization and PostgreSQL RLS.
- **Least privilege:** separate migration, runtime, and RLS-helper roles; no runtime
  `BYPASSRLS`; provider secrets never enter frontend bundles.
- **Defense in depth:** same-origin checks, HttpOnly sessions, API dependencies, database policies,
  input schemas, upload validation, and safe error responses protect different failure layers.
- **Transactional outbox:** anniversary work records durable intent in PostgreSQL before a later
  worker considers delivery, with deduplication and retry state.
- **Optimistic concurrency:** memory updates carry an expected version so stale edits fail instead
  of silently overwriting a collaborator's change.
- **Soft deletion and recovery:** normal deletion removes a memory from active reads while retaining
  a bounded recovery path and an explicit permanent-delete operation.
- **Snapshotting:** external movie/place data is copied into the memory record to preserve history.
- **Structured observability:** request IDs, JSON logs, bounded error categories, health/readiness
  endpoints, and safe diagnostics make production failures actionable without logging secrets or
  user content.
- **Test-layer separation:** deterministic UI/backend tests run locally, PG18 tests prove RLS and
  multi-user boundaries, and the live suite uses real OAuth state only for safe namespaced flows.

## Future work

The following work is intentionally outside the frozen V1 product surface:

- Add a Tandem-scoped PostgreSQL watchlist with TMDb snapshots, authorized removal, and conversion
  into a movie memory. It must not revive the retired Firebase watchlist as a second source of truth.
- Complete an owner-approved legacy-data import plan. Existing Firebase records have unresolved
  ownership and must not be guessed into a Tandem; imports need dry runs, mapping, checksums,
  rollback, and explicit destination ownership.
- Enable Resend only after sender-domain setup, privacy review, and production delivery operations
  are ready. V1 keeps `EMAIL_DELIVERY_ENABLED=false`.
- Add shared rate limiting for multi-instance deployment. Current in-process limits are bounded but
  intentionally not a distributed security boundary.
- Add the next collaboration surfaces only when their data and notification semantics are clear:
  realtime updates, richer invitation delivery, and additional media operations.
- Continue incremental TypeScript migration and remove legacy Firebase code only after equivalent
  PostgreSQL-backed functionality and data parity are proven.
- Expand production validation with disposable second Google identities for wrong-recipient invites,
  cross-account denial, account deactivation, and account deletion. These remain manual today to
  avoid destructive testing against the primary identity.

See [`docs/ROADMAP.md`](docs/ROADMAP.md), [`docs/TARGET_ARCHITECTURE.md`](docs/TARGET_ARCHITECTURE.md),
and [`docs/v1-live-regression-report.md`](docs/v1-live-regression-report.md) for the detailed
follow-up list, architecture boundaries, and final validation evidence.

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
