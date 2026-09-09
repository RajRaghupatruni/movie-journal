import { expect, it, vi } from 'vitest';
import { legacyProviderRequest, legacyProviderSearchEnabled } from './legacyProviders';

it('cannot issue unauthenticated provider requests or expose browser credentials', async () => {
  const fetchSpy = vi.spyOn(globalThis, 'fetch');
  expect(legacyProviderSearchEnabled).toBe(false);
  await expect(legacyProviderRequest('/search/movie')).rejects.toThrow('temporarily unavailable');
  expect(fetchSpy).not.toHaveBeenCalled();
  fetchSpy.mockRestore();
});
