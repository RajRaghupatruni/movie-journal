"""Create local-only database configuration without reading or replacing legacy .env."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
target = root / ".env.local"
password = secrets.token_hex(24)
try:
    with target.open("x", encoding="utf-8") as output:
        output.write(
            "APP_ENV=development\n"
            "POSTGRES_DB=tandem\n"
            "POSTGRES_USER=tandem\n"
            f"POSTGRES_PASSWORD={password}\n"
            f"DATABASE_URL=postgresql+psycopg://tandem:{password}@127.0.0.1:5432/tandem\n"
        )
    print("Created ignored .env.local with a new local database password. No provider credentials added.")
except FileExistsError:
    print(".env.local already exists; left unchanged. Check its settings before starting Compose.")
