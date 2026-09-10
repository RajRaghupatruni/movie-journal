import { defineConfig } from '@playwright/test';

const baseURL = process.env.TANDEM_E2E_BASE_URL || 'http://127.0.0.1:4173';
const liveProduction = process.env.TANDEM_LIVE_PRODUCTION === 'true';
const expectedHost = 'tandem-web-xnih.onrender.com';
const hostname = new URL(baseURL).hostname;

if (liveProduction && hostname !== expectedHost) {
  throw new Error(`TANDEM_LIVE_PRODUCTION requires ${expectedHost}; received ${hostname}`);
}

if (!liveProduction && hostname === expectedHost) {
  throw new Error('Production hostname requires TANDEM_LIVE_PRODUCTION=true');
}

const runId = process.env.TANDEM_E2E_RUN_ID || new Date().toISOString().replace(/[:.]/g, '-');

export default defineConfig({
  testDir: './tests/e2e/production',
  fullyParallel: false,
  forbidOnly: true,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  outputDir: `test-results/live/${runId}`,
  use: {
    baseURL,
    storageState: process.env.TANDEM_STORAGE_STATE || undefined,
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    navigationTimeout: 45_000,
    actionTimeout: 15_000,
  },
  webServer: liveProduction
    ? undefined
    : {
        command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 4173',
        url: 'http://127.0.0.1:4173',
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
