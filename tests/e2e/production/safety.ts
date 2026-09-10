import { expect } from '@playwright/test';

export const PRODUCTION_HOST = 'tandem-web-xnih.onrender.com';

export function assertProductionOptIn(baseURL: string | undefined) {
  const live = process.env.TANDEM_LIVE_PRODUCTION === 'true';
  expect(live, 'Live production tests require TANDEM_LIVE_PRODUCTION=true').toBe(true);
  expect(new URL(baseURL || '').hostname).toBe(PRODUCTION_HOST);
}

export function assertSingleAccountWriteOptIn(baseURL: string | undefined) {
  assertProductionOptIn(baseURL);
  expect(process.env.TANDEM_LIVE_WRITE, 'Write tests require TANDEM_LIVE_WRITE=true').toBe('true');
  expect(process.env.TANDEM_E2E_NAMESPACE, 'Write tests require TANDEM_E2E_NAMESPACE').toMatch(
    /^[A-Za-z0-9][A-Za-z0-9-]{2,48}$/,
  );
  expect(process.env.TANDEM_STORAGE_STATE, 'Write tests require TANDEM_STORAGE_STATE').toBeTruthy();
}

export function e2eName(label: string) {
  const runId = process.env.TANDEM_E2E_RUN_ID || new Date().toISOString();
  const namespace = process.env.TANDEM_E2E_NAMESPACE || 'unconfigured';
  return `[E2E] ${namespace} ${label} ${runId}`;
}
