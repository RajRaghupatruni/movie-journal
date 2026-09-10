# Tandem security model

This milestone establishes the security boundary for Tandem's invite-only application. The
legacy Firebase UI remains in place, but these backend tables and endpoints do not trust its
client-side state or any user-supplied tandem identifier.

## Authentication and sessions

Google is the identity provider. Authlib's OAuth 2.0/OpenID Connect client uses Google's
discovery document and requests `openid email profile`. The callback accepts only a verified
Google subject and verified email. The Google subject is the stable provider identity; the
email is normalized and used to bind invitations.

The backend does not persist Google access or ID tokens. After a successful callback it creates
a cryptographically random opaque session token, stores only its SHA-256 hash in PostgreSQL,
and sends the raw token in a bounded, HttpOnly cookie. Production cookies are Secure and
SameSite=Lax. Logout deletes the server-side session and expires the cookie. Expired or
unknown tokens receive 401 responses.

OAuth state is also cryptographically random, stored only as a hash with a short expiry, and
bound to an HttpOnly state cookie. The callback requires an exact query/cookie match and an
unconsumed database record. State records are single-use. Real Google credentials are not
needed by tests: tests create users and sessions directly through helpers under `backend/tests`.
Those helpers are not imported by the application and therefore cannot become a production
authentication bypass.

## Tandem tenant boundary

`users` are real database identities. A tandem creator receives its only initial `OWNER`
membership in the same transaction. Members have either `OWNER` or `MEMBER` role. Owners may
update a tandem and invite/remove ordinary members; ordinary members can read tandem data and
leave. The final owner cannot leave, and ownership transfer or tandem deletion must exist
before that invariant can be relaxed.

Every private route uses centralized FastAPI dependencies: `get_current_user`,
`require_tandem_member`, and `require_tandem_owner`. A missing membership is intentionally
reported as 404 for tandem resources to avoid confirming guessed UUIDs; a member attempting an
owner operation receives 403. Frontend route hiding is never an authorization decision.

## Invitation security

Invitation references are URL-safe random values. PostgreSQL stores only their hash. An
invitation has an explicit status, expiry, optional accepting user, and response timestamp.
Only one pending, unexpired invitation for a tandem/email pair is allowed by the service; an
expired pending invitation is closed before a replacement is created. Acceptance and membership
creation happen in one transaction, and the invitation is then marked accepted. A second use,
expired invitation, wrong email, declined invitation, and revoked invitation cannot create a
membership. Acceptance always compares the authenticated, normalized email with the intended
email, so possession of a reference cannot authorize arbitrary self-membership.

Invitation responses never expose `token_hash`. The raw reference is returned only when an
owner creates the invitation, for delivery by a later email service.

## PostgreSQL RLS and runtime identity

FastAPI checks are the first authorization layer. PostgreSQL RLS is defense in depth on
`tandems`, `tandem_members`, `invitations`, and every memory-domain table: `memories`,
`memory_participants`, `tags`, `memory_tags`, and `activity_events`. Policies use trusted
`SECURITY DEFINER`
membership predicates to avoid recursive policy queries and `FORCE ROW LEVEL SECURITY` so
even table owners are subject to these policies. RLS permits a pending invitee to inspect the
invited tandem/invitation just enough to complete the accept/decline flow.

At the start of an authenticated request, the backend executes a parameterized
`set_config('app.current_user_id', <uuid>, true)`. The `true` makes the setting transaction
local. The request session dependency rolls back and closes its SQLAlchemy session, and every
explicit commit ends the local setting. Routes that query again after a commit re-establish the
identity. This is important with pooled connections: an identity is never stored as a process
global or connection-persistent setting.

The API runtime role must be a login role with `NOSUPERUSER` and `NOBYPASSRLS`. A separate
migration/owner role owns schema objects and runs Alembic. Local Compose provisions this split
on a fresh PostgreSQL volume; an existing volume must be recreated or provisioned explicitly.
The runtime role receives only application table/function privileges. A superuser or a role with
`BYPASSRLS` is not a valid production runtime configuration, even though a simple disposable
test database may use one for migrations.

## Threats considered and limits

This design addresses guessed tandem IDs, arbitrary self-membership, invitation replay,
wrong-recipient acceptance, stale sessions, OAuth state replay, token disclosure in the
database, connection-pool identity leakage, and accidental omission of an application-level
tenant filter. It does not replace TLS termination, Google Console account policy, secret
rotation, rate limiting, email delivery controls, or operational database backups. CSRF risk is
reduced by HttpOnly SameSite cookies and same-origin deployment; state-changing browser clients
should also send an allowed Origin and a later frontend milestone should add a dedicated CSRF
token/header contract before cross-site embedding is considered.
