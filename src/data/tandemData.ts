export type MemoryType = 'movie' | 'place' | 'trip' | 'activity' | 'moment' | 'custom'

export const navItems = [
  { label: 'Today', path: '/', icon: 'sun' },
  { label: 'Memories', path: '/memories', icon: 'timeline' },
  { label: 'Calendar', path: '/calendar', icon: 'calendar' },
] as const

export const memoryTypeLabels: Record<MemoryType, string> = {
  movie: 'Movie', place: 'Place', trip: 'Trip', activity: 'Activity', moment: 'Life moment', custom: 'Something else',
}

export const launcherChoices = [
  { type: 'movie' as const, label: 'Movie', note: 'Something we watched', icon: 'film' },
  { type: 'place' as const, label: 'Place', note: 'Somewhere we went', icon: 'pin' },
  { type: 'trip' as const, label: 'Trip', note: 'A day or journey away', icon: 'map' },
  { type: 'activity' as const, label: 'Activity', note: 'Something we did', icon: 'sparkles' },
  { type: 'custom' as const, label: 'Something else', note: 'Make it your own', icon: 'plus' },
]

export function getAnniversaryCopy(memory?: { title: string; excerpt: string }, yearsAgo?: number): { eyebrow: string; fallback: boolean; title: string; excerpt: string } {
  if (!memory) {
    return { eyebrow: 'A small invitation', fallback: true, title: 'Nothing happened on this date — here’s something worth remembering.', excerpt: 'Every day does not need a story. Sometimes it is enough to make room for the next one.' }
  }
  const label = yearsAgo === 1 ? 'One year ago today' : `${yearsAgo || 3} years ago today`
  return { eyebrow: label, fallback: false, title: memory.title, excerpt: memory.excerpt }
}

export function groupMemoriesByYear(memories: Array<{ date: string }>): Array<{ year: string; months: Array<{ label: string; memories: Array<{ date: string }> }> }> {
  const years = new Map<string, Map<string, Array<{ date: string }>>>()
  memories.slice().sort((a, b) => b.date.localeCompare(a.date)).forEach((memory) => {
    const date = new Date(`${memory.date}T12:00:00`)
    const year = String(date.getFullYear())
    const month = date.toLocaleDateString('en-US', { month: 'long' }).toUpperCase()
    if (!years.has(year)) years.set(year, new Map())
    const months = years.get(year)!
    if (!months.has(month)) months.set(month, [])
    months.get(month)!.push(memory)
  })
  return Array.from(years, ([year, months]) => ({ year, months: Array.from(months, ([label, grouped]) => ({ label, memories: grouped })) }))
}

export function formatMemoryDate(date: string, style: 'long' | 'short' = 'long'): string {
  return new Date(`${date}T12:00:00`).toLocaleDateString('en-US', style === 'long' ? { month: 'long', day: 'numeric', year: 'numeric' } : { month: 'short', day: 'numeric' })
}
