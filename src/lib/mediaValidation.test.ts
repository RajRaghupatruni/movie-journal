import { describe, expect, it } from 'vitest'
import { MAX_PHOTO_COUNT, MAX_PHOTO_BYTES, validatePhotoFiles } from './mediaValidation'

function file(name: string, type: string, size: number) {
  return new File([new Uint8Array(size)], name, { type })
}

describe('photo upload validation', () => {
  it('accepts supported image MIME types within the raw limit', () => {
    expect(validatePhotoFiles([file('memory.webp', 'image/webp', 1024)])).toEqual([])
  })

  it('rejects unsupported MIME types, oversized files, and too many photos', () => {
    expect(validatePhotoFiles([file('bad.svg', 'image/svg+xml', 1024)])).toHaveLength(1)
    expect(validatePhotoFiles([file('large.jpg', 'image/jpeg', MAX_PHOTO_BYTES + 1)])).toHaveLength(1)
    expect(validatePhotoFiles(Array.from({ length: MAX_PHOTO_COUNT + 1 }, (_, i) => file(`${i}.jpg`, 'image/jpeg', 10)))).toHaveLength(1)
  })
})
