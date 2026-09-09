import { expect, test } from '@playwright/test';

test('serves the Tandem application shell', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle('Tandem');
  await expect(page.getByRole('heading', { name: 'Tandem' })).toBeVisible();
});
