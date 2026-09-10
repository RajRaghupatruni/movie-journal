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

  it('covers the P0 lifecycle, notification, global-view, and invitation API actions', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, options = {}) => {
      const method = options.method || 'GET'
      return new Response(method === 'GET' ? JSON.stringify({ items: [], unread_count: 0 }) : null, { status: method === 'GET' ? 200 : 204, headers: { 'Content-Type': 'application/json' } })
    })
    await tandemApi.globalMemories({ tandem_id: undefined, from_date: '2026-01-01', to_date: '2026-12-31' } as never)
    await tandemApi.globalToday()
    await tandemApi.notifications()
    await tandemApi.markNotificationRead('notice-1')
    await tandemApi.markAllNotificationsRead()
    await tandemApi.promoteMember('tandem-1', 'member-1')
    await tandemApi.demoteMember('tandem-1', 'member-1')
    await tandemApi.removeMember('tandem-1', 'member-1')
    await tandemApi.leaveTandem('tandem-1')
    await tandemApi.deactivateAccount()
    await tandemApi.reactivateAccount()
    await tandemApi.deleteAccount()
    await tandemApi.invitations('tandem-1')
    await tandemApi.createInvitation('tandem-1', 'person@example.test')
    await tandemApi.revokeInvitation('tandem-1', 'invite-1')
    await tandemApi.resendInvitation('tandem-1', 'invite-1')
    const paths = fetchMock.mock.calls.map(([input]) => String(input))
    expect(paths).toEqual(expect.arrayContaining([
      '/api/me/memories?from_date=2026-01-01&to_date=2026-12-31',
      '/api/me/on-this-day',
      '/api/me/notifications?limit=50',
      '/api/me/notifications/notice-1/read',
      '/api/me/notifications/read-all',
      '/api/tandems/tandem-1/members/member-1/promote',
      '/api/tandems/tandem-1/members/member-1/demote',
      '/api/tandems/tandem-1/members/member-1',
      '/api/tandems/tandem-1/leave',
      '/api/me/deactivate',
      '/api/me/reactivate',
      '/api/me/delete',
      '/api/tandems/tandem-1/invitations',
      '/api/tandems/tandem-1/invitations/invite-1/revoke',
      '/api/tandems/tandem-1/invitations/invite-1/resend',
    ]))
  })
})
