"""Seed representative legacy rows for the V1 migration acceptance check."""

import os

import psycopg


def main() -> None:
    url = os.environ["MIGRATION_SEED_URL"]
    with psycopg.connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (id, google_subject, email, display_name, avatar_url) "
                "VALUES ('11111111-1111-1111-1111-111111111111', 'google-legacy-owner', "
                "'legacy-owner@example.test', 'Legacy Owner', NULL), "
                "('22222222-2222-2222-2222-222222222222', 'google-legacy-member', "
                "'legacy-member@example.test', 'Legacy Member', NULL)"
            )
            cursor.execute(
                "INSERT INTO tandems (id, name, created_by, timezone) VALUES "
                "('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Legacy Movie Night', "
                "'11111111-1111-1111-1111-111111111111', 'UTC')"
            )
            cursor.execute(
                "INSERT INTO tandem_members (tandem_id, user_id, role) VALUES "
                "('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', 'OWNER'), "
                "('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '22222222-2222-2222-2222-222222222222', 'MEMBER')"
            )
            cursor.execute(
                "INSERT INTO memories "
                "(id, tandem_id, category, title, local_date, timezone, notes, rating, created_by, metadata) "
                "VALUES ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', "
                "'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'movie', 'The Legacy Film', '2021-09-10', 'UTC', "
                "'Legacy notes survived the migration.', 8, '11111111-1111-1111-1111-111111111111', "
                '\'{"provider_movie_id": "550", "provider_title": "The Legacy Film", '
                '"provider_release_date": "1999-10-15", "review": "A favorite from movie night."}\')'
            )
            cursor.execute(
                "INSERT INTO memory_participants (memory_id, tandem_id, user_id) VALUES "
                "('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', "
                "'11111111-1111-1111-1111-111111111111'), "
                "('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', "
                "'22222222-2222-2222-2222-222222222222')"
            )
            cursor.execute(
                "INSERT INTO tags (id, tandem_id, name, normalized_name) VALUES "
                "('cccccccc-cccc-cccc-cccc-cccccccccccc', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Movie night', 'movie night')"
            )
            cursor.execute(
                "INSERT INTO memory_tags (memory_id, tag_id, tandem_id) VALUES "
                "('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'cccccccc-cccc-cccc-cccc-cccccccccccc', "
                "'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa')"
            )
            cursor.execute(
                "INSERT INTO user_notification_preferences "
                "(id, user_id, timezone, anniversary_notifications_enabled, anniversary_email_enabled, notification_hour) "
                "VALUES ('dddddddd-dddd-dddd-dddd-dddddddddddd', '11111111-1111-1111-1111-111111111111', 'America/Chicago', true, false, 8)"
            )
        connection.commit()
    print(
        "seeded legacy user, Tandem, membership, movie metadata, rating, review, notes, participants, tags, and notification preferences"
    )


if __name__ == "__main__":
    main()
