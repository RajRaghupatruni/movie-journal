import { describe, expect, it } from 'vitest'
import { resolveMemoryTimezone } from './memoryDefaults'

describe('memory timezone defaults', () => {
  it('prefers the selected Tandem timezone', () => {
    expect(resolveMemoryTimezone({ tandemTimezone: 'America/Chicago', userTimezone: 'UTC', browserTimezone: 'Europe/London' })).toBe('America/Chicago')
  })

  it('falls back through user, browser, and finally UTC', () => {
    expect(resolveMemoryTimezone({ userTimezone: 'Europe/London', browserTimezone: 'Asia/Tokyo' })).toBe('Europe/London')
    expect(resolveMemoryTimezone({ browserTimezone: 'Asia/Tokyo' })).toBe('Asia/Tokyo')
    expect(resolveMemoryTimezone()).toBe('UTC')
  })
})
