import { expect, test } from '@playwright/test';
import { assertProductionOptIn } from './safety';

test.describe('@smoke @read-only @production-safe live V1 smoke', () => {
  test.beforeEach(({ baseURL }) => assertProductionOptIn(baseURL));

  test('serves the deployed shell and public security boundary', async ({ page, request, baseURL }) => {
    const root = await page.goto('/');
    expect(root?.ok()).toBe(true);
    await expect(page).toHaveTitle('Login');
    await expect(page.getByRole('heading', { name: 'Keep the days you want to remember.' })).toBeVisible();
    await expect(page.getByRole('link', { name: /Continue with Google/ })).toHaveAttribute(
      'href',
      '/auth/google/login',
    );

    const health = await request.get(`${baseURL}/api/health`);
    expect(health.status()).toBe(200);
    expect(await health.json()).toEqual({ status: 'ok', application: 'ok', database: 'ok' });

    const ready = await request.get(`${baseURL}/api/readyz`);
    expect(ready.status()).toBe(200);
    expect(await ready.json()).toEqual({ status: 'ok', application: 'ok', database: 'ok' });

    const liveness = await request.get(`${baseURL}/healthz`);
    expect(liveness.status()).toBe(200);
    expect(await liveness.json()).toEqual({ status: 'ok' });

    const me = await request.get(`${baseURL}/api/me`);
    expect(me.status()).toBe(401);

    const crossOriginWrite = await request.post(`${baseURL}/api/tandems`, {
      headers: { Origin: 'https://evil.example', 'Content-Type': 'application/json' },
      data: {},
    });
    expect(crossOriginWrite.status()).toBe(403);
  });

  test('OAuth entry point redirects only to Google', async ({ request, baseURL }) => {
    const response = await request.get(`${baseURL}/auth/google/login`, { maxRedirects: 0 });
    expect(response.status()).toBe(302);
    const location = response.headers().location;
    expect(location).toMatch(/^https:\/\/accounts\.google\.com\//);
    expect(location).not.toContain('client_secret');
    expect(location).not.toContain('DATABASE_URL');
  });
});
