import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, tandemApi } from './tandemApi'

afterEach(() => vi.restoreAllMocks())

describe('tandem API client', () => {
  it('sends session cookies and server-side filters', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ items: [] }), { status: 200 }))
    await tandemApi.memories('tandem-1', { q: 'blue door', category: 'custom', year: 2024, limit: 20 })
    expect(fetchMock).toHaveBeenCalledWith('/api/tandems/tandem-1/memories?q=blue+door&category=custom&year=2024&limit=20', expect.objectContaining({ credentials: 'include' }))
  })

  it('preserves 409 details for the edit conflict surface', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: { message: 'changed', current_version: 3 } }), { status: 409 }))
    await expect(tandemApi.updateMemory('tandem-1', 'memory-1', { expected_version: 2, title: 'new' })).rejects.toEqual(expect.objectContaining({ status: 409, detail: { message: 'changed', current_version: 3 } }))
    expect(ApiError).toBeDefined()
  })
})
