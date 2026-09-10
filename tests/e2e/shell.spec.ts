import { expect, test } from '@playwright/test';

test('serves the Tandem application shell', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle('Tandem');
  await expect(page.getByRole('heading', { name: 'Tandem' })).toBeVisible();
  await page.screenshot({ path: 'test-results/tandem-login-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Tandem' })).toBeVisible();
  await page.screenshot({ path: 'test-results/tandem-login-mobile.png', fullPage: true });
});
