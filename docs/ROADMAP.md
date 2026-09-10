# Product follow-ups

## P1: PostgreSQL watchlist

Add a small Tandem-scoped watchlist under Explore. Each entry should store a TMDb movie snapshot,
the member who added it, its creation time, and an optional note. Support authorized removal and
conversion into a movie memory, with PostgreSQL constraints and RLS matching the existing memory
domain. This is intentionally separate from the retired Firebase watchlist and should not become
a second source of truth for movie memories.
