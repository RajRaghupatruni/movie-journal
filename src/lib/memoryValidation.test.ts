import { describe, expect, it } from 'vitest'
import { validateMemoryDraft } from './memoryValidation'

describe('memory draft validation', () => {
  it('requires a title and valid rating', () => {
    expect(validateMemoryDraft({ title: ' ', timezone: 'UTC', rating: 11, tags: [] })).toEqual([
      'Give this memory a title.',
      'Rating must be a whole number from 1 to 10.',
    ])
  })

  it('rejects duplicate tags before the request', () => {
    expect(validateMemoryDraft({ title: 'A day', timezone: 'UTC', rating: null, tags: ['NYC', ' nyc '] })).toContain('Tags must be unique.')
  })
})
