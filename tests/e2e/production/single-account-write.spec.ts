import { expect, request as playwrightRequest, test } from '@playwright/test';
import { assertSingleAccountWriteOptIn, e2eName } from './safety';

const pngBytes = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  'base64',
);

async function json(response: Awaited<ReturnType<import('@playwright/test').APIRequestContext['get']>>, status: number) {
  expect(response.status()).toBe(status);
  return response.json();
}

function safeFailureBody(body: unknown) {
  if (body === null || body === undefined) return { body_type: 'empty' };
  if (typeof body !== 'object') return { body_type: typeof body };
  return { body_type: 'object', body_keys: Object.keys(body as Record<string, unknown>).slice(0, 20) };
}

async function browserApi(page: import('@playwright/test').Page, method: string, path: string, body?: unknown) {
  return page.evaluate(async ({ method, path, body }) => {
    const response = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: body === null ? undefined : { 'Content-Type': 'application/json' },
      body: body === null ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    let parsed: unknown = null;
    try { parsed = text ? JSON.parse(text) : null; } catch { parsed = null; }
    return { status: response.status, body: parsed };
  }, { method, path, body: body === undefined ? null : body });
}

async function browserJson(page: import('@playwright/test').Page, method: string, path: string, status: number, body?: unknown) {
  const result = await browserApi(page, method, path, body);
  if (result.status !== status) {
    throw new Error(`Browser API ${method} ${path} returned ${result.status}; ${JSON.stringify(safeFailureBody(result.body))}`);
  }
  return result.body as Record<string, any>;
}

async function browserMultipart(page: import('@playwright/test').Page, path: string, bytes: Uint8Array, status: number) {
  const result = await page.evaluate(async ({ path, bytes }) => {
    const form = new FormData();
    form.append('files', new Blob([new Uint8Array(bytes)], { type: 'image/png' }), 'e2e.png');
    const response = await fetch(path, { method: 'POST', credentials: 'same-origin', body: form });
    const text = await response.text();
    let parsed: unknown = null;
    try { parsed = text ? JSON.parse(text) : null; } catch { parsed = null; }
    return { status: response.status, body: parsed };
  }, { path, bytes: Array.from(bytes) });
  if (result.status !== status) {
    throw new Error(`Browser API POST ${path} returned ${result.status}; ${JSON.stringify(safeFailureBody(result.body))}`);
  }
  return result.body as Array<Record<string, any>>;
}

function compact<T extends Record<string, unknown>>(value: T): Partial<T> {
  return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== null && item !== undefined));
}

test.describe('@write @provider @production-safe one-account V1 journey', () => {
  test.beforeEach(({ baseURL }) => assertSingleAccountWriteOptIn(baseURL));

  test('@write-smoke browser same-origin mutation preflight', async ({ page }) => {
    await page.goto('/');
    await browserJson(page, 'GET', '/api/me', 200);
    await browserJson(page, 'GET', '/api/me/preferences', 200);
    let tandemId: string | undefined;
    try {
      const tandem = await browserJson(page, 'POST', '/api/tandems', 201, {
        name: e2eName('Preflight-Tandem'), timezone: 'America/Chicago',
      });
      tandemId = tandem.id;
      const tandems = await browserJson(page, 'GET', '/api/me/tandems', 200);
      expect(tandems.map((item: { id: string }) => item.id)).toContain(tandemId);
    } finally {
      if (tandemId) await browserJson(page, 'DELETE', `/api/tandems/${tandemId}`, 204, { confirmation: 'DELETE' });
    }
  });

  test('runs isolated single-user creation, providers, media, recovery, navigation, and cleanup', async ({ page, request }) => {
    test.setTimeout(120_000);
    const createdTandems: string[] = [];
    let originalPreferences: Record<string, unknown> | undefined;
    try {
      await page.goto('/');
      await browserJson(page, 'GET', '/api/me', 200);
      await browserJson(page, 'GET', '/api/me/preferences', 200);
      originalPreferences = await json(await request.get('/api/me/preferences'), 200);

      const tandemName = e2eName('Tandem');
      const secondTandemName = e2eName('Second-Tandem');
      const tandem = await browserJson(page, 'POST', '/api/tandems', 201, { name: tandemName, timezone: 'America/Chicago' });
      createdTandems.push(tandem.id);
      const secondTandem = await browserJson(page, 'POST', '/api/tandems', 201, { name: secondTandemName, timezone: 'UTC' });
      createdTandems.push(secondTandem.id);

      const allTandems = await json(await request.get('/api/me/tandems'), 200);
      expect(allTandems.map((item: { id: string }) => item.id)).toEqual(
        expect.arrayContaining(createdTandems),
      );
      expect((await json(await request.get(`/api/tandems/${secondTandem.id}/memories`), 200)).items).toHaveLength(0);

      const date = '2024-09-10';
      const memories: Array<{ id: string; category: string }> = [];
      const createMemory = async (payload: Record<string, unknown>) => {
        const saved = await browserJson(page, 'POST', `/api/tandems/${tandem.id}/memories`, 201, payload);
        memories.push(saved);
        return saved;
      };

      let custom = await createMemory({
        category: 'custom', title: e2eName('Custom-Memory'), local_date: date, timezone: 'America/Chicago',
        metadata: { label: 'single-account regression' }, tags: ['e2e', 'custom'], rating: 8,
      });
      custom = await browserJson(page, 'PATCH', `/api/tandems/${tandem.id}/memories/${custom.id}`, 200, {
        expected_version: custom.version, notes: 'Edited by the one-account production journey.',
      });
      expect(custom.notes).toContain('one-account production journey');
      const activity = await createMemory({
        category: 'activity', title: e2eName('Activity-Memory'), local_date: '2024-09-11', timezone: 'America/Chicago',
        metadata: { activity_kind: 'concert' },
      });
      await createMemory({
        category: 'trip', title: e2eName('Trip-Memory'), local_date: '2024-09-12', end_date: '2024-09-14', timezone: 'America/Chicago',
        metadata: { destination: 'E2E destination', start_date: '2024-09-12', end_date: '2024-09-14' },
      });

      const movieSearch = await json(await request.get('/api/integrations/movies/search?q=Inception'), 200);
      expect(movieSearch.items.length).toBeGreaterThan(0);
      const movie = movieSearch.items[0];
      const movieMemory = await createMemory({
        category: 'movie', title: movie.title, local_date: '2024-09-15', timezone: 'America/Chicago',
        metadata: compact({ provider: 'tmdb', provider_movie_id: String(movie.tmdb_id), movie_title_snapshot: movie.title,
          original_title: movie.original_title, release_year: movie.release_year, release_date: movie.release_date,
          poster_url: movie.poster_url, backdrop_url: movie.backdrop_url, overview: movie.overview,
          genres: movie.genres, runtime_minutes: movie.runtime_minutes }),
      });
      expect(movieMemory.metadata.provider).toBe('tmdb');
      expect(movieMemory.metadata.poster_url || movieMemory.metadata.backdrop_url).toBeTruthy();

      let placeSearch: { items: Array<Record<string, any>> } | undefined;
      for (const query of ['Chicago', 'New York', 'London', 'Paris']) {
        const candidate = await json(await request.get(`/api/integrations/places/search?q=${encodeURIComponent(query)}`), 200);
        if (candidate.items.length > 0) {
          placeSearch = candidate;
          break;
        }
      }
      expect(placeSearch?.items.length || 0).toBeGreaterThan(0);
      const place = placeSearch!.items[0];
      const placeMemory = await createMemory({
        category: 'place', title: place.name, local_date: '2024-09-16', timezone: 'America/Chicago',
        metadata: compact({ provider: 'geoapify', provider_place_id: place.provider_place_id, name: place.name,
          formatted_address: place.formatted_address, city: place.city, region: place.region, country: place.country,
          latitude: place.latitude, longitude: place.longitude, category: place.category }),
      });
      expect(placeMemory.metadata.provider).toBe('geoapify');
      expect(placeMemory.metadata.provider_place_id).toBe(place.provider_place_id);
      expect(memories.map((item) => item.category)).toEqual(
        expect.arrayContaining(['custom', 'activity', 'trip', 'movie', 'place']),
      );

      const duplicates = await json(
        await request.get(`/api/tandems/${tandem.id}/memories/duplicates?category=movie&local_date=2024-09-15&title=${encodeURIComponent(movie.title)}&provider_id=${movie.tmdb_id}`),
        200,
      );
      expect(duplicates.some((item: { id: string }) => item.id === movieMemory.id)).toBe(true);

      const filtered = await json(await request.get(`/api/tandems/${tandem.id}/memories?category=movie&year=2024&q=${encodeURIComponent(movie.title)}`), 200);
      expect(filtered.items.map((item: { id: string }) => item.id)).toContain(movieMemory.id);
      expect((await json(await request.get(`/api/tandems/${tandem.id}/memories?category=trip`), 200)).items[0].end_date).toBe('2024-09-14');

      const reflection = await browserJson(page, 'PUT', `/api/tandems/${tandem.id}/memories/${movieMemory.id}/reflections/me`, 200, {
        rating: 9, reaction: 'favorite', note: 'One-account production regression.',
      });
      expect(reflection.rating).toBe(9);
      expect((await json(await request.get(`/api/tandems/${tandem.id}/memories/${movieMemory.id}`), 200)).my_reflection.note).toContain('production regression');

      const media = await browserMultipart(page, `/api/tandems/${tandem.id}/memories/${custom.id}/media`, pngBytes, 201);
      expect(media).toHaveLength(1);
      expect((await json(await request.get(`/api/tandems/${tandem.id}/memories/${custom.id}/media`), 200))[0].url).toMatch(/^https?:\/\//);
      const signedUrl = new URL(media[0].url);
      const anonymous = await playwrightRequest.newContext();
      try {
        let presigned;
        try {
          // Keep the complete capability URL inside the request; never include it in diagnostics.
          presigned = await anonymous.get(media[0].url);
        } catch {
          throw new Error('Presigned media request failed before a response was received');
        }
        expect(presigned.status(), 'presigned media status').toBe(200);
        const presignedBytes = await presigned.body();
        expect(presignedBytes.length, 'presigned media body length').toBeGreaterThan(0);
        const responseContentType = (presigned.headers()['content-type'] || '').split(';', 1)[0].toLowerCase();
        expect(responseContentType, 'presigned media content type').toMatch(/^image\//);
        expect(responseContentType).toBe(String(media[0].content_type || '').toLowerCase());

        const rawObject = await anonymous.get(`${signedUrl.origin}${signedUrl.pathname}`);
        expect([400, 401, 403, 404], 'unsigned private object denial status').toContain(rawObject.status());
      } finally {
        await anonymous.dispose();
      }
      await browserJson(page, 'DELETE', `/api/tandems/${tandem.id}/memories/${custom.id}/media/${media[0].id}`, 204);

      // Rediscovery is preference-scoped. Verify the normal eligible-memory
      // contract before disabling resurfacing for this user's Tandem.
      const createdMemoryIds = memories.map((item) => item.id);
      const enabledShuffle = await json(
        await request.get(`/api/me/rediscovery/shuffle?tandem_id=${tandem.id}&seed=e2e`),
        200,
      );
      expect(enabledShuffle.memory).toBeTruthy();
      expect(createdMemoryIds).toContain(enabledShuffle.memory.id);

      const enabledYearReview = await json(
        await request.get(`/api/me/rediscovery/year-review?year=2024&tandem_id=${tandem.id}`),
        200,
      );
      expect(enabledYearReview.memory_count).toBeGreaterThan(0);
      expect(enabledYearReview.highlights.length).toBeGreaterThan(0);

      const enabledCollections = await json(
        await request.get(`/api/me/rediscovery/collections?tandem_id=${tandem.id}`),
        200,
      );
      expect(Array.isArray(enabledCollections.items)).toBe(true);
      const yearCollection = enabledCollections.items.find(
        (item: { key: string; memory_ids: string[] }) => item.key === 'year-2024',
      );
      expect(yearCollection?.memory_ids ?? []).toEqual(expect.arrayContaining(createdMemoryIds));

      const tandemPreference = await browserJson(page, 'PATCH', `/api/tandems/${tandem.id}/preferences`, 200, {
        resurfacing_enabled: false, routine_notifications_enabled: false,
      });
      expect(tandemPreference.resurfacing_enabled).toBe(false);
      expect(tandemPreference.routine_notifications_enabled).toBe(false);
      const updatedPreferences = await browserJson(page, 'PATCH', '/api/me/preferences', 200, { anniversary_notifications_enabled: false });
      expect(updatedPreferences.anniversary_notifications_enabled).toBe(false);
      expect((await json(await request.get(`/api/me/on-this-day?tandem_id=${tandem.id}`), 200)).anniversaries).toEqual([]);
      expect((await json(await request.get(`/api/me/rediscovery/shuffle?tandem_id=${tandem.id}&seed=e2e`), 200)).memory).toBeNull();
      const disabledYearReview = await json(
        await request.get(`/api/me/rediscovery/year-review?year=2024&tandem_id=${tandem.id}`),
        200,
      );
      expect(disabledYearReview.memory_count).toBe(0);
      expect(disabledYearReview.highlights).toEqual([]);

      const disabledCollections = await json(
        await request.get(`/api/me/rediscovery/collections?tandem_id=${tandem.id}`),
        200,
      );
      expect(Array.isArray(disabledCollections.items)).toBe(true);
      const disabledMemoryIds = disabledCollections.items.flatMap(
        (item: { memory_ids: string[] }) => item.memory_ids,
      );
      expect(disabledMemoryIds).not.toEqual(expect.arrayContaining(createdMemoryIds));
      expect((await json(await request.get('/api/me/notifications'), 200)).items).toBeDefined();

      // Restore the Tandem's normal resurfacing state before validating the
      // ordinary Memories/navigation surfaces below.
      const restoredTandemPreference = await browserJson(
        page,
        'PATCH',
        `/api/tandems/${tandem.id}/preferences`,
        200,
        { resurfacing_enabled: true, routine_notifications_enabled: true },
      );
      expect(restoredTandemPreference.resurfacing_enabled).toBe(true);

      const renamed = e2eName('Renamed-Tandem');
      const updatedTandem = await browserJson(page, 'PATCH', `/api/tandems/${tandem.id}`, 200, { name: renamed, timezone: 'UTC' });
      expect(updatedTandem.name).toBe(renamed);
      expect(updatedTandem.timezone).toBe('UTC');

      await page.goto('/');
      await expect(page.getByRole('heading', { name: 'Your shared story, lately.' })).toBeVisible();
      await page.locator('.top-tandem-switcher').click();
      await page.getByRole('menuitem', { name: /All Tandems/ }).click();
      await expect(page.locator('.context-kicker')).toHaveText('All Tandems');
      await page.locator('.top-tandem-switcher').click();
      await page.getByRole('menuitem', { name: renamed }).click();
      await expect(page.locator('.context-kicker')).toHaveText(renamed);
      await page.getByRole('link', { name: 'Memories' }).click();
      await expect(page.getByRole('heading', { name: 'Memories' })).toBeVisible();
      const movieTitle = page.getByText(movie.title, { exact: true }).first();
      await expect(movieTitle).toBeVisible();
      await page.getByRole('button', { name: 'Gallery' }).click();
      await expect(page.getByText(movie.title, { exact: true }).first()).toBeVisible();
      await page.getByRole('link', { name: 'Calendar' }).click();
      await expect(page.getByRole('heading', { name: 'Calendar' })).toBeVisible();
      await page.getByRole('button', { name: 'Recently Deleted' }).evaluate(
        (element) => (element as HTMLButtonElement).click(),
      );
      await expect(page.getByRole('heading', { name: 'Recently Deleted' })).toBeVisible();
      await page.getByRole('link', { name: 'Memories' }).click();
      await page.getByText(movie.title, { exact: true }).first().click();
      await expect(page.getByRole('heading', { name: movie.title })).toBeVisible();
      await page.getByRole('button', { name: /Delete$/ }).click();
      await expect(page.getByRole('dialog', { name: /Move/ })).toBeVisible();
      await page.getByRole('button', { name: 'Cancel' }).click();
      await page.getByRole('button', { name: 'People & settings' }).click();
      await expect(page.getByRole('heading', { name: 'People & settings' })).toBeVisible();
      await page.getByRole('button', { name: 'Delete Tandem' }).click();
      const tandemDialog = page.getByRole('dialog', { name: `Delete ${renamed}?` });
      await expect(tandemDialog).toBeVisible();
      await expect(tandemDialog.getByRole('button', { name: 'Delete Tandem' })).toBeDisabled();
      await page.getByRole('button', { name: 'Cancel' }).click();

      await browserJson(page, 'DELETE', `/api/tandems/${tandem.id}/memories/${activity.id}?expected_version=1`, 204);
      const deletedList = await json(await request.get(`/api/tandems/${tandem.id}/memories/deleted`), 200);
      expect(deletedList.items.map((item: { id: string }) => item.id)).toContain(activity.id);
      const restoredActivity = await browserJson(page, 'POST', `/api/tandems/${tandem.id}/memories/${activity.id}/restore`, 200);
      expect(restoredActivity.id).toBe(activity.id);
      await browserJson(page, 'DELETE', `/api/tandems/${tandem.id}/memories/${activity.id}?expected_version=${restoredActivity.version}`, 204);
      await browserJson(page, 'DELETE', `/api/tandems/${tandem.id}/memories/${activity.id}/permanent`, 204);

      await page.getByRole('button', { name: 'People & settings' }).click();
      await page.getByRole('button', { name: 'Delete Tandem' }).click();
      const finalTandemDialog = page.getByRole('dialog', { name: `Delete ${renamed}?` });
      await finalTandemDialog.locator('input').fill(renamed);
      await finalTandemDialog.getByRole('button', { name: 'Delete Tandem' }).click();
      await expect.poll(async () => (await request.get(`/api/tandems/${tandem.id}`)).status()).toBe(404);
      createdTandems.splice(createdTandems.indexOf(tandem.id), 1);
    } finally {
      if (originalPreferences) {
        await browserApi(page, 'PATCH', '/api/me/preferences', originalPreferences).catch(() => undefined);
      }
      for (const tandemId of createdTandems.reverse()) {
        await browserApi(page, 'DELETE', `/api/tandems/${tandemId}`, { confirmation: 'DELETE' }).catch(() => undefined);
      }
    }
  });
});
