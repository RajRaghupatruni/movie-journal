# Capture integrations

Tandem keeps provider access behind FastAPI. The browser calls only Tandem endpoints; it
never receives TMDb or Geoapify credentials and never depends on their raw response shapes.

## TMDb

Set `TMDB_API_TOKEN` in the backend runtime environment. This is a TMDb API Read Access Token,
not a `VITE_*` variable. `GET /api/integrations/movies/search?q=` and
`GET /api/integrations/movies/{tmdb_id}` return normalized movie data. Requests have a short
timeout, bounded result count, redacted errors, and correlation IDs in structured logs. Tokens
are not logged or included in responses. Tandem displays TMDb artwork and should retain the
required TMDb attribution in production product/legal copy.

## Geoapify

Set `GEOAPIFY_API_KEY` in the backend runtime environment. `GET /api/integrations/places/search?q=`
uses Geoapify autocomplete and returns only the Tandem place schema: provider ID, name,
formatted address, locality fields, coordinates, and category. The raw Geoapify feature is
never returned to the browser.

## Snapshots and outages

Selecting a movie or place copies the useful normalized fields into the memory's category
metadata. Movie snapshots include the provider ID, title, release data, artwork URLs, overview,
genres, and runtime. Place snapshots include the provider ID, address, locality, coordinates,
and category. These are historical values: Timeline, search over saved memories, and Memory
Detail do not call either provider. Provider outages return a controlled error and manual movie
or place entry remains available.

Automated tests use mocked HTTP responses and never call live providers. Rotate any old TMDb and
Foursquare credentials before configuring the new backend secrets.
