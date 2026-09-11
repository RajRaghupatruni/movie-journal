# Tandem V1 regression inventory and coverage matrix

This inventory is derived from the V1 implementation at the start of the validation branch,
not from the product brief alone. The application is feature frozen. Coverage labels are:

- **LIVE-AUTOMATED**: executed against `https://tandem-web-xnih.onrender.com`; write coverage uses one
  genuine OAuth identity captured through the normal Google flow and a namespaced disposable resource
  set. Capturing that state is manual; replaying it in the regression suite is automated.
- **LOCAL-INTEGRATION**: executed against the PG18 test stack or a provider/storage mock. This is
  the authoritative layer for multi-user authorization when only one live identity is available.
- **UNIT/COMPONENT**: deterministic frontend/backend logic coverage.
- **MANUAL**: requires a human OAuth, visual, provider, account, worker, or destructive action;
  automation may continue after a human securely captures the one-account storage state.
- **BLOCKED**: only used when no safe execution layer exists and the missing evidence materially
  affects release readiness. The revised V1 inventory has no such cases.

Every row below has a classification. Production write and destructive rows are not silently
treated as passed when they are manual or blocked.

## Inventory provenance

- Frontend: `src/App.jsx`, `src/components/tandem/components.jsx`, `src/components/tandem/ProviderSearch.jsx`, `src/lib/tandemApi.ts`.
- Backend: registered routers in `backend/app/main.py` and route decorators under `backend/app/api`.
- Database: Alembic migrations `0001` through `0016_v1_completion` and SQLAlchemy models.
- Workers: `backend/app/workers/anniversary.py` and `backend/app/workers/deleted_memories.py`.
- Existing lower-layer suites: 31 frontend tests, backend tests under `backend/tests`, and mocked Playwright acceptance flows under `tests/e2e`.

## Frontend routes and screens

| ID | Route/state | Implementation behavior | Coverage |
|---|---|---|---|
| FE-01 | `/` unauthenticated | Login page; Google OAuth link; invitation query is preserved in session storage | LIVE-AUTOMATED |
| FE-02 | `/` authenticated | Today, recent memories, On This Day/fallback, add-memory entry point, rediscovery panel | LOCAL-INTEGRATION |
| FE-03 | `/privacy` | Static privacy explanation and return link | UNIT/COMPONENT |
| FE-04 | `/reactivate` | Inactive-user reactivation screen | LOCAL-INTEGRATION |
| FE-05 | `/memories` | Timeline or Gallery mode, type/year/search/sort controls | LOCAL-INTEGRATION |
| FE-06 | `/timeline` | Timeline presentation with type filter and newest/oldest sort | LOCAL-INTEGRATION |
| FE-07 | `/explore` | Gallery mode route alias with query state | LOCAL-INTEGRATION |
| FE-08 | `/calendar` | Month navigation, date selection, trip ranges, side panel, memory opening | LOCAL-INTEGRATION |
| FE-09 | `/tandem` | Scoped People & settings and member/invitation management | LOCAL-INTEGRATION |
| FE-10 | `/recently-deleted` | Scoped recovery list, restore, permanent-delete confirmation | LOCAL-INTEGRATION |
| FE-11 | `/settings` | Personal preferences, export, deactivate, delete, logout | LOCAL-INTEGRATION |
| FE-12 | `/memory/:id` | Memory detail, edit/delete controls, reflections, nostalgia control | LOCAL-INTEGRATION |
| FE-13 | loading | Public loading mark and authenticated loading skeleton | UNIT/COMPONENT |
| FE-14 | service error | Retryable error screen with generic safe message | UNIT/COMPONENT |
| FE-15 | session expiry | 401 event returns the shell to unauthenticated login | UNIT/COMPONENT |
| FE-16 | browser history | `pushState`, popstate, back/forward, query mode/search preservation | LOCAL-INTEGRATION |

## Modals, drawers, forms, menus, and conditional controls

| ID | Surface or action | States and behavior | Coverage |
|---|---|---|---|
| UI-01 | Add Memory launcher | Movie, Place, Trip, Activity, Something else; close X, Escape, backdrop | LOCAL-INTEGRATION |
| UI-02 | Memory form | destination selector, member count, creator/participant selection, required validation, cancel | LOCAL-INTEGRATION |
| UI-03 | Movie form | TMDb search/result card, manual title, saved artwork, duplicate warning | LOCAL-INTEGRATION |
| UI-04 | Place form | Geoapify search/result card and manual place fallback | LOCAL-INTEGRATION |
| UI-05 | Trip form | destination, optional end date, date-range validation | UNIT/COMPONENT |
| UI-06 | Activity/custom form | title, date, activity kind or free title | LOCAL-INTEGRATION |
| UI-07 | More details | timezone, notes, rating, tags, participant checkboxes, hide/show | LOCAL-INTEGRATION |
| UI-08 | Photo picker | JPEG/PNG/WebP, multiple files, previews, remove new/saved photo | LOCAL-INTEGRATION |
| UI-09 | Reflection form | independent rating, reaction, note; own reflection only | LOCAL-INTEGRATION |
| UI-10 | Confirmation modal | exact phrase, disabled submit, Cancel, Escape, busy state | LOCAL-INTEGRATION |
| UI-11 | Notification drawer | unread badge, list, mark one read, mark all read, deep link | LOCAL-INTEGRATION |
| UI-12 | Scope switcher | All Tandems, each Tandem, create another; People & settings only scoped | LOCAL-INTEGRATION |
| UI-13 | Tandem management | rename, timezone, invite, copy link, revoke/resend, promote/demote/remove, delete | LOCAL-INTEGRATION |
| UI-14 | Member view | leave action and non-owner controls; owner controls hidden | LOCAL-INTEGRATION |
| UI-15 | Personal settings | notification toggle, timezone/hour, save feedback | LOCAL-INTEGRATION |
| UI-16 | Tandem preferences | resurfacing and routine-notification toggles scoped to current Tandem | LOCAL-INTEGRATION |
| UI-17 | Recently Deleted | restore; permanent delete with `DELETE` phrase | LOCAL-INTEGRATION |
| UI-18 | Empty/loading/error states | zero Tandems, zero memories, no search results, skeletons, retryable errors | UNIT/COMPONENT |
| UI-19 | Native dialogs audit | no product-facing `alert`, `confirm`, or `prompt` remains in source | UNIT/COMPONENT |
| UI-20 | Desktop visual behavior | 1280/1440/1600 desktop screenshots in mocked acceptance suite | LOCAL-INTEGRATION |

## Backend route inventory

The application registers **61 HTTP routes**. Paths below include router prefixes as exposed by
FastAPI. Authenticated routes use the session cookie and transaction-local RLS identity; member
and owner dependencies are called out where they are stricter than authentication.

| ID | Method and path | Authorization / side effects | Coverage |
|---|---|---|---|
| API-01 | GET `/api/health` | DB readiness | LIVE-AUTOMATED |
| API-02 | GET `/api/readyz` | DB readiness | LIVE-AUTOMATED |
| API-03 | GET `/healthz` | process liveness | LIVE-AUTOMATED |
| API-04 | GET `/auth/google/login` | starts Google OAuth state | LIVE-AUTOMATED |
| API-05 | GET `/auth/google/callback` | OAuth state, Google identity, session creation | MANUAL |
| API-06 | POST `/auth/logout` | authenticated; revokes current session | LOCAL-INTEGRATION |
| API-07 | GET `/api/me` | authenticated | LIVE-AUTOMATED |
| API-08 | POST `/api/me/deactivate` | authenticated; lifecycle transition and session revocation | LOCAL-INTEGRATION |
| API-09 | GET `/api/me/reactivation` | authenticated including inactive | LOCAL-INTEGRATION |
| API-10 | POST `/api/me/reactivate` | authenticated including inactive | LOCAL-INTEGRATION |
| API-11 | POST `/api/me/delete` | authenticated; irreversible identity cleanup | MANUAL |
| API-12 | GET `/api/me/preferences` | authenticated; creates defaults | LOCAL-INTEGRATION |
| API-13 | PATCH `/api/me/preferences` | authenticated; current-user only | LOCAL-INTEGRATION |
| API-14 | GET `/api/me/tandems` | authenticated; RLS-scoped list | LOCAL-INTEGRATION |
| API-15 | GET `/api/me/memories` | authenticated; global filters/pagination | LOCAL-INTEGRATION |
| API-16 | GET `/api/me/timeline` | authenticated; global timeline alias | LOCAL-INTEGRATION |
| API-17 | GET `/api/me/calendar` | authenticated; global calendar alias | LOCAL-INTEGRATION |
| API-18 | GET `/api/me/on-this-day` | authenticated; preferences, timezone, anniversary/fallback | LOCAL-INTEGRATION |
| API-19 | GET `/api/me/export` | authenticated; bounded current-access export | LOCAL-INTEGRATION |
| API-20 | GET `/api/me/notifications` | authenticated; unread count and bounded list | LOCAL-INTEGRATION |
| API-21 | POST `/api/me/notifications/{notification_id}/read` | current-user notification only | LOCAL-INTEGRATION |
| API-22 | POST `/api/me/notifications/read-all` | current-user notifications only | LOCAL-INTEGRATION |
| API-23 | GET `/api/me/rediscovery/shuffle` | global or `tandem_id`; eligibility and seed | LOCAL-INTEGRATION |
| API-24 | GET `/api/me/rediscovery/year-review` | global/scoped year summary | LOCAL-INTEGRATION |
| API-25 | GET `/api/me/rediscovery/collections` | global/scoped deterministic collections | LOCAL-INTEGRATION |
| API-26 | POST `/api/tandems` | authenticated; creates Tandem and owner membership | LOCAL-INTEGRATION |
| API-27 | GET `/api/tandems/{tandem_id}` | member | LOCAL-INTEGRATION |
| API-28 | GET `/api/tandems/{tandem_id}/preferences` | member; current-user preference row | LOCAL-INTEGRATION |
| API-29 | PATCH `/api/tandems/{tandem_id}/preferences` | member; current-user preference row | LOCAL-INTEGRATION |
| API-30 | DELETE `/api/tandems/{tandem_id}` | owner; media cleanup and irreversible delete | LOCAL-INTEGRATION |
| API-31 | PATCH `/api/tandems/{tandem_id}` | owner; name/timezone | LOCAL-INTEGRATION |
| API-32 | GET `/api/tandems/{tandem_id}/members` | member | LOCAL-INTEGRATION |
| API-33 | DELETE `/api/tandems/{tandem_id}/members/{user_id}` | owner; final-owner guard and notifications | LOCAL-INTEGRATION |
| API-34 | POST `/api/tandems/{tandem_id}/members/{user_id}/promote` | owner; owner notification | LOCAL-INTEGRATION |
| API-35 | POST `/api/tandems/{tandem_id}/members/{user_id}/demote` | owner; self/final-owner guard | LOCAL-INTEGRATION |
| API-36 | POST `/api/tandems/{tandem_id}/leave` | member; sole-owner guard and notifications | LOCAL-INTEGRATION |
| API-37 | POST `/api/tandems/{tandem_id}/invitations` | owner; capacity, history summary, notification | LOCAL-INTEGRATION |
| API-38 | GET `/api/tandems/{tandem_id}/invitations` | owner | LOCAL-INTEGRATION |
| API-39 | POST `/api/tandems/{tandem_id}/invitations/{safe_reference}/revoke` | owner; pending-only | LOCAL-INTEGRATION |
| API-40 | POST `/api/tandems/{tandem_id}/invitations/{safe_reference}/resend` | owner; rotates token | LOCAL-INTEGRATION |
| API-41 | GET `/api/invitations/{safe_reference}` | authenticated matching invited email | LOCAL-INTEGRATION |
| API-42 | POST `/api/invitations/{safe_reference}/accept` | authenticated matching invited email; membership/capacity | LOCAL-INTEGRATION |
| API-43 | POST `/api/invitations/{safe_reference}/decline` | authenticated matching invited email | LOCAL-INTEGRATION |
| API-44 | GET `/api/tandems/{tandem_id}/memories` | member; filters/pagination | LOCAL-INTEGRATION |
| API-45 | POST `/api/tandems/{tandem_id}/memories` | member; memory, participants, tags, activity, notifications | LOCAL-INTEGRATION |
| API-46 | GET `/api/tandems/{tandem_id}/memories/duplicates` | member; duplicate candidate lookup | LOCAL-INTEGRATION |
| API-47 | GET `/api/tandems/{tandem_id}/memories/deleted` | member; Recently Deleted scope | LOCAL-INTEGRATION |
| API-48 | GET `/api/tandems/{tandem_id}/memories/{memory_id}` | member; private detail | LOCAL-INTEGRATION |
| API-49 | PATCH `/api/tandems/{tandem_id}/memories/{memory_id}` | creator/owner; optimistic version | LOCAL-INTEGRATION |
| API-50 | DELETE `/api/tandems/{tandem_id}/memories/{memory_id}` | creator/owner; soft delete and media retention | LOCAL-INTEGRATION |
| API-51 | POST `/api/tandems/{tandem_id}/memories/{memory_id}/restore` | creator/owner; recoverable window | LOCAL-INTEGRATION |
| API-52 | DELETE `/api/tandems/{tandem_id}/memories/{memory_id}/permanent` | creator/owner; irreversible purge | MANUAL |
| API-53 | PUT `/api/tandems/{tandem_id}/memories/{memory_id}/reflections/me` | member; current-user reflection | LOCAL-INTEGRATION |
| API-54 | DELETE `/api/tandems/{tandem_id}/memories/{memory_id}/reflections/me` | member; current-user reflection | LOCAL-INTEGRATION |
| API-55 | GET `/api/tandems/{tandem_id}/memories/{memory_id}/media` | member; signed/private media URLs | LOCAL-INTEGRATION |
| API-56 | POST `/api/tandems/{tandem_id}/memories/{memory_id}/media` | creator/owner; multipart validation/storage | LOCAL-INTEGRATION |
| API-57 | DELETE `/api/tandems/{tandem_id}/memories/{memory_id}/media/{media_id}` | creator/owner; storage cleanup | LOCAL-INTEGRATION |
| API-58 | GET `/api/tandems/{tandem_id}/on-this-day` | member; scoped nostalgia | LOCAL-INTEGRATION |
| API-59 | GET `/api/integrations/movies/search` | authenticated; live/mock TMDb | MANUAL |
| API-60 | GET `/api/integrations/movies/{tmdb_id}` | authenticated; live/mock TMDb detail | MANUAL |
| API-61 | GET `/api/integrations/places/search` | authenticated; live/mock Geoapify | MANUAL |

## Database and authorization inventory

Domain tables are `users`, `auth_sessions`, `oauth_states`, `tandems`, `tandem_members`,
`invitations`, `memories`, `memory_participants`, `tags`, `memory_tags`, `activity_events`,
`memory_media`, `memory_reflections`, `user_notification_preferences`,
`tandem_user_preferences`, `notifications`, `notification_outbox`, and
`storage_cleanup_failures`.

RLS and lifecycle state coverage:

| Area | Actual states/policies | Coverage |
|---|---|---|
| Tandem membership | OWNER/MEMBER, multiple owners, final-owner invariant, removed/left member | LOCAL-INTEGRATION |
| Invitations | PENDING, ACCEPTED, DECLINED, REVOKED, EXPIRED, resend rotation | LOCAL-INTEGRATION |
| Memory lifecycle | active, soft-deleted, restore window, restore/purge eligibility | LOCAL-INTEGRATION |
| Memory privacy | member reads, creator/owner writes, participant validation, cross-Tandem rejection | LOCAL-INTEGRATION |
| Reflections | one per user/memory, independent rating/note/reaction, owner cannot impersonate | LOCAL-INTEGRATION |
| Preferences | user defaults, per-Tandem resurfacing and routine notifications | LOCAL-INTEGRATION |
| Notifications | unread/read/archived, read-all, dedupe, critical vs routine policy | LOCAL-INTEGRATION |
| Media | private object key, signed access, file validation, cleanup failure record | LOCAL-INTEGRATION |
| RLS helpers | bounded SECURITY DEFINER helpers, fixed search path, no public execute | LOCAL-INTEGRATION |
| RLS adversarial identities | A owner, B member, C outsider, former/deactivated users | LOCAL-INTEGRATION |

## Workers and integrations

| ID | Behavior | Coverage |
|---|---|---|
| W-01 | Anniversary candidate generation, timezone/hour eligibility, dedupe | LOCAL-INTEGRATION |
| W-02 | Anniversary email outbox disabled in V1 (`EMAIL_DELIVERY_ENABLED=false`) | UNIT/COMPONENT |
| W-03 | Outbox lease, retry, cancel, failure states | LOCAL-INTEGRATION |
| W-04 | 30-day deleted-memory purge and object cleanup | LOCAL-INTEGRATION |
| I-01 | Google OAuth state/callback/session | MANUAL |
| I-02 | TMDb real search/detail/artwork | MANUAL |
| I-03 | Geoapify real place search | MANUAL |
| I-04 | Backblaze B2 upload/read/delete and signed private access | MANUAL |
| I-05 | Resend adapter remains disabled for V1 | UNIT/COMPONENT |

## State and role matrix

| Matrix case | Required assertion | Coverage |
|---|---|---|
| A / zero Tandems | onboarding create, skip, empty Today/Memories/Calendar, later create | LOCAL-INTEGRATION |
| A / one Tandem | owner controls, scoped/global views, create/edit/delete | LOCAL-INTEGRATION |
| A / multiple Tandems | scope switch, labels, destination switch, isolation | LOCAL-INTEGRATION |
| B / ordinary member | shared reads, add memory, own reflection, leave | LOCAL-INTEGRATION |
| C / authenticated outsider | 404/403 and no cross-Tandem data by identifier | LOCAL-INTEGRATION |
| D / former member | access disappears; historical attribution remains | LOCAL-INTEGRATION |
| E / invited not joined | logged-out link, correct-email continuation, wrong-email rejection | MANUAL |
| F / deactivated | reactivation path, revoked session, preserved valid memberships | LOCAL-INTEGRATION |
| G / zero-Tandem authenticated | settings/logout/incoming invitation still available | LOCAL-INTEGRATION |
| one-member/sole-owner | cannot leave or remove final owner | LOCAL-INTEGRATION |
| multi-owner | promote/demote/remove with at least one owner | LOCAL-INTEGRATION |
| provider failure | 401/403, timeout, zero results; manual fallback remains usable | UNIT/COMPONENT |
| browser state | refresh, deep link, back/forward, filters/query/mode persistence | LOCAL-INTEGRATION |
| privacy/XSS | text rendered as text; sanitized review helper; no unsafe HTML sink | UNIT/COMPONENT |

### PG18 multi-user evidence map

These cases are intentionally LOCAL-INTEGRATION, not live OAuth claims. The tests run PostgreSQL
18.6 with `tandem_app` and `tandem_migrator` as non-superuser, `NOBYPASSRLS` roles and FORCE RLS.

| Security behavior | Exact automated evidence |
|---|---|
| A/B/C Tandem visibility and direct SQL RLS | `backend/tests/test_auth_domain.py::test_invites_members_and_isolates_tandem_rows`; `test_tandem_rls_create_listing_and_direct_sql_boundaries` |
| Invitation wrong-user rejection, join, reuse, revoke, expiry | `backend/tests/test_auth_domain.py::test_invites_members_and_isolates_tandem_rows`; `backend/tests/test_product_completion.py::test_invitation_revoke_resend_and_history_use_management_identifiers` |
| Owner promotion/demotion, removal, leave, final-owner invariant | `backend/tests/test_product_completion.py::test_membership_roles_leave_removal_and_last_owner_race` |
| Former-member attribution and deactivated membership behavior | `backend/tests/test_product_completion.py::test_account_lifecycle_is_explicit_and_preserves_shared_memory_anonymity` |
| Reflection authorship and independent member reactions | `backend/tests/test_memory_domain.py::test_v1_reflections_recovery_duplicates_rediscovery_and_preferences` |
| Cross-Tandem participant and duplicate isolation | `backend/tests/test_memory_domain.py::test_memory_vertical_slice_is_member_scoped_and_versioned`; `test_v1_reflections_recovery_duplicates_rediscovery_and_preferences` |
| Private media identifiers and cleanup | `backend/tests/test_media_api.py::test_member_media_is_private_and_memory_delete_cleans_objects` |
| Per-user Tandem preferences and resurfacing | `backend/tests/test_memory_domain.py::test_v1_reflections_recovery_duplicates_rediscovery_and_preferences` |
| Protected-field mass assignment and upload validation | `backend/tests/test_security_hardening.py::test_sensitive_mutation_schemas_forbid_protected_properties`; `backend/tests/test_media_processing.py` |

## Production execution overlay

These are explicit production execution cases, separate from their lower-layer coverage above.
The live write suite uses one genuine Google identity. Multi-user authorization remains in the PG18
suite and is not represented as live OAuth evidence.

| ID | Production-only case | Exact unblock requirement | Coverage |
|---|---|---|---|
| LIVE-01 | authenticated one-account read/write journey | one genuine OAuth storage state, explicit write opt-in, unique `[E2E]` namespace | LIVE-AUTOMATED |
| LIVE-02 | A/B/C isolation and membership lifecycle | PG18 tests `test_invites_members_and_isolates_tandem_rows`, `test_tandem_rls_create_listing_and_direct_sql_boundaries`, and `test_membership_roles_leave_removal_and_last_owner_race` | LOCAL-INTEGRATION |
| LIVE-03 | live TMDb/Geoapify/B2 writes and private media | one-account storage state, live provider configuration, disposable B2 namespace, cleanup access | LIVE-AUTOMATED |
| LIVE-04 | irreversible account deletion and second-human OAuth flows | never use the available account for deletion; second human identity is required | MANUAL |
| LIVE-05 | live anniversary cron/manual trigger | Render job operator access and a disposable anniversary fixture | MANUAL |
| LIVE-06 | media cleanup failure/retry | PG18/storage mock coverage; production failure injection is unsafe | LOCAL-INTEGRATION |

### Final live evidence and defect disposition

The final clean run used `https://tandem-web-xnih.onrender.com` with the production opt-in,
write opt-in, one saved real Google-authenticated storage state, and a unique `[E2E]` namespace:

```text
npx playwright test tests/e2e/production --config=playwright.production.config.ts
4 passed, 1 worker
```

The anonymous smoke genuinely had empty browser storage and verified the Login shell and protected
boundaries. The authenticated suite used the saved state, completed the one-account provider/media
journey, and cleaned every namespaced resource. No test-login endpoint, fake user, or auth bypass was
used.

The only product defect found in the live pass was Geoapify response normalization: production's
`format=json` response uses `results[]`, while the parser expected `features[]`. This was fixed in
`ae97f68a99c96fa26092cecb087ce5142347039`; malformed provider schemas now fail as provider errors
instead of silently becoming empty results, and the deployed fix passed the subsequent live run.

The remaining findings were test-harness defects only: raw APIRequestContext writes lacked the
browser origin required by `SameOriginMiddleware`; unsigned private B2 objects correctly returned
401; the Year Review assertion ignored the resurfacing preference; and the combined run needed an
explicit empty anonymous state, a bounded 120-second write timeout, and one production worker.
Product security and backend behavior were unchanged.

## Coverage limitations and safe execution policy

The final production run used the safe unauthenticated/readiness suite and the separate one-account
write suite together: **4/4 passed with one worker**. The read-only file explicitly overrides the
global storage state with empty cookies/origins, while the write file uses the locally stored state
captured through the normal Google flow. All generated `[E2E]` resources were cleaned up. No auth
bypass or fake production user was used.

Account deletion, second-human OAuth, and other multi-human invitation/account-lifecycle flows
remain MANUAL by design. Multi-user authorization is LOCAL-INTEGRATION under the exact PG18
production-shaped roles; it is not claimed as live OAuth evidence.

No production test accepts arbitrary resource IDs. Any future write suite must require the exact
production hostname, an explicit opt-in, a unique `[E2E]` namespace, run-local ID tracking, and a
second opt-in for irreversible account or resource deletion.

Final classification totals remain 136: 8 LIVE-AUTOMATED, 104 LOCAL-INTEGRATION,
11 UNIT/COMPONENT, 13 MANUAL, and 0 BLOCKED.
