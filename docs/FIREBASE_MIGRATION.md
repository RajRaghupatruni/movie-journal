# Firebase retirement decision

Firebase migration was deliberately abandoned for this product-cleanup milestone. Legacy
Firebase data is disposable, PostgreSQL starts fresh, and PostgreSQL is the sole application
source of truth. No import, dual-write, compatibility, or Firebase migration script is planned.

The active application uses authenticated FastAPI endpoints backed by PostgreSQL for Tandems,
memberships, invitations, memories, participants, tags, and media. TMDb and Geoapify are
backend-owned capture providers. The old Firestore event, watched-movie, and watchlist flows
were removed from active production code because their useful memory capture path has been
replaced and no legacy data needs to be preserved.

Watchlist remains a useful Explore concept, but its Firebase implementation is intentionally
not retained. A small tandem-scoped PostgreSQL watchlist is a documented P1 follow-up; it must
include a TMDb snapshot, `added_by`, `added_at`, optional note, remove, authorization/RLS, and
an explicit conversion path to a movie memory.

Historical audit and planning documents may mention Firebase or Foursquare as repository history.
They do not describe active runtime behavior or create a migration obligation.
