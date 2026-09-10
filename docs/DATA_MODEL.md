# Tandem memory data model

Migration `0008_memory_domain` makes PostgreSQL authoritative for newly created memories.
`memories` is the common entity for `movie`, `place`, `trip`, `activity`, and `custom`. The
category is constrained in SQL and the `metadata` JSONB column is validated by a strict,
category-selected Pydantic model. Unknown metadata keys are rejected. `schema_version` is
currently `1`, leaving room for compatible metadata evolution without creating five CRUD
systems.

## Entities and relationships

- `memories`: title, human calendar `local_date`, optional exact `occurred_at`, IANA
  `timezone`, plain-text notes, 1–10 rating, creator, timestamps, optimistic `version`, and
  `nostalgia_eligible`.
- `memory_participants`: a memory/user join with a denormalized `tandem_id`. Composite
  foreign keys require both the memory and user membership to belong to the same Tandem.
- `tags`: Tandem-scoped normalized names. Normalization trims outer whitespace, collapses
  internal whitespace, and applies Unicode case-folding; the normalized value is stored as
  the display value for now. `(tandem_id, normalized_name)` is unique.
- `memory_tags`: the memory/tag join, also carrying `tandem_id` for RLS and composite-FK
  tenant integrity.
- `memory_media`: private processed image metadata keyed to an opaque S3-compatible object key.
  The tandem ID is denormalized for RLS and composite memory foreign-key integrity.
- `activity_events`: append-only, small audit records. State tables remain authoritative;
  this is not event sourcing. Event payloads are bounded to 4 KiB and never include notes,
  photos, tokens, or secrets.

Movie metadata supports manual or future TMDb snapshots; place metadata supports manual or
future Geoapify snapshots; trips require a destination and optionally carry start/end dates;
activity and custom metadata stay deliberately small.

## Time and querying

`local_date` is the date a person means when remembering an event and is the source for
timeline grouping and calendar indicators. `occurred_at` is only an additional exact instant
when known and must include an offset. `timezone` is validated with Python's IANA `zoneinfo`
database. Anniversary features must use `local_date`, never derive a date from UTC.

The list API uses bounded offset pagination (`limit` 1–100, `offset` at most 10,000) with a
stable `local_date DESC, id DESC` order. Cursor pagination is a sensible follow-up if the
archive outgrows this first slice. Filters combine category, date range/year, participant,
rating, exact normalized tag, and PostgreSQL full-text search.

The generated `search_vector` covers title, notes, and metadata snapshots and has a GIN
index. A tag join participates in text search so normalized tag names are searchable. B-tree
indexes support tenant/date timeline reads, category filters, updated records, participants,
tag joins, media ordering, and activity history.

## Security and concurrency

All five memory-related tables have `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.
Policies use the existing transaction-local `app.current_user_id()` and the existing
security-definer `app.is_tandem_member()` predicate. FastAPI's centralized tandem dependency
is the first check; RLS remains the database boundary. Participants also have composite FKs
to `tandem_members`, so a user cannot be attached merely by guessing an ID.

New memories start at version `1`. PATCH and version-aware DELETE include the expected version
in the same SQL predicate as the mutation. A zero-row update is returned as HTTP 409 with the
current version when it still exists; last-write-wins is never used.

Creation, edits, participant/tag changes, and deletion write their compact activity events
in the same database transaction as state changes. Hard deletion cascades participant/tag
joins; the deletion event retains only the memory UUID and actor metadata.

## Extension strategy

Add a new enum value, a new strict metadata Pydantic model, and its adapter entry first. Add
only category-specific fields that are genuinely reusable. A future provider integration can
populate the existing snapshot fields without changing the memory CRUD or UI contracts.
