// @vitest-environment jsdom
import { createElement, type ReactElement } from 'react'
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ReactivationScreen, SettingsScreen, TandemManagement } from './App.jsx'
import { getDocumentTitle } from './lib/documentTitle'
import { tandemApi } from './lib/tandemApi'

Reflect.set(globalThis, 'IS_REACT_ACT_ENVIRONMENT', true)

function mount(element: ReactElement) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root = createRoot(container)
  act(() => root.render(element))
  return {
    container,
    unmount: () => { act(() => root.unmount()); container.remove() },
  }
}

const preferences = {
  timezone: 'UTC', notification_hour: 9,
  anniversary_notifications_enabled: true, anniversary_email_enabled: true,
}

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

describe('account and Tandem management surfaces', () => {
  it('uses privacy-safe route titles', () => {
    expect(getDocumentTitle('/', 'authenticated')).toBe('Today — Tandem')
    expect(getDocumentTitle('/timeline', 'authenticated')).toBe('Memories — Tandem')
    expect(getDocumentTitle('/memory/private-title', 'authenticated')).toBe('Memory — Tandem')
    expect(getDocumentTitle('/settings', 'authenticated')).toBe('Settings — Tandem')
    expect(getDocumentTitle('/tandem', 'authenticated')).toBe('Tandem — Settings')
    expect(getDocumentTitle('/?invite=private-ref', 'unauthenticated')).toBe('Login')
    expect(getDocumentTitle('/memory/private-title', 'authenticated')).not.toContain('private-title')
  })

  it('requires explicit destructive confirmations and exposes export/privacy settings', async () => {
    const onDeactivate = vi.fn()
    const onDelete = vi.fn()
    const view = mount(createElement(SettingsScreen, { preferences, onSave: vi.fn(), onDeactivate, onDelete } as never))
    expect(view.container.querySelector('a[href="/api/me/export"]')).not.toBeNull()
    expect(view.container.textContent).toContain('Private by default')

    const requestConfirm = vi.fn()
    const buttons = Array.from(view.container.querySelectorAll('button'))
    const deactivate = buttons.find((button) => button.textContent?.includes('Deactivate account')) as HTMLButtonElement
    act(() => deactivate.click())
    expect(requestConfirm).not.toHaveBeenCalled()
    expect(onDeactivate).not.toHaveBeenCalled()

    view.unmount()
    const confirmedView = mount(createElement(SettingsScreen, { preferences, onSave: vi.fn(), onDeactivate, onDelete, onRequestConfirm: requestConfirm } as never))
    const confirmedDeactivate = Array.from(confirmedView.container.querySelectorAll('button')).find((button) => button.textContent?.includes('Deactivate account')) as HTMLButtonElement
    act(() => confirmedDeactivate.click())
    expect(requestConfirm).toHaveBeenCalledOnce()
    await act(async () => requestConfirm.mock.calls[0][0].onConfirm())
    expect(onDeactivate).toHaveBeenCalledOnce()
    const remove = Array.from(confirmedView.container.querySelectorAll('button')).find((button) => button.textContent?.includes('Delete account')) as HTMLButtonElement
    await act(async () => remove.click())
    expect(requestConfirm).toHaveBeenCalledTimes(2)
    await act(async () => requestConfirm.mock.calls[1][0].onConfirm())
    expect(onDelete).toHaveBeenCalledOnce()
    confirmedView.unmount()
  })

  it('renders the explicit reactivation flow', async () => {
    const onReactivate = vi.fn()
    const view = mount(createElement(ReactivationScreen, { user: { display_name: 'Former member' }, onReactivate } as never))
    expect(view.container.textContent).toContain('memberships that still exist and your shared history will return')
    await act(async () => (view.container.querySelector('button') as HTMLButtonElement).click())
    expect(onReactivate).toHaveBeenCalledOnce()
    view.unmount()
  })

  it('covers owner management actions, invite history, and the solo-history warning', async () => {
    const invitations = vi.spyOn(tandemApi, 'invitations').mockResolvedValue([
      { id: 'invite-1', tandem_id: 'tandem-1', tandem_name: 'Sunday table', invited_email: 'person@example.test', status: 'PENDING', expires_at: '2026-09-11T00:00:00Z' },
    ])
    const createInvitation = vi.spyOn(tandemApi, 'createInvitation').mockResolvedValue({ reference: 'fresh-ref', invited_email: 'person@example.test' })
    const promoteMember = vi.spyOn(tandemApi, 'promoteMember').mockResolvedValue({} as never)
    const removeMember = vi.spyOn(tandemApi, 'removeMember').mockResolvedValue()
    const onRefresh = vi.fn().mockResolvedValue(undefined)
    const requestConfirm = vi.fn()
    const soloView = mount(createElement(TandemManagement, {
      tandem: { id: 'tandem-1', name: 'Sunday table', timezone: 'UTC' },
      members: [{ user_id: 'owner-1', display_name: 'Owner', role: 'OWNER' }],
      memories: [{ id: 'memory-1' }], currentUser: { id: 'owner-1' }, onRefresh, onRequestConfirm: requestConfirm,
    } as never))
    await act(async () => {})
    const soloEmail = soloView.container.querySelector('input[type="email"]') as HTMLInputElement
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set?.call(soloEmail, 'person@example.test')
      soloEmail.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => (soloView.container.querySelector('.invite-form') as HTMLFormElement).dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
    expect(createInvitation).toHaveBeenCalledWith('tandem-1', 'person@example.test')
    soloView.unmount()

    const members = [
      { user_id: 'owner-1', display_name: 'Owner', role: 'OWNER' },
      { user_id: 'member-1', display_name: 'Member', role: 'MEMBER' },
    ]
    const view = mount(createElement(TandemManagement, {
      tandem: { id: 'tandem-1', name: 'Sunday table', timezone: 'UTC' }, members,
      memories: [{ id: 'memory-1' }], currentUser: { id: 'owner-1' }, onRefresh, onRequestConfirm: requestConfirm,
    } as never))
    await act(async () => {})
    expect(invitations).toHaveBeenCalledWith('tandem-1')
    expect(view.container.textContent).toContain('Invitation history')

    const email = view.container.querySelector('input[type="email"]') as HTMLInputElement
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set?.call(email, 'person@example.test')
      email.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await act(async () => (view.container.querySelector('.invite-form') as HTMLFormElement).dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })))
    expect(createInvitation).toHaveBeenCalledWith('tandem-1', 'person@example.test')
    const copyLink = Array.from(view.container.querySelectorAll('button')).find((button) => button.textContent?.includes('Copy link')) as HTMLButtonElement
    await act(async () => copyLink.click())
    expect(view.container.textContent).toContain('Invite link copied.')
    expect(copyLink.textContent).toContain('Copied')

    const makeOwner = Array.from(view.container.querySelectorAll('button')).find((button) => button.textContent?.includes('Make owner')) as HTMLButtonElement
    await act(async () => makeOwner.click())
    expect(promoteMember).toHaveBeenCalledWith('tandem-1', 'member-1')

    const remove = Array.from(view.container.querySelectorAll('button')).find((button) => button.textContent?.includes('Remove')) as HTMLButtonElement
    await act(async () => remove.click())
    expect(removeMember).not.toHaveBeenCalled()
    expect(requestConfirm).toHaveBeenCalled()
    await act(async () => requestConfirm.mock.calls.at(-1)?.[0].onConfirm())
    expect(removeMember).toHaveBeenCalledWith('tandem-1', 'member-1')
    view.unmount()
  })
})
