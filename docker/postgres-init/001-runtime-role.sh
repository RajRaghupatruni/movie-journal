#!/usr/bin/env bash
set -euo pipefail

runtime_user="${POSTGRES_RUNTIME_USER:-tandem_app}"
: "${POSTGRES_RUNTIME_PASSWORD:?POSTGRES_RUNTIME_PASSWORD must be set separately from POSTGRES_PASSWORD}"
runtime_password="$POSTGRES_RUNTIME_PASSWORD"
migration_user="${POSTGRES_MIGRATION_USER:-$POSTGRES_USER}"
migration_password="${POSTGRES_MIGRATION_PASSWORD:-$POSTGRES_PASSWORD}"
rls_owner_role="${POSTGRES_RLS_OWNER_ROLE:-tandem_rls_owner}"

if [[ "$runtime_user" == "$POSTGRES_USER" || "$runtime_user" == "$migration_user" ]]; then
  echo "POSTGRES_RUNTIME_USER must differ from the migration/admin role" >&2
  exit 1
fi

if [[ "$rls_owner_role" == "$runtime_user" || "$rls_owner_role" == "$migration_user" ]]; then
  echo "POSTGRES_RLS_OWNER_ROLE must differ from the migration and runtime roles" >&2
  exit 1
fi

# The official image creates POSTGRES_USER as the initial bootstrap role.
# Create the API and migration roles separately and make their RLS boundaries explicit.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=migration_user="$migration_user" \
  --set=migration_password="$migration_password" \
  --set=runtime_user="$runtime_user" \
  --set=runtime_password="$runtime_password" \
  --set=rls_owner_role="$rls_owner_role" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS', :'migration_user', :'migration_password')
WHERE :'migration_user' <> current_user
  AND NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'migration_user')\gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS', :'runtime_user', :'runtime_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'runtime_user')\gexec
SELECT format('CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION BYPASSRLS', :'rls_owner_role')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'rls_owner_role')\gexec
SELECT format('GRANT %I TO %I', :'rls_owner_role', :'migration_user')\gexec
SELECT format('ALTER ROLE %I NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS', :'migration_user')\gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', current_database(), :'migration_user')\gexec
SQL
