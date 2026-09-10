export const MAX_PHOTO_BYTES = 10 * 1024 * 1024
export const MAX_PHOTO_COUNT = 10
export const PHOTO_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])

export function validatePhotoFiles(files: File[], existingCount = 0): string[] {
  const errors: string[] = []
  if (existingCount + files.length > MAX_PHOTO_COUNT) errors.push(`Choose at most ${MAX_PHOTO_COUNT} photos per memory.`)
  files.forEach((file) => {
    if (!PHOTO_TYPES.has(file.type)) errors.push(`${file.name} is not a JPEG, PNG, or WebP image.`)
    if (file.size > MAX_PHOTO_BYTES) errors.push(`${file.name} is larger than 10 MB.`)
  })
  return errors
}
