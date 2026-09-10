# Firebase migration boundary

No Firebase dependency is used by the new memory API. The legacy Firebase consumers remain
in the repository until their watched/watchlist and historical event data have an approved,
repeatable import path.

## Collections discovered

- `tandems/{tandemId}/events/{eventId}`: title, `category` (Movie/Place/Trip/Activity), date,
  free-text participant names, rating, review/notes, optional location snapshot, source, and
  created/updated timestamps.
- `watchedMovies/{id}`: TMDb ID/title/poster, watched date, rating, and review HTML.
- `watchlistMovies/{id}`: TMDb ID/title/poster, year, and added timestamp.

The old root movie collections have no Tandem scope in the client code. They must not be
assigned to a Tandem by guessing from the current UI. Ownership and the intended Tandem must
be approved by the data owner first.

## Safe mapping

Historical event records map to `memories` after review: category is lower-cased into the
canonical enum, the event date becomes `local_date`, the original location becomes a manual
place/trip snapshot, and notes are migrated as plain text only after the existing safe review
policy is applied. Free-text participant names are not identities; preserve them in a review
report until each person is explicitly mapped to a current Tandem member. Tags are optional
and should be normalized with the PostgreSQL API contract.

Watched movies and watchlist entries are separate future product tables, not silently folded
into memories. Preserve provider IDs, original Firestore IDs, and source timestamps in an
import mapping table/report. Do not relabel Foursquare data as Geoapify or invent TMDb data
for manual records.

## What can be dropped

Malformed records with no approved Tandem ownership, records whose identity mapping cannot be
verified, duplicate provider snapshots after an owner-approved deduplication decision, and
legacy rich HTML that cannot pass the plain-text/safe-review policy may be excluded. Every
exclusion should appear in a dry-run report; nothing should be deleted from Firebase as part
of this milestone.

## Deletion gate

It is safe to remove Firebase SDK dependencies only after: an owner-approved read-only export
exists; a dry-run import reports counts and rejects; the import is repeatable using stable
source IDs; watched/watchlist and event screens have PostgreSQL replacements; reviews have
passed sanitization; and a backup/rollback decision is recorded. Until then, legacy provider
and Firebase code is intentionally retained as a migration boundary.
