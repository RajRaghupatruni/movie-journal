# Tandem production smoke checklist

Run this against the final HTTPS URL after every first deploy, schema change, or auth/storage
configuration change. Use real but disposable test accounts and one real photo that is safe for
the test. Record timestamps and the `X-Request-ID` for any failure.

## Preflight

- [ ] `GET /healthz` returns only `{"status":"ok"}`.
- [ ] `GET /api/health` and `/api/readyz` are 200 and do not reveal infrastructure details.
- [ ] A client-side route such as `/timeline` returns the SPA HTML on a direct browser refresh.
- [ ] A missing hashed asset returns 404, while a known hashed asset is immutable-cacheable.
- [ ] `/api/not-a-route` returns JSON 404 and never the SPA shell.
- [ ] Response headers include CSP, `no-referrer`, `nosniff`, frame protection, and a suitable
  Permissions-Policy; HSTS is present on production HTTPS.

## User A: owner journey

- [ ] Open the final URL and log in with Google.
- [ ] Create a Tandem with a known test name and timezone.
- [ ] Invite User B’s exact Google email; copy the invitation URL without pasting it into logs.
- [ ] Confirm a second invitation for the same email is rejected while the first is pending.
- [ ] Create a movie memory by searching TMDb; select a result and confirm title/provider snapshot.
- [ ] Add a 1–10 rating, note, participants, and tags; save and refresh the page.
- [ ] Confirm the movie is present in Timeline, Explore search, Calendar, and its detail route.
- [ ] Edit the note/rating, refresh, and confirm optimistic versioning preserves the edit.
- [ ] Toggle resurfacing off for the memory; confirm it is absent from On This Day after the
  controlled-date setup below.
- [ ] Log out; confirm the app returns to the Google login page and the old session cannot call
  `/api/me`.

## User B: invitation and collaboration journey

- [ ] Open the invitation URL while logged out; confirm the invite message survives the Google
  redirect and the post-login page still offers acceptance.
- [ ] Sign in with B’s exact invited email and accept the invitation.
- [ ] Confirm B sees the Tandem and A’s movie memory, rating, note, Timeline, Explore, and Calendar.
- [ ] Create a place/activity memory using Geoapify where available; use manual entry if the
  provider is intentionally unavailable and record that behavior.
- [ ] Upload one real JPEG/PNG/WebP photo; confirm it appears in the detail page and Timeline.
- [ ] Refresh and confirm the photo still loads through a short-lived private URL, not a public
  bucket URL.
- [ ] Edit the memory and remove the photo; confirm the object is no longer readable.

## User C: non-member boundary

- [ ] Authenticate C with Google but do not accept an invitation or join the Tandem.
- [ ] Confirm C’s `/api/me/tandems` is empty and the app offers Tandem creation, not A/B’s data.
- [ ] Directly request A’s Tandem UUID, memory UUID, and media URL/API route as C.
- [ ] Confirm the responses do not reveal whether the resource exists (Tandem/memory/media
  boundaries should be 404-style); C cannot enumerate, modify, or delete anything.
- [ ] Attempt a forged participant or membership ID in a write; confirm 4xx and no database row.
- [ ] Confirm a copied presigned URL is short-lived and cannot be used after expiration.

## Worker and anniversary

- [ ] In a controlled database branch or disposable test Tandem, create a memory represented by
  a prior date whose month/day is today in the user’s IANA timezone.
- [ ] Keep anniversary notifications enabled and set the preferred hour to a testable hour.
- [ ] Verify Today shows the anniversary and that `nostalgia_eligible=false` suppresses it.
- [ ] Manually run the exact worker command once from the Render cron image or trigger the cron:
  `python -m app.workers.anniversary`.
- [ ] Confirm the Render cron log shows bounded counts and no credentials/content.
- [ ] Confirm one deduplicated in-app On This Day notification appears in the notification center.
- [ ] With `EMAIL_DELIVERY_ENABLED=false`, confirm no email outbox row is generated and no Resend
  request is attempted.
- [ ] If testing the future email path, enable the global flag with both Resend credentials and a
  verified sending domain; then confirm the privacy-preserving email arrives with only the generic
  CTA and application URL, and that a second worker run creates no duplicate outbox intent.
- [ ] If testing Feb 29, verify the documented Feb 28 non-leap-year rule.

## Negative and failure paths

- [ ] Fill a Tandem to its five-member limit; a new invite/acceptance fails with a friendly
  “Tandem is full” response and does not create a membership.
- [ ] Open an expired invitation; confirm a clear expired/invalid state, no membership, and no
  token in logs.
- [ ] Temporarily block TMDb or Geoapify in a controlled environment; confirm a retryable provider
  message and that manual memory entry still works.
- [ ] Upload a text file renamed to `.jpg`, an unsupported MIME type, and a file over 10 MiB;
  confirm each is rejected without an object or partial media row.
- [ ] Delete a memory; confirm its detail, Timeline entry, On This Day result, and media are no
  longer accessible.
- [ ] Confirm the email preference is not offered in launch Settings while global delivery is
  disabled; the backend preference field remains available for a future re-enable.
- [ ] Confirm state-changing requests from a foreign Origin are rejected in production, while
  same-origin UI actions work.
- [ ] Inspect logs for the whole run: no notes, titles, email invitation references, session/OAuth
  tokens, photo bytes, provider keys, SQL credentials, or stack traces are present.

## P0 completion journey

- [ ] Create two Tandems for User A and switch between them; confirm each selected Tandem keeps
  its own Timeline, Calendar, Explore, and On This Day context.
- [ ] Add a memory in Tandem 1 and confirm members of Tandem 2 cannot access it through a direct
  memory, media, notification, or global-view request.
- [ ] Confirm User B can edit only memories User B created, while the creator can edit or delete
  their own memory; verify a concurrent stale-version edit returns 409.
- [ ] Promote and demote a member, remove a member, and test that the last owner cannot leave,
  be removed, or demote themselves.
- [ ] Deactivate an account with `DEACTIVATE`, confirm delivery state and memberships are gone,
  then sign in again and reactivate without automatic membership restoration.
- [ ] Export the account and verify the download contains authorized metadata and media
  descriptors but no media bytes, object-store credentials, notes from inaccessible Tandems, or
  unbounded query results.
- [ ] Trigger an invite, acceptance, memory-add, member-change, and owner-change event; verify
  the notification bell updates on focus and does not surface another Tandem's event.
