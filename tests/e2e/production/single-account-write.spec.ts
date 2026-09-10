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

function compact<T extends Record<string, unknown>>(value: T): Partial<T> {
  return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== null && item !== undefined));
}

test.describe('@write @provider @production-safe one-account V1 journey', () => {
  test.beforeEach(({ baseURL }) => assertSingleAccountWriteOptIn(baseURL));

  test('runs isolated single-user creation, providers, media, recovery, navigation, and cleanup', async ({ page, request }) => {
    const createdTandems: string[] = [];
    let originalPreferences: Record<string, unknown> | undefined;
    try {
      await json(await request.get('/api/me'), 200);
      originalPreferences = await json(await request.get('/api/me/preferences'), 200);

      const tandemName = e2eName('Tandem');
      const secondTandemName = e2eName('Second-Tandem');
      const tandem = await json(
        await request.post('/api/tandems', { data: { name: tandemName, timezone: 'America/Chicago' } }),
        201,
      );
      createdTandems.push(tandem.id);
      const secondTandem = await json(
        await request.post('/api/tandems', { data: { name: secondTandemName, timezone: 'UTC' } }),
        201,
      );
      createdTandems.push(secondTandem.id);

      const allTandems = await json(await request.get('/api/me/tandems'), 200);
      expect(allTandems.map((item: { id: string }) => item.id)).toEqual(
        expect.arrayContaining(createdTandems),
      );
      expect((await json(await request.get(`/api/tandems/${secondTandem.id}/memories`), 200)).items).toHaveLength(0);

      const date = '2024-09-10';
      const memories: Array<{ id: string; category: string }> = [];
      const createMemory = async (payload: Record<string, unknown>) => {
        const saved = await json(await request.post(`/api/tandems/${tandem.id}/memories`, { data: payload }), 201);
        memories.push(saved);
        return saved;
      };

      let custom = await createMemory({
        category: 'custom', title: e2eName('Custom-Memory'), local_date: date, timezone: 'America/Chicago',
        metadata: { label: 'single-account regression' }, tags: ['e2e', 'custom'], rating: 8,
      });
      custom = await json(await request.patch(`/api/tandems/${tandem.id}/memories/${custom.id}`, {
        data: { expected_version: custom.version, notes: 'Edited by the one-account production journey.' },
      }), 200);
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

      const placeSearch = await json(await request.get('/api/integrations/places/search?q=Chicago%20Millennium%20Park'), 200);
      expect(placeSearch.items.length).toBeGreaterThan(0);
      const place = placeSearch.items[0];
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

      const reflection = await json(
        await request.put(`/api/tandems/${tandem.id}/memories/${movieMemory.id}/reflections/me`, {
          data: { rating: 9, reaction: 'favorite', note: 'One-account production regression.' },
        }),
        200,
      );
      expect(reflection.rating).toBe(9);
      expect((await json(await request.get(`/api/tandems/${tandem.id}/memories/${movieMemory.id}`), 200)).my_reflection.note).toContain('production regression');

      const media = await json(
        await request.post(`/api/tandems/${tandem.id}/memories/${custom.id}/media`, {
          multipart: { files: { name: 'e2e.png', mimeType: 'image/png', buffer: pngBytes } },
        }),
        201,
      );
      expect(media).toHaveLength(1);
      expect((await json(await request.get(`/api/tandems/${tandem.id}/memories/${custom.id}/media`), 200))[0].url).toMatch(/^https?:\/\//);
      const signedUrl = new URL(media[0].url);
      const anonymous = await playwrightRequest.newContext();
      try {
        const rawObject = await anonymous.get(`${signedUrl.origin}${signedUrl.pathname}`);
        expect([400, 403, 404]).toContain(rawObject.status());
      } finally {
        await anonymous.dispose();
      }
      expect((await request.delete(`/api/tandems/${tandem.id}/memories/${custom.id}/media/${media[0].id}`)).status()).toBe(204);

      const tandemPreference = await json(await request.patch(`/api/tandems/${tandem.id}/preferences`, {
        data: { resurfacing_enabled: false, routine_notifications_enabled: false },
      }), 200);
      expect(tandemPreference.resurfacing_enabled).toBe(false);
      expect(tandemPreference.routine_notifications_enabled).toBe(false);
      const updatedPreferences = await json(await request.patch('/api/me/preferences', {
        data: { anniversary_notifications_enabled: false },
      }), 200);
      expect(updatedPreferences.anniversary_notifications_enabled).toBe(false);
      expect((await json(await request.get(`/api/me/on-this-day?tandem_id=${tandem.id}`), 200)).anniversaries).toEqual([]);
      expect((await json(await request.get(`/api/me/rediscovery/shuffle?tandem_id=${tandem.id}&seed=e2e`), 200)).memory).toBeNull();
      expect((await json(await request.get(`/api/me/rediscovery/year-review?year=2024&tandem_id=${tandem.id}`), 200)).memory_count).toBeGreaterThan(0);
      expect((await json(await request.get(`/api/me/rediscovery/collections?tandem_id=${tandem.id}`), 200)).items).toBeDefined();
      expect((await json(await request.get('/api/me/notifications'), 200)).items).toBeDefined();

      const renamed = e2eName('Renamed-Tandem');
      const updatedTandem = await json(await request.patch(`/api/tandems/${tandem.id}`, { data: { name: renamed, timezone: 'UTC' } }), 200);
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
      await expect(page.getByRole('button', { name: `Open memory: ${movie.title}` })).toBeVisible();
      await page.getByRole('button', { name: 'Gallery' }).click();
      await expect(page.getByText(movie.title, { exact: true }).first()).toBeVisible();
      await page.getByRole('link', { name: 'Calendar' }).click();
      await expect(page.getByRole('heading', { name: 'Calendar' })).toBeVisible();
      await page.getByRole('button', { name: 'Recently Deleted' }).click();
      await expect(page.getByRole('heading', { name: 'Recently Deleted' })).toBeVisible();
      await page.getByRole('link', { name: 'Memories' }).click();
      await page.getByRole('button', { name: `Open memory: ${movie.title}` }).click();
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

      const deleted = await request.delete(`/api/tandems/${tandem.id}/memories/${activity.id}`, { params: { expected_version: 1 } });
      expect(deleted.status()).toBe(204);
      const deletedList = await json(await request.get(`/api/tandems/${tandem.id}/memories/deleted`), 200);
      expect(deletedList.items.map((item: { id: string }) => item.id)).toContain(activity.id);
      const restoredActivity = await json(await request.post(`/api/tandems/${tandem.id}/memories/${activity.id}/restore`), 200);
      expect(restoredActivity.id).toBe(activity.id);
      expect((await request.delete(`/api/tandems/${tandem.id}/memories/${activity.id}`, { params: { expected_version: restoredActivity.version } })).status()).toBe(204);
      expect((await request.delete(`/api/tandems/${tandem.id}/memories/${activity.id}/permanent`)).status()).toBe(204);

      await page.getByRole('button', { name: 'People & settings' }).click();
      await page.getByRole('button', { name: 'Delete Tandem' }).click();
      const finalTandemDialog = page.getByRole('dialog', { name: `Delete ${renamed}?` });
      await finalTandemDialog.locator('input').fill(renamed);
      await finalTandemDialog.getByRole('button', { name: 'Delete Tandem' }).click();
      await expect.poll(async () => (await request.get(`/api/tandems/${tandem.id}`)).status()).toBe(404);
      createdTandems.splice(createdTandems.indexOf(tandem.id), 1);
    } finally {
      if (originalPreferences) {
        await request.patch('/api/me/preferences', { data: originalPreferences }).catch(() => undefined);
      }
      for (const tandemId of createdTandems.reverse()) {
        await request.delete(`/api/tandems/${tandemId}`, { data: { confirmation: 'DELETE' } }).catch(() => undefined);
      }
    }
  });
});
