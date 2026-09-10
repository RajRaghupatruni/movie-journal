// @vitest-environment jsdom
import { createElement, type ReactElement } from 'react'
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import { AddMemoryLauncher, AnniversaryHero, AvatarStack, CalendarPanel, MemoryDetail, NotificationBell, Sidebar, TandemSwitcher } from './components.jsx'
import { getAnniversaryCopy, groupMemoriesByYear, launcherChoices, navItems } from '../../data/tandemData'
import { formatParticipantNames } from './presentation'
import { MovieSearchPicker } from './ProviderSearch'

describe('Tandem presentation contracts', () => {
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

  const sampleMemories = [
    { date: '2023-09-09' },
    { date: '2024-08-18' },
    { date: '2026-09-03' },
  ]

  it('exposes the desktop navigation in the intended order', () => {
    expect(navItems.map((item) => item.label)).toEqual(['Today', 'Memories', 'Calendar'])
    const markup = renderToStaticMarkup(createElement(Sidebar, { path: '/', onNavigate: () => {}, onAddMemory: () => {} }))
    expect(markup).toContain('aria-current="page"')
    expect(markup).toContain('Add memory')
  })

  it('supports anniversary and warm fallback copy states', () => {
    expect(getAnniversaryCopy({ title: 'A memory', excerpt: 'A detail worth keeping.' }).fallback).toBe(false)
    expect(getAnniversaryCopy(undefined).title).toContain('Nothing happened on this date')
    const markup = renderToStaticMarkup(createElement(AnniversaryHero, { memory: undefined, copy: getAnniversaryCopy(), onOpen: () => {}, onAddMemory: () => {} }))
    expect(markup).toContain('here’s something worth remembering')
    expect(markup).toContain('Add a memory')
  })

  it('groups timeline memories by year and month', () => {
    const groups = groupMemoriesByYear(sampleMemories)
    expect(groups[0].year).toBe('2026')
    expect(groups[0].months[0].label).toBe('SEPTEMBER')
    expect(groups.some((group) => group.year === '2023')).toBe(true)
  })

  it('keeps add-memory choices discoverable and keyboard-safe', () => {
    expect(launcherChoices.map((choice) => choice.label)).toEqual(['Movie', 'Place', 'Trip', 'Activity', 'Something else'])
    const markup = renderToStaticMarkup(createElement(AddMemoryLauncher, { open: true, onClose: () => {}, onChoose: () => {} }))
    expect(markup).toContain('role="dialog"')
    expect(markup).toContain('aria-modal="true"')
    expect(markup).toContain('What are we remembering?')
  })

  it('renders a compact selected TMDb card with a visible change action', () => {
    const markup = renderToStaticMarkup(createElement(MovieSearchPicker, { selected: { title: 'Inception', release_year: 2010, poster_url: 'https://image.tmdb.org/t/p/w92/poster.jpg' }, onSelect: vi.fn() } as never))
    expect(markup).toContain('selected-provider')
    expect(markup).toContain('Change')
    expect(markup).toContain('poster.jpg')
  })

  it('renders any one-to-five member participant stack', () => {
    const members = Array.from({ length: 5 }, (_, index) => ({
      id: `member-${index}`,
      name: `Member ${index + 1}`,
      initials: `M${index + 1}`,
      color: '#8f4357',
    }))
    const markup = renderToStaticMarkup(createElement(AvatarStack, { members, size: 'large' }))
    expect(markup).toContain('Member 1, Member 2, Member 3, Member 4, and Member 5')
    expect((markup.match(/class="avatar"/g) || []).length).toBe(5)
    expect(formatParticipantNames([])).toBe('No participants selected')
    expect(formatParticipantNames(['Member 1'])).toBe('Member 1')
    expect(formatParticipantNames(['Member 1', 'Member 2'])).toBe('Member 1 and Member 2')
  })

  it('switches Tandems and closes the menu after selection', () => {
    const onSelect = vi.fn()
    const view = mount(createElement(TandemSwitcher, {
      tandems: [{ id: 'one', name: 'Sunday table' }, { id: 'two', name: 'Cousins' }],
      selectedId: 'one', selectedName: 'Sunday table', onSelect, onCreate: vi.fn(),
    } as never))
    act(() => (view.container.querySelector('.top-tandem-switcher') as HTMLButtonElement).click())
    expect(view.container.querySelector('[role="menu"]')).not.toBeNull()
    const option = Array.from(view.container.querySelectorAll('[role="menuitem"]')).find((item) => item.textContent?.includes('Cousins')) as HTMLButtonElement
    act(() => option.click())
    expect(onSelect).toHaveBeenCalledWith('two')
    expect(view.container.querySelector('[role="menu"]')).toBeNull()
    view.unmount()
  })

  it('keeps an explicit global scope and scoped management navigation', () => {
    const onSelectTandem = vi.fn()
    const globalMarkup = renderToStaticMarkup(createElement(Sidebar, { path: '/', onNavigate: vi.fn(), onAddMemory: vi.fn(), tandems: [{ id: 'one', name: 'Sunday table' }], onSelectTandem } as never))
    expect(globalMarkup).toContain('All Tandems')
    expect(globalMarkup).not.toContain('People &amp; settings')
    const scopedMarkup = renderToStaticMarkup(createElement(Sidebar, { path: '/tandem', onNavigate: vi.fn(), onAddMemory: vi.fn(), tandems: [{ id: 'one', name: 'Sunday table' }], selectedTandemId: 'one', tandemName: 'Sunday table', onSelectTandem } as never))
    expect(scopedMarkup).toContain('People &amp; settings')
  })

  it('handles notification drawer read, read-all, and memory actions', () => {
    const onRead = vi.fn()
    const onReadAll = vi.fn()
    const onOpenMemory = vi.fn()
    const item = { id: 'notice-1', type: 'memory_added', actor_name: 'Alex', tandem_name: 'Sunday table', memory_id: 'memory-1', created_at: '2026-09-10T12:00:00Z', read_at: null }
    const view = mount(createElement(NotificationBell, { notifications: [item], unreadCount: 1, open: true, onToggle: vi.fn(), onRead, onReadAll, onOpenMemory } as never))
    expect(view.container.querySelector('.notification-bell')?.getAttribute('aria-label')).toContain('1 unread')
    act(() => (view.container.querySelector('.notification-item') as HTMLButtonElement).click())
    expect(onRead).toHaveBeenCalledWith(item)
    expect(onOpenMemory).toHaveBeenCalledWith(item)
    act(() => (view.container.querySelector('.notification-drawer-head .text-action') as HTMLButtonElement).click())
    expect(onReadAll).toHaveBeenCalledOnce()
    view.unmount()
  })

  it('shows global Calendar Tandem labels and permission-aware memory controls', () => {
    const memories = [
      { id: 'one', date: '2026-09-10', tandemName: 'Sunday table', title: 'Dinner', image: '/one.jpg', imageAlt: 'Dinner', excerpt: 'A quiet meal', type: 'custom', location: '', participants: [], tags: [] },
      { id: 'two', date: '2026-09-10', tandemName: 'Cousins', title: 'Walk', image: '/two.jpg', imageAlt: 'Walk', excerpt: 'A long walk', type: 'custom', location: '', participants: [], tags: [] },
    ]
    const panel = renderToStaticMarkup(createElement(CalendarPanel, { memories, onOpen: vi.fn() } as never))
    expect(panel).toContain('2 memories across your Tandems')
    expect(panel).toContain('Sunday table')
    expect(panel).toContain('Cousins')
    const detail = { ...memories[0], notes: '', rating: null, createdByName: 'Alex', media: [] }
    expect(renderToStaticMarkup(createElement(MemoryDetail, { memory: detail, canManage: false, onBack: vi.fn(), onAddMemory: vi.fn(), onEdit: vi.fn(), onDelete: vi.fn() } as never))).not.toContain('>Edit<')
    expect(renderToStaticMarkup(createElement(MemoryDetail, { memory: detail, canManage: true, onBack: vi.fn(), onAddMemory: vi.fn(), onEdit: vi.fn(), onDelete: vi.fn() } as never))).toContain('>Edit<')
  })
})
