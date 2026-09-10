from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.services.on_this_day import (
    anniversary_date_for,
    build_anniversary_matches,
    local_date_for,
)
from app.workers.anniversary import idempotency_key_for, retry_at


def test_local_date_uses_the_requesting_users_timezone_at_midnight_boundary():
    instant = datetime(2026, 9, 10, 0, 15, tzinfo=UTC)
    assert local_date_for(instant, "America/Chicago") == date(2026, 9, 9)
    assert local_date_for(instant, "Asia/Kolkata") == date(2026, 9, 10)


def test_feb_29_policy_is_explicit():
    original = date(2020, 2, 29)
    assert anniversary_date_for(original, 2024) == date(2024, 2, 29)
    assert anniversary_date_for(original, 2025) == date(2025, 2, 28)


def test_naive_clock_is_safely_interpreted_as_utc():
    assert local_date_for(datetime(2026, 1, 1, 0, 1), "America/New_York") == date(2025, 12, 31)


def memory(memory_id, year, month=9, day=9, eligible=True):
    return SimpleNamespace(
        id=memory_id,
        local_date=date(year, month, day),
        nostalgia_eligible=eligible,
    )


def test_matching_supports_one_year_multiple_years_and_several_memories():
    result = build_anniversary_matches(
        [memory("old", 2023), memory("recent", 2025), memory("second", 2024)],
        date(2026, 9, 9),
    )
    assert [item.years_ago for item in result] == [1, 2, 3]
    assert [item.memory.id for item in result] == ["recent", "second", "old"]


def test_non_anniversary_and_disabled_memories_are_excluded():
    result = build_anniversary_matches(
        [memory("wrong-day", 2025, day=10), memory("disabled", 2025, eligible=False)],
        date(2026, 9, 9),
    )
    assert result == []


def test_feb_29_surfaces_on_feb_28_in_non_leap_years():
    result = build_anniversary_matches([memory("leap", 2020, 2, 29)], date(2025, 2, 28))
    assert len(result) == 1
    assert result[0].anniversary_date == date(2025, 2, 28)


def test_outbox_key_and_backoff_are_deterministic():
    now = datetime(2026, 9, 9, 14, 0)
    assert idempotency_key_for("t", "u", "m", 2026) == "anniversary:t:u:m:2026:email"
    assert retry_at(now, 1) == datetime(2026, 9, 9, 14, 5)
    assert retry_at(now, 2) == datetime(2026, 9, 9, 14, 10)
