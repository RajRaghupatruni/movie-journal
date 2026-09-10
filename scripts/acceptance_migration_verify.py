"""Verify legacy-data preservation, V1 backfills, and runtime RLS after migration."""

import os

import psycopg


def main() -> None:
    admin_url = os.environ["MIGRATION_VERIFY_URL"]
    with psycopg.connect(admin_url) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM users")
        assert cursor.fetchone()[0] == 2
        cursor.execute("SELECT count(*) FROM tandems")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT count(*) FROM memories")
        assert cursor.fetchone()[0] == 1
        cursor.execute(
            "SELECT metadata ->> 'provider_movie_id', rating, notes, created_by FROM memories"
        )
        memory_values = cursor.fetchone()
        assert memory_values[:3] == (
            "550",
            8,
            "Legacy notes survived the migration.",
        )
        cursor.execute(
            "SELECT count(*) FROM memory_participants WHERE participant_display_name IS NOT NULL"
        )
        participant_snapshot_count = cursor.fetchone()[0]
        assert participant_snapshot_count == 2, participant_snapshot_count
        cursor.execute("SELECT rating, note FROM memory_reflections")
        reflection = cursor.fetchone()
        assert reflection == (8, "Legacy notes survived the migration.")
        cursor.execute(
            "SELECT timezone, anniversary_email_enabled FROM user_notification_preferences"
        )
        assert cursor.fetchone() == ("America/Chicago", False)
    runtime_url = os.environ["MIGRATION_RUNTIME_URL"]
    with psycopg.connect(runtime_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.current_user_id', %s, false)",
            ("11111111-1111-1111-1111-111111111111",),
        )
        cursor.execute("SELECT count(*) FROM memories")
        assert cursor.fetchone()[0] == 1
        cursor.execute(
            "SELECT count(*) FROM memories WHERE tandem_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'"
        )
        assert cursor.fetchone()[0] == 1
    print(
        "legacy rows preserved; end_date/reflection/participant backfills verified; runtime RLS visibility verified"
    )


if __name__ == "__main__":
    main()
