# Product completion notes

This document records the P0 completion behavior that is shared by the API and the web client.

## Tandems and membership

- A user may belong to multiple Tandems and the selected Tandem is persisted in browser storage.
- Each Tandem has one to five members. Owners can promote and demote members, remove another
  member, and create or resend invitations. The last owner cannot demote, leave, or be removed.
- Leaving or being removed revokes access to all Tandem-scoped memories, media, Timeline,
  Calendar, Explore, On This Day, and Tandem notifications. Shared rows remain for the other
  members.
- Tandem deletion requires an explicit Tandem-name or `DELETE` confirmation. Private media is
  removed before the database transaction; a failed cleanup is recorded for operator retry.

## Account lifecycle and privacy

- Deactivation is reversible, requires `DEACTIVATE`, clears delivery state, and removes all
  memberships. A Google sign-in creates a reactivation-only session and shows the reactivation
  screen without restoring memberships automatically.
- Permanent deletion requires `DELETE`, revokes pending invitations, removes the account row,
  and nulls historical actor references so shared memories and activity history remain intact.
- Tandem data is private by default. Authorization is enforced in the API and database RLS; UI
  hiding is not treated as an access boundary.
- `GET /api/me/export` returns bounded JSON for the Tandems the current user can access. It
  includes metadata and media descriptors, never private object bytes or storage credentials.

## Notifications

The notification table is recipient-owned and RLS-protected. Notification creation goes through
the allowlisted database function, which verifies the actor and Tandem/invitation relationship.
Supported events are invitations, invitation acceptance, memory additions, owner changes, and
member leave/removal. The web client refreshes on focus and polls every 45 seconds only while the
document is visible; the bell shows unread count and deep-links to a memory when available.

## Global views

`/api/me/memories`, `/api/me/timeline`, and `/api/me/calendar` return the union of memories across
the current user's active Tandem memberships, with optional Tandem, category, year, date-range,
and search filters. `/api/me/on-this-day` applies the current user's IANA timezone and returns
anniversaries across all accessible Tandems. Today and Calendar use this global aggregation in the
web client; Timeline and Explore remain selected-Tandem views for a calmer focused reading
experience, while their account-level endpoints are available for future filter controls.

## Verification and operations

Run the repository checks before deployment:

```text
python -m ruff check backend/app backend/alembic
python -m compileall -q backend/app backend/tests
npm run lint
npm run typecheck
npm test -- --run
npm run build
```

Run the production smoke checklist after applying migration `0012_product_completion`, especially
the account lifecycle, membership-boundary, notification, export, and storage-cleanup cases.
