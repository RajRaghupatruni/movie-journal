export type MemoryType = 'movie' | 'place' | 'trip' | 'activity' | 'moment' | 'custom'

export interface TandemMember {
  id: string
  name: string
  role: string
  initials: string
  color: string
  image?: string
}

export interface Memory {
  id: string
  title: string
  type: MemoryType
  date: string
  location?: string
  participants: string[]
  excerpt: string
  notes?: string
  rating?: number
  tags: string[]
  image: string
  imageAlt: string
  source?: string
}

export interface TandemSnapshot {
  tandem: {
    name: string
    memberCount: number
    memoryCount: number
    createdLabel: string
  }
  members: TandemMember[]
  memories: Memory[]
  collections: Array<{ name: string; count: number; image: string }>
}

export type DataState<T> =
  | { status: 'loading'; data: null; error: null }
  | { status: 'ready'; data: T; error: null }
  | { status: 'empty'; data: T; error: null }
  | { status: 'error'; data: null; error: string }

const photos = {
  lisbon: 'https://images.unsplash.com/photo-1555881400-74d7acaacd8b?auto=format&fit=crop&w=1400&q=85',
  coast: 'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1000&q=85',
  restaurant: 'https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?auto=format&fit=crop&w=1000&q=85',
  cabin: 'https://images.unsplash.com/photo-1449158743715-0a90ebb6d2d8?auto=format&fit=crop&w=1000&q=85',
  concert: 'https://images.unsplash.com/photo-1506157786151-b8491531f063?auto=format&fit=crop&w=1000&q=85',
  film: 'https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=1000&q=85',
  coffee: 'https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?auto=format&fit=crop&w=1000&q=85',
  garden: 'https://images.unsplash.com/photo-1497250681960-ef046c08a56e?auto=format&fit=crop&w=1000&q=85',
}

export const demoSnapshot: TandemSnapshot = {
  tandem: {
    name: 'Raj & Alex',
    memberCount: 2,
    memoryCount: 147,
    createdLabel: 'Since 2021',
  },
  members: [
    { id: 'raj', name: 'Raj Rao', role: 'Member', initials: 'RR', color: '#8f4357' },
    { id: 'alex', name: 'Alex Morgan', role: 'Member', initials: 'AM', color: '#b86d57' },
  ],
  memories: [
    {
      id: 'lisbon-lunch', title: 'A long lunch in Lisbon', type: 'place', date: '2023-09-09', location: 'Taberna da Rua das Flores',
      participants: ['Raj', 'Alex'], excerpt: 'We meant to stay for an hour. The afternoon had other plans.', notes: 'The waiter brought us the tiny almond cakes after we asked for the bill.', tags: ['summer', 'food', 'slow days'], image: photos.lisbon, imageAlt: 'Sunlit street in Lisbon', source: 'manual',
    },
    {
      id: 'coast-road', title: 'The coast road, with no plan', type: 'trip', date: '2024-08-18', location: 'Big Sur, California',
      participants: ['Raj', 'Alex'], excerpt: 'One road, two coffees, and a playlist we still can’t agree on.', tags: ['road trip', 'weekend'], image: photos.coast, imageAlt: 'Blue ocean coast',
    },
    {
      id: 'perfect-film', title: 'The perfect rainy movie', type: 'movie', date: '2025-02-14', location: 'Home',
      participants: ['Raj', 'Alex'], excerpt: 'A perfect 9/10, mostly because the power went out halfway through.', rating: 9, tags: ['movies', 'rainy day'], image: photos.film, imageAlt: 'Rows of seats in a cinema', source: 'tmdb',
    },
    {
      id: 'first-concert', title: 'Our first concert in years', type: 'activity', date: '2025-06-21', location: 'The Salt Shed',
      participants: ['Raj', 'Alex'], excerpt: 'We lost our voices, found a new favorite band, and walked home in the rain.', tags: ['music', 'summer'], image: photos.concert, imageAlt: 'Crowd at a concert',
    },
    {
      id: 'cabin-weekend', title: 'The cabin weekend', type: 'trip', date: '2025-10-04', location: 'Saugatuck, Michigan',
      participants: ['Raj', 'Alex'], excerpt: 'The kind of quiet that makes you hear yourself laughing.', tags: ['autumn', 'getaway'], image: photos.cabin, imageAlt: 'Cabin in a forest',
    },
    {
      id: 'corner-coffee', title: 'The corner coffee shop', type: 'place', date: '2026-03-12', location: 'Dayglow Coffee',
      participants: ['Raj', 'Alex'], excerpt: 'Still our favorite place to make very serious weekend plans.', tags: ['rituals', 'coffee'], image: photos.coffee, imageAlt: 'Coffee on a wooden table',
    },
    {
      id: 'new-apartment', title: 'The first night in our new place', type: 'moment', date: '2026-05-02', location: 'Chicago, Illinois',
      participants: ['Raj', 'Alex'], excerpt: 'No furniture yet. Just takeout, a borrowed lamp, and a lot of hope.', tags: ['milestones', 'home'], image: photos.garden, imageAlt: 'Green plant in a bright room',
    },
    {
      id: 'late-summer-walk', title: 'A late summer walk', type: 'activity', date: '2026-09-03', location: 'Lincoln Park',
      participants: ['Raj', 'Alex'], excerpt: 'The light stayed with us all the way home.', tags: ['today', 'walks'], image: photos.garden, imageAlt: 'Sunlit green leaves',
    },
  ],
  collections: [
    { name: 'Little rituals', count: 24, image: photos.coffee },
    { name: 'Summer, somewhere', count: 18, image: photos.coast },
    { name: 'Things we watched', count: 36, image: photos.film },
  ],
}

export const navItems = [
  { label: 'Today', path: '/', icon: 'sun' },
  { label: 'Timeline', path: '/timeline', icon: 'timeline' },
  { label: 'Explore', path: '/explore', icon: 'search' },
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

export function getAnniversaryCopy(memory?: Memory): { eyebrow: string; fallback: boolean; title: string; excerpt: string } {
  if (!memory) {
    return { eyebrow: 'A small invitation', fallback: true, title: 'Nothing happened on this date — here’s something worth remembering.', excerpt: 'Every day does not need a story. Sometimes it is enough to make room for the next one.' }
  }
  return { eyebrow: 'Three years ago today', fallback: false, title: memory.title, excerpt: memory.excerpt }
}

export function groupMemoriesByYear(memories: Memory[]): Array<{ year: string; months: Array<{ label: string; memories: Memory[] }> }> {
  const years = new Map<string, Map<string, Memory[]>>()
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

export async function loadDemoSnapshot(): Promise<DataState<TandemSnapshot>> {
  return { status: 'ready', data: demoSnapshot, error: null }
}
