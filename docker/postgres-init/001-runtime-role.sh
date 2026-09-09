#!/usr/bin/env bash
set -euo pipefail

migration_user="${POSTGRES_MIGRATION_USER:-${POSTGRES_USER}_migrator}"
migration_password="${POSTGRES_MIGRATION_PASSWORD:-$POSTGRES_PASSWORD}"

# The official image runs init scripts as the initial database superuser. Keep
# that privilege only for migrations and demote the login role used by the API.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=migration_user="$migration_user" \
  --set=migration_password="$migration_password" \
  --set=runtime_user="$POSTGRES_USER" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS', :'migration_user', :'migration_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'migration_user')\gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', current_database(), :'migration_user')\gexec
SELECT format('ALTER ROLE %I NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS', :'runtime_user')\gexec
SQL
