# Repository audit — foundation milestone

> Historical snapshot taken before `tandem/product-cleanup`. Firebase and Foursquare references
> below describe retired code and are not active architecture. See [Firebase retirement](FIREBASE_MIGRATION.md)
> and [the current roadmap](ROADMAP.md) for the post-cleanup decisions.

Audited 2026-09-09 against the existing working tree, before implementation. All tracked application, configuration and documentation files were inspected, along with the npm lockfile, source imports/HTML sinks, local environment variable names, Git status and local Git history. No Firestore records, deployed rules, provider dashboards or hosted application were accessed. The only pre-existing working-tree modification was `.env`; its contents were preserved. This audit distinguishes source observations from assumptions about the deployed system.

## 1. Current architecture

- React 19 SPA, `src/main.jsx` → `src/App.jsx`, React StrictMode. Four tabs use local state: Search (initial tab), Watched, Watchlist, Timeline. No router, state store, server, authentication or service worker was present.
- Vite 7, ES modules, npm and committed `package-lock.json`. Existing scripts were `dev`, `build`, `preview`, `lint`. Build system and package manager are retained. Compatible security updates were applied within existing version ranges.
- Tailwind 3, PostCSS, custom dark theme/date-picker CSS in `src/index.css`. Both Tailwind 3 and a Tailwind 4 PostCSS package are declared; the existing configuration still builds. Radix Dialog, Headless UI Transition, lucide-react, date-fns, react-datepicker, emoji-picker-react and react-hot-toast support the UI. No redesign was undertaken.
- `App.jsx` subscribes to both root movie collections. `WatchedList.jsx` and `Watchlist.jsx` separately subscribe and ignore the supplied data/filter props. This duplicates reads and state ownership.
- The browser calls Firestore directly. Before cleanup it also called TMDb and Foursquare using `VITE_*` environment values. These are compiled into public JavaScript, not private server settings.
- `firebase.json` serves `dist` with a catch-all `/index.html` rewrite. `.firebaserc` selects project `movie-journal-6e7f5`. `.firebase/hosting.ZGlzdA.cache` was committed generated deployment metadata. There was no Docker, CI, backend, database migration or infrastructure configuration beyond Firebase Hosting.
- Existing docs: default Vite README; `TAKEOVER_GUIDE.md` is the most useful prior code inventory; `Northstar.md` is a conversational unfinished-feature list; `END_PRODUCT_BLUEPRINT.md` includes earlier Firebase/mobile plans. The new target architecture supersedes those plans, while retaining the old documents for context.

## 2. Reusable functionality

| Code | Existing behavior worth retaining |
| --- | --- |
| `MovieSearch.jsx` | 500 ms debounce, movie-title search, person lookup when at most one movie result, then person movie credits, six-result display and add actions |
| `AddMovieModal.jsx` | Watched date, 1–10 rating, rich review formatting and emoji input |
| `AddToWatchlistButton.jsx` | TMDb ID duplicate check and feedback |
| `WatchedList.jsx` | Date normalization, month and title filters, 20-entry batches, review reader, edit/delete confirmation |
| `Watchlist.jsx`, `WatchlistCard.jsx` | Recently added/title sorting, title search, delete with undo, mark as watched |
| `AddEventModal.jsx` | Movie/Place/Trip/Activity form, participants, date, review and notes |
| `Timeline.jsx` | Category/month filters, date ordering, source display, edit/delete entry points |
| `FoursquareSearch.jsx` | 400 ms debounce, optional browser location, New York/manual city fallback, normalized place selection |
| `components/ui/*`, `index.css` | Existing primitives, spacing, dialogs, calendars and theme |

Provider algorithms and UI components are retained, but live provider requests are temporarily disabled for this milestone. Saved Firestore content, watched/watchlist workflows and non-place event flows retain their existing persistence paths. Basic review formatting remains supported through sanitization. Paste inserts plain text and HTML drag/drop into review editors is blocked.

## 3. Firebase dependencies and authentication assumptions

`src/firebase.js` initializes the Firebase app and exports Firestore. It includes public client identifiers (`apiKey`, `authDomain`, `projectId`, `storageBucket`, sender ID and app ID). These are not Firebase Admin credentials and are retained during migration. There is no Firebase Auth, Storage SDK use, Admin SDK, service-account file, session, login, membership check or authenticated user context in application code.

Direct Firestore consumers: `App.jsx`, `firebaseHelpers.js`, `AddEventModal.jsx`, `EditEventModal.jsx`, `Timeline.jsx`, `WatchedList.jsx`, `Watchlist.jsx`, `AddToWatchlistButton.jsx`, `EditMovieModal.jsx`. `AddMovieModal.jsx` also constructs Firestore Timestamps. APIs include `onSnapshot`, `addDoc`, `updateDoc`, `deleteDoc`, `setDoc`, `getDocs`, `query`, `orderBy`, `where`, `Timestamp` and `serverTimestamp`.

`App.jsx` supplies `test-tandem-id` to Add Event and Timeline. Timeline defaults to the same value; Add Event's unused fallback is `test-tandem`. These strings are routing placeholders, not access controls. Root movie collections have no tandem scope at all. Do not simply substitute an arbitrary user ID: migration requires explicit group membership and ownership mapping.

There are **no checked-in Firestore rules or indexes**, emulator configuration, or rules tests. `firebase.json` only configures Hosting. Deployed rules were not inspected: the absence of rules in Git does not prove the live database is open. The final read-only browser smoke check received `permission-denied` from the existing unauthenticated snapshot listeners; no saved records could be retrieved. This establishes that those reads were denied in this environment, not the complete live authorization policy. No live rules were changed.

## 4. Security findings and remediation

| Finding | Evidence and action |
| --- | --- |
| Committed provider credentials | `.env` was tracked; local names are `VITE_TMDB_API_KEY` and `VITE_FOURSQUARE_API_KEY`. History scan confirms TMDb assignment in the initial commit. `.env` removed from Git index only; local edits preserved. Ignore patterns now cover nested env files, Firebase cache, key files and Python output. |
| Browser secret exposure | TMDb key was sent as a query parameter; Foursquare key in an Authorization header. Removed frontend secret reads and set Vite `envPrefix: []`. Search requests are disabled with explicit UI notices pending backend integrations. No replacements created. |
| Stored XSS: display | Two `dangerouslySetInnerHTML` sinks in Watched List (card and reader) and one in Timeline consumed Firestore reviews verbatim. All now call typed `sanitizeReviewHtml`. |
| Stored XSS: editor | `EditMovieModal` assigned stored review to `editorRef.current.innerHTML`. Assignment is now sanitized. Both movie editors sanitize before saving; paste is plain text and drop is blocked. Ordinary React text interpolation remains escaped. |
| Unsafe rich content policy | DOMPurify allows only paragraph/div/line-break and basic emphasis/list tags; no attributes, links, style, images, SVG, MathML, scripts or frames. Existing raw Firestore records are not rewritten. Future backend validation must enforce the same policy; a browser sanitizer does not secure direct database writes. |
| Dependency vulnerabilities | Initial npm audit reported 21 (2 low, 4 moderate, 12 high, 3 critical), including transitive protobufjs/tar/websocket-driver and Vite tooling. Compatible `npm audit fix` reduced the report to zero at verification time. This is not a claim about all possible vulnerabilities. |
| Unknown privacy boundary | No identity or checked-in rules. New API is local development infrastructure, not a production-ready private application. Compose ports bind to loopback. |
| Secret recurrence | Added names-only `.env.example`, source inventory guard, Gitleaks defaults plus a provider-specific rule, and CI current-checkout scanning. Narrow exception only for the public Firebase browser key line in `src/firebase.js`. No history-wide secret allowlist. |

Source scan includes tracked and untracked nonignored files, excluding staged deletions. Local ignored `.env` was inspected only for variable names/presence; provider values are never printed or copied to documentation. Gitleaks history scan covers the six locally available commits, not inaccessible refs, deleted remotes, forks or external caches. No other server credential files were identified. Scan results cannot prove that previously shared secrets have not been copied elsewhere.

## 5. Credentials requiring manual rotation / revocation

1. **TMDb:** revoke/regenerate every previously committed or browser-delivered API key/token. A credential was present in `.env` in initial commit `e7c942f`. Review provider usage and account settings. Store future replacements only in backend deployment secrets, never `VITE_*` variables.
2. **Foursquare:** revoke every previously used/committed key even if the local history scanner does not identify its particular encoding. The current local `.env` has a Foursquare key name and the old app sent its value directly from the browser. Review usage. Geoapify is the later intended place integration; do not create a replacement Foursquare key just for this milestone.
3. **Other previously committed provider secrets:** apply the same assumption if additional refs/accounts identify them. No Google OAuth, S3 or Resend credentials are needed yet.
4. **Firebase client config:** not a server secret. Review Google API key application/API restrictions and actual Firestore rules in the console. Do not confuse retaining client config with approving current database privacy. If any Admin/private key is discovered outside this checkout, revoke it separately.
5. Remove compromised values from the user's preserved local `.env` after rotation and record incident closure outside Git. Consider coordinated Git history cleanup, old Firebase Hosting releases, CI artifacts and cached bundles after rotation. **No history rewrite, force-push, cloud deployment or provider revocation was performed.** Untracking alone does not erase history.

## 6. Current data model (observed from code)

| Firestore path | Fields and semantics |
| --- | --- |
| `watchedMovies/{autoId}` | `tmdbId` usually numeric; `title`; `poster` usually a TMDb path; `dateWatched` Firestore Timestamp or legacy `MM/DD/YYYY`; `rating` normally a string from movie forms; `review` HTML string. Edit/mark-watched writes same shape. |
| `watchlistMovies/{autoId}` | `tmdbId`, `title`, `poster` written as full TMDb image URL, `year` string or `N/A`, `addedAt` Timestamp. Undo writes `serverTimestamp()` and spreads the document's `id` into its body. |
| `tandems/{tandemId}/events/{autoId}` | `title`; `category` Movie/Place/Trip/Activity; nullable `location`; `date` Timestamp; `participants` array of free text names; nullable integer `rating`; `review`, `notes`; `source` tmdb/foursquare/manual; `createdAt`; optional `updatedAt`. |
| Event `location` | `name`, `lat`, `lng`, `address`, `source`. Foursquare result ID is **not** saved. |

No implemented users, memberships, media records or tandem parent-document fields were found. Proposed `users`/`members` collections in old docs are plans, not existing code. Movie events entered manually can be labeled `tmdb` solely because of category; that does not prove TMDb provenance. Deduplication is client-side and race-prone. Marking watched performs an insert followed by a separate delete, without a transaction.

## 7. Proposed migration map and exact next tasks

No application schema or data migration is included now. The empty `0001_foundation` migration creates only Alembic tracking.

| Legacy concern | Later PostgreSQL/backend destination |
| --- | --- |
| Hardcoded tandem context | Explicit `tandems`, `users`, `memberships`; server-enforced membership on every scoped operation |
| Watched and watchlist roots | Tandem-scoped watched/watchlist tables plus provider movie reference; preserve Firestore IDs in an import mapping |
| Events subcollection | Scoped events with typed category, occurrence date, nullable rating and normalized place snapshot |
| Free text participants | Preserve display names until a reviewed mapping to identities exists; never infer membership from a name |
| Reviews | Explicit sanitized HTML contract preserving basic formatting, or a separately approved structured-text migration |
| TMDb requests | Backend-owned search/person/credits adapter with timeout, validation and response mapping |
| Foursquare | Preserve existing location snapshots; later Geoapify adapter. Do not relabel Foursquare records as Geoapify or assume IDs translate. |
| Firestore snapshots | Typed HTTP reads/mutations; start with refetch after mutation. Decide polling needs based on real collaboration requirements. |

Next milestones, in dependency order (documented only):

1. Complete provider revocation, inspect deployed Firestore rules, and inventory all legacy data owners/paths with owner-approved read-only exports. Decide whether existing root movie entries belong to one tandem; do not guess.
2. Approve API contracts and SQL schema: IDs, memberships, movie uniqueness, repeat viewings, date-only versus timestamp semantics, rating range, missing posters, place snapshots and review policy. Add an Alembic schema migration and isolation tests in a separate milestone.
3. Implement Google OAuth/OIDC and membership authorization with server sessions, secure cookies, CSRF protection and explicit unauthorized/cross-tandem tests. No product endpoints should be exposed publicly before that boundary exists.
4. Add authenticated backend TMDb and Geoapify integrations with response schemas, timeouts, bounded requests, redacted errors and provider-only server configuration. Reconnect the preserved search UI and test title/person/credits behavior and place title selection.
5. Implement watched/watchlist HTTP operations first, including transactional mark-watched, uniqueness enforcement and stable poster/date normalization. Add typed frontend adapters and migrate one screen at a time; avoid dual writes.
6. Build a separately authorized import command with dry run, source-ID mapping, counts/checksums, malformed-data report, explicit tandem ownership, repeatability and rollback/backup procedure. Test on fixtures, then an isolated export. Do not import while ownership is unresolved.
7. Migrate event CRUD and timeline filters, fix controlled edit-modal wiring and place title validation, and verify existing saved reviews and filters. Remove duplicate subscriptions as each screen's HTTP replacement passes parity checks.
8. Only after all persisted features have replacements and imports are verified: remove Firebase SDK/helpers/config/hosting, hardcoded tandem defaults and obsolete docs. Later add private media and email within their own milestones.

## 8. Files/features to preserve

Preserve current React screens, date/review editors, watchlist conversion and undo flows, filter behavior, styles and UI primitives. Keep `src/firebase.js`, active Firestore consumers and Firebase Hosting configuration until their replacements work. Keep npm/Vite, the lockfile and existing user's `.env` contents. Retain old planning documents with a superseded notice. New code is typed at the review security boundary and provider-disable boundary; broad JSX conversion is deliberately deferred.

## 9. Files/features likely to delete later

- `src/firebaseHelpers.js` has no imports elsewhere; likely dead wrapper after confirming no external consumers. Left intact.
- `src/App.css`, `src/assets/react.svg` appear to be unused starter assets. `public/vite.svg` is still referenced by `index.html`. No cosmetic deletions now.
- Duplicate App-level subscriptions/state become removable when screen data adapters are migrated.
- Firebase SDK, `firebase.js`, Firebase Hosting files and hardcoded tandem IDs only after feature/data parity.
- Disabled Foursquare request implementation after Geoapify parity; old mobile/Firebase roadmap sections after migration docs settle.
- Generated `.firebase` cache was removed from tracking now, with local file preserved.

## 10. Implementation risks and verification limits

- The app remains dependent on the original Firestore project. Browser navigation loaded all four screen shells, but Firestore snapshot reads failed with `permission-denied`. Saved-data behavior could not be verified and no live data mutation was performed. The owner must review existing access configuration without blindly opening database rules.
- Search is intentionally unavailable until backend integrations exist. This is the unavoidable limitation of removing browser secrets while keeping integrations out of this milestone. Existing search code is retained; saved records are not removed.
- Existing bugs: Place selection sets `location` but not required `title`; Timeline renders a self-triggered Edit Event dialog while expecting parent control; watchlist poster is a full URL but cards prefix it again; rating types and dates differ; movie dedupe can race; watchlist conversion is not atomic; toast host is not mounted; movie save closes before awaited completion; screen listeners lack error callbacks. These are documented, not silently folded into a rewrite.
- Legacy lint began at two errors/two warnings. Node globals configuration fixes the old `require` warning source, but the unused `lastDeleted` error and two hook warnings remain. CI does not claim legacy lint is clean; new Python checks and typed code checks are enforced.
- Existing build warnings include large JavaScript bundle size and redundant line-clamp plugin. No code-splitting or CSS refactor was performed.
- Existing responsive classes remain, but desktop is the only target. No PWA/mobile development, auth, media upload, Redis-dependent features, data import or feature redesign was added.
- Local Compose uses development servers and database credentials stored only in ignored `.env.local`. Persistent volumes survive `down`; changing the password file does not rotate the initialized PostgreSQL role. Redis is unconnected product infrastructure with AOF persistence. This Compose file is not a public deployment recipe.
- Tests cover new foundation behavior and review security, not complete legacy user journeys. See `docs/VERIFICATION.md` for exact results and limitations.
