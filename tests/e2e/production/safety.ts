import { expect } from '@playwright/test';

export const PRODUCTION_HOST = 'tandem-web-xnih.onrender.com';

export function assertProductionOptIn(baseURL: string | undefined) {
  const live = process.env.TANDEM_LIVE_PRODUCTION === 'true';
  expect(live, 'Live production tests require TANDEM_LIVE_PRODUCTION=true').toBe(true);
  expect(new URL(baseURL || '').hostname).toBe(PRODUCTION_HOST);
}

export function e2eName(label: string) {
  const runId = process.env.TANDEM_E2E_RUN_ID || new Date().toISOString();
  return `[E2E] ${label} ${runId}`;
}
