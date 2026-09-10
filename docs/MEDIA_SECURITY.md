# Private media security

Photos are uploaded to FastAPI, validated and normalized, then written to private S3-compatible
object storage. Tandem stores only object metadata in PostgreSQL; it does not use the container
filesystem or put binary data in database columns. The adapter works with Backblaze B2 and other
S3-compatible services. Set `S3_ENDPOINT_URL` for B2-compatible endpoints or MinIO, alongside
`S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, and optional `S3_REGION`.

## Upload policy

- JPEG, PNG, and WebP only; the declared MIME type is checked and Pillow must successfully decode
  the actual bytes. Filename extensions are not trusted.
- Raw uploads are limited to 10 MiB per file and 10 photos per memory.
- Images are EXIF-auto-oriented, converted to RGB, resized so neither dimension exceeds 2,400
  pixels, and re-encoded as WebP at quality 85. Re-encoding strips unnecessary EXIF metadata.
- Object keys are opaque UUID-based keys under the tandem/memory prefix. User filenames are kept
  only as sanitized display metadata and are never keys.

## Reads and deletion

Every media endpoint first applies the existing authenticated Tandem membership dependency and
queries by both the nested memory and Tandem IDs. A member receives a short-lived (five minute)
presigned read URL; URLs are never permanent or public. PostgreSQL `memory_media` has RLS and
`FORCE ROW LEVEL SECURITY` with policies derived from the Tandem membership function.

Deleting one photo removes the object before its metadata. Deleting a memory attempts to delete
all associated objects before committing the cascading metadata deletion. If storage is
unavailable, metadata is retained and the API reports a retryable error. Batch-upload failures
best-effort clean up objects already written and never commit partial metadata; cleanup failures
are logged as orphan-cleanup failures for operator follow-up. No background queue is required
for the current 10–20-user target.

The frontend lazy-loads photo thumbnails and uses the first photo as the Timeline/Calendar
thumbnail. Storage credentials stay backend-only and are never included in API responses.
