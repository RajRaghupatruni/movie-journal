export function validateMemoryDraft(draft: { title: string; timezone: string; rating: string | number | null; tags: string[] }) {
  const errors: string[] = []
  if (!draft.title.trim()) errors.push('Give this memory a title.')
  if (!draft.timezone.trim()) errors.push('Add an IANA timezone, such as America/Chicago.')
  const rating = draft.rating === '' || draft.rating === null ? null : Number(draft.rating)
  if (rating !== null && (!Number.isInteger(rating) || rating < 1 || rating > 10)) errors.push('Rating must be a whole number from 1 to 10.')
  const normalizedTags = draft.tags.map((tag) => tag.trim().toLocaleLowerCase()).filter(Boolean)
  if (new Set(normalizedTags).size !== normalizedTags.length) errors.push('Tags must be unique.')
  if (normalizedTags.length > 20) errors.push('Use 20 tags or fewer.')
  return errors
}
