# Tandem Repo Takeover Guide

> Historical guide from before `tandem/product-cleanup`. Its Firebase/Foursquare/watchlist
> implementation details are retained for context only; they are not active runtime paths.

> Historical pre-foundation snapshot. Current setup, security status and migration priorities are in `README.md`, `docs/REPOSITORY_AUDIT.md` and `docs/TARGET_ARCHITECTURE.md`. Review those before following the old provider-key or deployment guidance below.

## What This Repo Is

This project started as a movie journal and is now halfway through becoming **Tandem**, a shared relationship/activity journal.

Today it does two things in the same app:

- A movie workflow:
  `search -> add to watched -> add to watchlist -> edit/delete entries`
- A newer shared-event workflow:
  `add event -> save to Firestore under a tandem -> view timeline -> start adding place search/edit/delete/filtering`

The repo is in a transition state. The movie side is more complete. The timeline/shared-event side is actively being built and is only partially finished.

## Current Snapshot

- Frontend only app built with `React + Vite`.
- Styling is `Tailwind CSS` with a dark zinc/indigo theme.
- Database is `Firestore` from Firebase.
- Movie search uses `TMDb`.
- Place search uses `Foursquare`.
- Hosting is configured for `Firebase Hosting`.
- There is **no auth yet**.
- There is **no backend server**.
- Firebase config is currently hardcoded in the frontend.
- A placeholder tandem scope is being used:
  `test-tandem-id`

## How To Run It

### Prerequisites

- Node installed. This machine currently has `node v22.17.1`.
- npm installed. This machine currently has `npm 10.9.2`.
- Dependencies installed in `node_modules`.

### Install

If you ever need to reinstall:

```bash
npm install
```

### Start Dev Server

Use:

```bash
npm run dev
```

If PowerShell blocks `npm`, use:

```bash
npm.cmd run dev
```

Vite will print a local URL, usually something like:

```text
http://localhost:5173
```

### Production Build

Use:

```bash
npm.cmd run build
```

I verified the production build succeeds right now.

### Lint

Use:

```bash
npm.cmd run lint
```

Lint currently reports:

- `src/components/Watchlist.jsx`
  `lastDeleted` is unused.
- `tailwind.config.js`
  ESLint complains about `require(...)`.
- `src/components/EditMovieModal.jsx`
  hook dependency warning.
- `src/components/FoursquareSearch.jsx`
  hook dependency warning.

So the app builds, but lint is not clean.

## Environment Variables

The app currently expects a root `.env` file with:

```env
VITE_TMDB_API_KEY=...
VITE_FOURSQUARE_API_KEY=...
```

### What They Are Used For

- `VITE_TMDB_API_KEY`
  Used by `src/components/MovieSearch.jsx` for TMDb movie and person search.
- `VITE_FOURSQUARE_API_KEY`
  Used by `src/components/FoursquareSearch.jsx` for place lookup.

### Important Notes

- The current `.env` file already exists locally in this repo.
- Since Vite exposes `VITE_*` variables to the client, these keys are frontend-visible at runtime.
- If you continue the project seriously, consider rotating keys and moving toward safer production handling where possible.
- Firebase config is **not** in env vars right now. It is hardcoded in `src/firebase.js`.

## Firebase Setup

### Firebase Project

This repo is pointed at:

- Firebase project id:
  `movie-journal-6e7f5`

That appears in:

- `.firebaserc`
- `src/firebase.js`

### Hosting

`firebase.json` is configured to serve the built `dist` folder with SPA rewrites back to `index.html`.

That means the intended hosting flow is:

```bash
npm run build
firebase deploy
```

There is no deploy script in `package.json`, so deployment would be done manually with the Firebase CLI.

### Firestore Usage

The app talks to Firestore directly from the browser. Main collections/subcollections in use:

- `watchedMovies`
- `watchlistMovies`
- `tandems/{tandemId}/events`

There are no server-side rules/helpers in this repo, so access/security depends entirely on Firebase project configuration outside this codebase.

## Project Structure

High-level folders/files:

- `src/App.jsx`
  Main shell, header, tabs, top-level movie listeners, and the new event/timeline entry points.
- `src/components`
  Main feature components.
- `src/components/ui`
  Small reusable UI primitives like `button`, `dialog`, `calendar`, `textarea`, `badge`.
- `src/firebase.js`
  Firebase app initialization and Firestore export.
- `src/index.css`
  Tailwind setup plus extra dark-theme styles and animation overrides.
- `Northstar.md`
  Working product roadmap / module notes.

## Tech Stack

- React 19
- Vite 7
- Tailwind CSS 3
- Firebase 12
- date-fns
- Radix Dialog
- Headless UI transitions
- Lucide icons
- react-datepicker
- emoji-picker-react
- react-hot-toast

## How The App Works Today

## 1. App Shell

`src/App.jsx` is the main screen. It shows:

- Header with the Tandem branding
- Add Event button
- Tabs:
  `Search`, `Watched`, `Watchlist`, `Timeline`

The app still contains legacy movie-oriented top-level state:

- watched movie snapshot listener
- watchlist snapshot listener
- movie add/delete handlers

Some of those props are still passed into child components even though the children now fetch their own data. That is one sign the app is mid-refactor rather than fully cleaned up.

## 2. Movie Search Flow

Main file:

- `src/components/MovieSearch.jsx`

How it works:

- User types a search.
- App calls TMDb movie search.
- If results are very small, it also tries TMDb person search.
- If it finds a matching person, it fetches that person’s movie credits.
- Results are merged and displayed as cards.
- Each result card supports:
  add to watched
- Each result card also supports:
  add to watchlist

### Add To Watched

Main file:

- `src/components/AddMovieModal.jsx`

What it captures:

- date watched
- rating
- rich-ish review text using a contentEditable editor
- optional emoji insertion

Data written to `watchedMovies`:

- `tmdbId`
- `title`
- `poster`
- `dateWatched`
- `rating`
- `review`

## 3. Watched List

Main file:

- `src/components/WatchedList.jsx`

How it works:

- Reads `watchedMovies` from Firestore in descending `dateWatched` order.
- Normalizes Firestore timestamps and some old string date formats.
- Supports:
  month filter
- Supports:
  title search
- Supports:
  load more pagination in the UI
- Supports:
  read full review
- Supports:
  edit watched item
- Supports:
  delete watched item

### Edit Watched Item

Main file:

- `src/components/EditMovieModal.jsx`

What it can do:

- update an existing watched movie
- convert a watchlist item into a watched movie

It reuses the same rating/date/review editing ideas as the add modal.

## 4. Watchlist

Main files:

- `src/components/Watchlist.jsx`
- `src/components/WatchlistCard.jsx`
- `src/components/AddToWatchlistButton.jsx`

How it works:

- `AddToWatchlistButton` checks Firestore to avoid duplicate `tmdbId`s.
- It writes to `watchlistMovies`.
- Watchlist screen listens to `watchlistMovies` ordered by `addedAt desc`.
- Supports:
  text search
- Supports:
  simple sort
- Supports:
  remove from watchlist
- Supports:
  undo remove with a toast
- Supports:
  mark as watched

### Watchlist Document Shape

Typical fields:

- `tmdbId`
- `title`
- `poster`
- `year`
- `addedAt`

## 5. Shared Event / Timeline Flow

This is the newer feature area and the reason the repo feels split between old and new.

Main files:

- `src/components/AddEventModal.jsx`
- `src/components/Timeline.jsx`
- `src/components/EditEventModal.jsx`
- `src/components/FoursquareSearch.jsx`

### Intended Goal

Instead of tracking only movies, the app should also track shared life events:

- Movie
- Place
- Trip
- Activity

These are stored under:

```text
tandems/{tandemId}/events
```

Right now the tandem id is hardcoded to:

```text
test-tandem-id
```

### Add Event Modal

`AddEventModal.jsx` currently collects:

- `category`
- `title`
- `location`
- `date`
- `participants`
- `rating`
- `review`
- `notes`

It writes an event object with roughly these fields:

- `title`
- `category`
- `location`
- `date`
- `participants`
- `rating`
- `review`
- `notes`
- `source`
- `createdAt`

`source` is set as:

- `foursquare` if a location was selected
- `tmdb` if category is `Movie`
- `manual` otherwise

### Timeline

`Timeline.jsx`:

- listens to `tandems/{tandemId}/events`
- orders by `date desc`
- renders each card in the timeline
- supports category filtering
- supports month filtering
- supports newest/oldest sorting
- supports delete
- tries to support edit

### Edit Event

`EditEventModal.jsx` can update:

- title
- date
- participants
- rating
- review
- notes
- `updatedAt`

This is the beginning of event editing, but it still needs cleanup in how it is opened/closed from the timeline.

### Foursquare Search

`FoursquareSearch.jsx`:

- gets browser geolocation on mount if allowed
- uses `ll=lat,lng` when available
- falls back to manual city input with `near=city`
- searches Foursquare Places API
- returns a location object back to the event form

Selected location shape is roughly:

- `name`
- `lat`
- `lng`
- `address`
- `source`

## What Is Actually Finished vs In Progress

### More Stable / More Complete

- Movie search
- Add watched movie
- Watchlist add/remove
- Mark watchlist item as watched
- Watched list browsing
- Edit watched entries
- Delete watched entries

### Mid-Build / In Progress

- Shared event creation
- Timeline browsing
- Event editing
- Event deletion
- Place search quality and UX
- Overall refactor from movie app into Tandem app

## Known Rough Edges

These are the biggest things to know before taking over.

### 1. Placeholder Tandem Scope

The timeline system is not user-aware yet.

Current behavior:

- App always reads/writes events under `test-tandem-id`

Future plan from `Northstar.md`:

- replace with authenticated user id or group-based tandem id

### 2. Place Event Creation Looks Incomplete

`AddEventModal.jsx` validates `title`, but in the `Place` flow the UI mainly sets `location`, not `title`.

That means:

- place events may fail validation unless title handling is adjusted
- or title needs to be auto-filled from the selected place

This is one of the first real bugs I would fix.

### 3. Event Edit Modal Wiring Needs Cleanup

`Timeline.jsx` stores `editingEvent` and conditionally renders `EditEventModal`, but `EditEventModal` itself also manages its own `open` state with a `DialogTrigger`.

That creates a mismatch:

- timeline wants to open it directly
- modal is still built like a self-triggered component

This likely needs a refactor so the modal is truly controlled by the parent.

### 4. App-Level State Is Partly Redundant

`App.jsx` still owns watched/watchlist state and passes props into screens, but `WatchedList.jsx` and `Watchlist.jsx` also fetch directly from Firestore themselves.

So right now:

- some props are redundant
- there is stale architecture from the earlier app version

### 5. Generic README Is Outdated

`README.md` is still basically the default Vite starter text and does not explain this app.

This new handoff doc is effectively the real README until that gets replaced.

### 6. Secrets / Config Shape Is Not Mature Yet

- Firebase config is hardcoded in frontend code.
- API keys are in `.env`.
- There is no auth.
- There is no backend.
- There is no documented Firestore rules setup in this repo.

That is fine for prototyping, but not production-ready.

### 7. Build Is Clean Enough, Lint Is Not

Current status:

- production build works
- lint has 2 errors and 2 warnings

Nothing looks catastrophic, but there is cleanup debt.

### 8. Encoding / Copy-Paste Noise Exists In Some Files

Some comments and strings show garbled emoji or encoding artifacts. That usually happens from copy/paste between tools/editors.

It does not stop the app from building, but it is a sign the codebase could use a small cleanup pass.

## Current Data Model

## watchedMovies

Used for the watched movie library.

Observed fields:

- `tmdbId`
- `title`
- `poster`
- `dateWatched`
- `rating`
- `review`

## watchlistMovies

Used for the future-watch list.

Observed fields:

- `tmdbId`
- `title`
- `poster`
- `year`
- `addedAt`

## tandems/{tandemId}/events

Used for shared timeline events.

Observed fields:

- `title`
- `category`
- `location`
- `date`
- `participants`
- `rating`
- `review`
- `notes`
- `source`
- `createdAt`
- `updatedAt`

### Event Category Values In Code

- `Movie`
- `Place`
- `Trip`
- `Activity`

### Event Source Values In Code

- `tmdb`
- `foursquare`
- `manual`

## UI / Styling Notes

- Tailwind drives most styling.
- The visual theme is dark:
  zinc backgrounds, indigo accents, white/light-zinc text.
- There are local UI primitives in `src/components/ui`.
- `react-datepicker` gets custom dark-theme overrides from `src/index.css`.
- Watchlist and watched screens are more visually polished than the newer timeline flow.

## Repo State Notes

At the moment of writing this guide, the git working tree already contains in-progress local changes around Module 3. That matches what we saw in the code:

- `src/components/AddEventModal.jsx`
- `src/components/EditEventModal.jsx`
- `src/components/FoursquareSearch.jsx`
- `src/components/Timeline.jsx`
- `src/components/ui/*`
- `src/App.jsx`
- `Northstar.md`

So if you come back later and wonder why the repo feels half-finished, that is real: the new Tandem event work is not fully settled yet.

## Suggested First Steps If You’re Taking It Over Again

If I were resuming this project, I would do the work in this order:

1. Clean up the docs and setup.
   Replace the default `README.md` with a shorter version of this guide.
2. Fix the event creation bug for `Place` events.
   Make selected place set both `location` and a sane `title`.
3. Refactor event editing into a controlled modal.
   Parent opens it, child only renders/edit-saves.
4. Decide whether `App.jsx` or each screen owns Firestore subscriptions.
   Pick one pattern and remove the duplicate one.
5. Finish Module 3.
   Event preview, user/group scoping, reliable edit/delete, and better filters.
6. Add authentication before treating tandem data as real user data.
7. Move secrets/config to a cleaner production approach.

## Fast Mental Model

If you only remember one thing, remember this:

- This was originally a movie tracker.
- You later started turning it into a shared couple/activity app called Tandem.
- The movie side is mostly working.
- The shared timeline side is promising but unfinished.
- The biggest architectural missing piece is real user/group identity instead of `test-tandem-id`.

## Command Cheatsheet

Install deps:

```bash
npm install
```

Run dev server:

```bash
npm.cmd run dev
```

Build production bundle:

```bash
npm.cmd run build
```

Run lint:

```bash
npm.cmd run lint
```

Firebase deploy:

```bash
firebase deploy
```
