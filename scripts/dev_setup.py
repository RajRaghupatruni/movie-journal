"""Create local-only database configuration without reading or replacing legacy .env."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / ".env.local"
runtime_password = secrets.token_hex(24)
migration_password = secrets.token_hex(24)
bootstrap_password = secrets.token_hex(24)
try:
    with target.open("x", encoding="utf-8") as output:
        output.write(
            "APP_ENV=development\n"
            "POSTGRES_DB=tandem\n"
            "POSTGRES_USER=tandem_bootstrap\n"
            f"POSTGRES_PASSWORD={bootstrap_password}\n"
            "POSTGRES_MIGRATION_USER=tandem_migrator\n"
            f"POSTGRES_MIGRATION_PASSWORD={migration_password}\n"
            "POSTGRES_RUNTIME_USER=tandem_app\n"
            f"POSTGRES_RUNTIME_PASSWORD={runtime_password}\n"
            "POSTGRES_RLS_OWNER_ROLE=tandem_rls_owner\n"
            f"DATABASE_URL=postgresql+psycopg://tandem_app:{runtime_password}@127.0.0.1:5432/tandem\n"
            f"MIGRATION_DATABASE_URL=postgresql+psycopg://tandem_migrator:{migration_password}@127.0.0.1:5432/tandem\n"
        )
    print(
        "Created ignored .env.local with a new local database password. No provider credentials added."
    )
except FileExistsError:
    print(
        ".env.local already exists; left unchanged. Check its settings before starting Compose."
    )
