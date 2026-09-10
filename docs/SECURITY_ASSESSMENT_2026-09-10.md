# Tandem adversarial pre-production security assessment

Assessment date: 2026-09-10
Scope: `tandem/security-hardening` only
Threat model: authenticated owner/member/outsider, former member, unauthenticated attacker,
malicious uploader, and abusive API client.

## Result

Thirty attack classes were assessed across the API, React client, PostgreSQL policies, storage
boundary, workers, production image, and deployment configuration. No P0/Critical or P1/High
application findings remain known after this pass.

The highest-priority boundary is enforced in both FastAPI and PostgreSQL: a user outside a Tandem
gets a non-enumerating 404 for Tandem, memory, media, and membership resources. Direct runtime-role
checks confirmed that RLS hides another user's Tandem rows and memory rows. Current members can
read shared memories, but only owners can manage membership/Tandem state and only owners or memory
creators can mutate memories.

## Findings and fixes

| Severity | Finding | Fix / disposition |
| --- | --- | --- |
| P2 | The old invitation SELECT policy exposed all invitation rows to any authenticated runtime session. The API still required a hashed reference, so this was not an HTTP enumeration path, but it weakened the DB boundary. | Migration `0013_security_hardening` limits rows to the inviting Tandem's members or the invitation's verified email. Wrong recipients now receive 404. |
| P2 | Sensitive mutation schemas ignored unknown JSON properties. | Explicit request models now use `extra="forbid"` for account, Tandem, invitation, preference, and memory mutations. |
| P2 | Rotating client keys could grow the rate-limiter map because stale non-empty buckets were not evicted. | The map is actively bounded at 4096 buckets. |
| P2 | A validly declared image with absurd dimensions could reach image decoding. | Image headers are checked before verification/decoding; input is capped at 40 million pixels and output is still normalized to WebP. |
| P2 | Private API GET responses had no universal cache directive; CSP also included an unnecessary wildcard B2 host. | `/api/*` and `/auth/*` responses are `no-store`; CSP allows only the configured object-storage host. |
| P2 | Notification internals and unused member/media identity fields crossed the API boundary. | Removed notification dedupe/recipient internals and unused member email/avatar and media filename/creator fields from response schemas; account exports no longer include other participants' email addresses. |
| P1 | Vulnerable dependency pins were found by `pip-audit`: Pillow 12.0.0 and python-multipart 0.0.20. | Updated to Pillow 12.3.0 and python-multipart 0.0.31; the follow-up audit reports no known vulnerabilities. |

## Areas tested

- Authentication, Google OIDC configuration, state hash/single-use/expiry/cookie binding, redirect
  handling, session hashing/expiry/logout/revocation, inactive-user behavior, and account delete.
- Tandem, memory, member, owner-role, invitation, notification, export, preference, global-view,
  and delete IDOR/BOLA paths with owner/member/outsider identities.
- Owner-only function authorization, former-member access, last-owner invariants, membership and
  capacity races, concurrent invitation acceptance, and tandem deletion ordering.
- Mass assignment/property injection, strict metadata, SQL parameterization, search/filter bounds,
  and error non-disclosure.
- CSRF with missing, foreign, malformed Origin and Referer inputs; same-origin production behavior;
  CSP, frame protection, HSTS, nosniff, referrer, permissions, and cache headers.
- Stored-XSS inputs in names, notes, tags, provider snapshots, participant names, notification
  payloads, and error paths. React escaping and the DOMPurify review boundary were inspected;
  there is no production `dangerouslySetInnerHTML` path.
- JPEG/PNG/WebP MIME mismatch, malformed bytes, size, dimensions, EXIF transpose/normalization,
  filename traversal/Unicode sanitization, opaque object keys, private signed reads, and deletion.
- Provider outbound HTTP, fixed provider base URLs, absence of arbitrary URL proxying, and SSRF
  surface. No user-controlled backend fetch URL was found.
- Notification cancellation, deep-link authorization, anniversary eligibility revalidation, email
  contents, account deletion/deactivation cleanup, and log/exception redaction.
- Runtime/migrator role split, FORCE RLS, migration head/check, Docker non-root image, Render
  configuration, dependency locks, npm audit, pip-audit, and source secret scan.

## Verification evidence

- Backend PostgreSQL suite: 60 passed, 3 intentionally deselected only because the host's global
  temp directory rejects pytest's `tmp_path` fixture. The deselected checks are environment/config
  tests, not application or database tests. The full executable integration set has zero DB skips.
- Focused security tests: 20 passed before the response-minimization changes; the full PostgreSQL
  run after those changes also passed all 60 executable tests.
- Ruff check and format check: passed.
- Alembic: `0013_security_hardening` is head; `alembic check` reports no new operations.
- Frontend: 24 tests passed; lint, TypeScript typecheck, and production build passed.
- `npm audit --audit-level=high`: 0 vulnerabilities.
- `pip-audit -r backend/requirements.lock`: no known vulnerabilities after the targeted updates.
- `python scripts/scan_secrets.py`: 0 findings.
- Production Docker build: passed; image user is non-root `tandem`.
- Disposable PostgreSQL Compose validation: passed.

## Residual risks and deployment assumptions

- The rate limiter is intentionally in-process and single-instance. Multiple web instances require
  a shared limiter or an edge control; this is documented and is not a tenant authorization layer.
- OAuth callback behavior still requires a real Google client, exact production redirect URI, TLS,
  and a real-user A/B/C smoke test. No Google credential or token is included in this document.
- B2 must remain private, with bucket-restricted credentials. Signed media URLs are intentionally
  bearer URLs for five minutes; anyone holding one can read that object until expiry.
- Render's proxy source must remain within the bounded private forwarded-header ranges configured
  in the production image, or the allowlist must be changed to Render's documented private range.
- Historical credentials mentioned in repository audit history must remain revoked independently;
  this assessment does not rotate external provider credentials.
- Direct database owner/migrator access remains operationally sensitive by design. The application
  runtime role is required to be `NOSUPERUSER`, `NOBYPASSRLS`, and not the schema owner.

## Security boundary summary

FastAPI dependencies provide the first authorization layer, PostgreSQL FORCE RLS provides defense
in depth, private object storage prevents public media access, and the browser receives only opaque
session cookies and short-lived signed media URLs. The frontend never decides authorization and no
client-controlled tandem, owner, recipient, storage key, or provider credential is trusted for a
server-side security decision.
