import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AddMemoryLauncher, AnniversaryHero, AvatarStack, Sidebar } from './components.jsx'
import { demoSnapshot, getAnniversaryCopy, groupMemoriesByYear, launcherChoices, navItems } from '../../data/tandemData'
import { formatParticipantNames } from './presentation'

describe('Tandem presentation contracts', () => {
  it('exposes the desktop navigation in the intended order', () => {
    expect(navItems.map((item) => item.label)).toEqual(['Today', 'Timeline', 'Explore', 'Calendar'])
    const markup = renderToStaticMarkup(createElement(Sidebar, { path: '/', onNavigate: () => {}, onAddMemory: () => {} }))
    expect(markup).toContain('aria-current="page"')
    expect(markup).toContain('Add memory')
  })

  it('supports anniversary and warm fallback copy states', () => {
    expect(getAnniversaryCopy(demoSnapshot.memories[0]).fallback).toBe(false)
    expect(getAnniversaryCopy(undefined).title).toContain('Nothing happened on this date')
    const markup = renderToStaticMarkup(createElement(AnniversaryHero, { memory: undefined, copy: getAnniversaryCopy(), onOpen: () => {}, onAddMemory: () => {} }))
    expect(markup).toContain('here’s something worth remembering')
    expect(markup).toContain('Add a memory')
  })

  it('groups timeline memories by year and month', () => {
    const groups = groupMemoriesByYear(demoSnapshot.memories)
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
})
