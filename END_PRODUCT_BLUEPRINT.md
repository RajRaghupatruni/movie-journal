# Tandem End Product Blueprint

## Product Goal

Build Tandem into a shared memory and planning app for two people (or a small group), where users can:

- Log meaningful events (movie, place, trip, activity)
- Keep a shared timeline of memories
- Track watchlist and watched movies
- Filter and revisit memories quickly
- Collaborate in one shared space scoped to a real user/group identity

The end product should feel like:

- A relationship/activity timeline first
- A movie tracker second

## End-State Experience

When a user opens the app, they should land on a timeline view scoped to the selected Tandem group. The timeline should be easy to add to, easy to search/filter, and easy to edit.

Core actions:

- Add Event
- Edit Event
- Delete Event
- Filter/Sort Timeline
- Switch Tandem Group (future, after Module 2 + auth wiring)

## Target Information Architecture

- `Timeline` (default home)
- `Search` (movie discovery via TMDb)
- `Watched` (shared or user-scoped watched entries)
- `Watchlist` (shared or user-scoped watchlist entries)
- `Settings` (future: profile, tandem membership, API/debug metadata)

## Target Page Layout (Desktop)

```text
+------------------------------------------------------------------------------------+
| Tandem                                                     [Add Event] [Profile]   |
| "From watchlist to watched. Together."                                          |
+------------------------------------------------------------------------------------+
| Tabs: [Timeline] [Search] [Watched] [Watchlist]                                  |
+------------------------------------------------------------------------------------+
| Filters: Category [All v]  Month [All v]  Sort [Newest v]  Rating [Any v]        |
| Search: [participant/title/location.................................] [Clear]      |
+------------------------------------------------------------------------------------+
| Timeline Feed                                                                        |
|                                                                                    |
|  [Event Card]  Title + category badge + date + participants + source              |
|                rating, review/notes, place address/map/photo (if present)         |
|                actions: [Edit] [Delete]                                            |
|                                                                                    |
|  [Event Card] ...                                                                  |
|                                                                                    |
|                           [Load more / Infinite scroll]                            |
+------------------------------------------------------------------------------------+
```

## Target Page Layout (Mobile)

```text
+--------------------------------------+
| Tandem                [Add Event]    |
| Tabs: Timeline Search Watched ...    |
+--------------------------------------+
| Category [v]  Month [v]  Sort [v]    |
| Search [..........................]   |
+--------------------------------------+
| Event Card                            |
| Event Card                            |
| Event Card                            |
+--------------------------------------+
```

## Add/Edit Event Modal (Target)

```text
+------------------------------------------------------+
| Add Event                                   [X]      |
| Category: [Movie] [Place] [Trip] [Activity]         |
|                                                      |
| Title / Place Search                                 |
| Date + Time                                          |
| Participants (chips or comma input)                  |
| Rating (optional)                                    |
| Review (optional)                                    |
| Notes (optional)                                     |
| Photo Upload (optional)                              |
| Map Preview (optional, for place)                    |
|                                                      |
| Event Preview Card (before save)                     |
|                                                      |
| [Save Event]                                         |
+------------------------------------------------------+
```

## Northstar Mapping (Module 3 Remaining)

These map directly to the remaining tasks in `Northstar.md`.

## 3.5 Fix Place Search Reliability

Target behavior:

- Place search works with geolocation when user allows location.
- If denied/unavailable, fallback city input appears and works.
- Selecting a place fills both:
  `location` object and a human-friendly `title`.
- Add clear "No results" and "API error" states.

Definition of done:

- Searching common places returns results reliably.
- Place events can be saved without title-validation conflicts.

## 3.6 Event Preview Before Save

Target behavior:

- Modal shows a live preview card of what will be saved.
- Preview updates as user edits fields.
- Save button persists exactly what preview shows.

Definition of done:

- User can sanity-check event details before committing.

## 3.7 Scoped Events (User/Group)

Target behavior:

- Remove hardcoded `test-tandem-id`.
- Resolve `tandemId` from authenticated user context (Module 6) and group membership (Module 2).
- Timeline and event writes are scoped to active tandem/group.

Definition of done:

- No cross-group data bleed.
- Data isolation works when switching tandem context.

## 3.8 Edit/Delete Functionality

Target behavior:

- Edit opens a controlled modal with existing event data prefilled.
- Save updates Firestore document and UI reflects changes in real time.
- Delete uses confirmation and removes event from timeline.

Definition of done:

- No broken modal open/close flows.
- Edit and delete work consistently across all event categories.

## 3.9 Filter/Sort Timeline

Target behavior:

- Category filter: Movie, Place, Trip, Activity.
- Date sort: newest-first, oldest-first.
- Optional filters:
  rating and participant.
- Filters compose (user can apply several at once).

Definition of done:

- Filtering logic is predictable, fast, and reflected in UI controls.

## 3.10 Optional UX Upgrades

Target behavior:

- Place events can show static map preview.
- Events can include photo upload/preview.
- Date picker supports time of day.

Definition of done:

- All optional fields are truly optional and do not block basic save.

## Data Model Target

Keep current collections working while migrating toward identity-based scoping:

- `users/{uid}`
- `tandems/{tandemId}`
- `tandems/{tandemId}/members/{uid}`
- `tandems/{tandemId}/events/{eventId}`

Current movie collections:

- `watchedMovies`
- `watchlistMovies`

Preferred eventual direction:

- Scope movies under tandem (or user + tandem), not only global root collections.

## Non-Functional Targets

- Real-time UI updates remain fast (Firestore snapshots).
- Lint clean or near-clean.
- Stable build with no runtime console errors in core flows.
- Basic empty/loading/error states for each main screen.
- Mobile layouts are fully usable.

## Suggested Delivery Milestones

## Milestone A: Finish Module 3 Core

- 3.5 place reliability
- 3.6 preview card
- 3.8 edit/delete cleanup
- 3.9 filter/sort completion

## Milestone B: Identity + Group Wiring

- 3.7 scoping wired to auth/group context
- remove placeholder tandem id from UI code

## Milestone C: UX Polish

- 3.10 optional upgrades
- visual cleanup and consistency across Timeline/Watched/Watchlist

## "Done" Definition For This Phase

You can consider this phase complete when:

- A logged-in user can select a tandem/group
- All events shown belong only to that tandem/group
- Add/Edit/Delete works end-to-end for every category
- Filtering and sorting are reliable and intuitive
- Place events are easy to add and visually informative
- Timeline is clearly the primary product surface

