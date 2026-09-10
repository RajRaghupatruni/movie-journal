import { describe, expect, it } from 'vitest'
import { resolveMemoryArtwork } from './memoryPresentation'

describe('memory artwork resolution', () => {
  it('retains TMDb backdrop and poster artwork after reload', () => {
    const artwork = resolveMemoryArtwork({ mediaUrl: null, posterUrl: 'poster.jpg', backdropUrl: 'backdrop.jpg', fallback: 'fallback.svg' })
    expect(artwork.image).toBe('backdrop.jpg')
    expect(artwork.posterImage).toBe('poster.jpg')
    expect(artwork.backdropImage).toBe('backdrop.jpg')
  })

  it('prefers authorized uploads and then falls back safely', () => {
    expect(resolveMemoryArtwork({ mediaUrl: 'private-photo.jpg', posterUrl: 'poster.jpg', fallback: 'fallback.svg' }).image).toBe('private-photo.jpg')
    expect(resolveMemoryArtwork({ fallback: 'fallback.svg' }).image).toBe('fallback.svg')
  })
})
