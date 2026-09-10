# On This Day and anniversary delivery

Today uses a backend `OnThisDayService`. For the requesting member, Tandem reads the configured
IANA timezone from `user_notification_preferences`, converts the current instant to that local
date, and selects memories from current Tandem memberships whose represented `local_date` has
the same month/day in an earlier year. A memory is eligible by default and can be excluded with
`nostalgia_eligible = false`; hard-deleted memories cannot be returned or delivered.

The represented date is date-only and is never derived from UTC. An exact `occurred_at` remains
metadata and does not change anniversary matching. If there are no exact anniversaries, Today
shows one deterministic eligible older memory or an abstract Tandem-owned fallback treatment.

Feb 29 is explicit: it resurfaces on Feb 29 during leap years and on Feb 28 during non-leap
years. On Feb 28 of a non-leap year, a Feb 28 memory and a Feb 29 memory may both surface.

## Preferences and outbox

Users can enable/disable On This Day, choose their timezone, and choose a local delivery hour.
The anniversary email preference remains stored for future re-enablement, but outbound email is
globally disabled for Tandem v1. Candidate generation always creates deduplicated in-app
notifications for eligible anniversaries. It inserts `notification_outbox` rows only when
`EMAIL_DELIVERY_ENABLED=true`, using a unique key:
`anniversary:tandem:user:memory:anniversary-year:email`. Re-running the worker is safe at the
database level.

Before delivery, the worker verifies the memory, membership, eligibility, and preferences again.
Transient Resend/network/429/5xx failures retry at 5 and 10 minutes, with a maximum of three
attempts; permanent or exhausted records become `FAILED`, and privacy changes become
`CANCELLED`. The claim is committed before calling Resend, which prevents concurrent workers
from sending the same row. A process crash after Resend accepts the message but before the
`SENT` commit can still cause a duplicate, so semantics are at-least-once at that boundary.

Run the bounded worker with:

```text
cd backend
python -m app.workers.anniversary
```

Production should schedule this command hourly (or more frequently if delivery-hour precision
matters), with `DATABASE_URL` set to the dedicated non-bypass-RLS runtime role. At launch,
`EMAIL_DELIVERY_ENABLED=false` means the worker generates in-app notifications only and does not
load a Resend adapter. `MIGRATION_DATABASE_URL` is for Alembic pre-deploy runs, never the worker.
Tests inject a deterministic clock
and fake adapter; they never call Google, Resend, TMDb, Geoapify, or S3.
