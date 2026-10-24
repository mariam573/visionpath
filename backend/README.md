# VisionPath backend foundation

This service is a protected account-profile and consent-record foundation. It is not a production deployment. It has no SQLite fallback, password store, public account-registration endpoint, or client-selected role assignment. The identity provider owns credential signup; `GET /users/me` only provisions the authenticated subject's profile. Scene questions, navigation questions, audio upload/transcription, synchronization, and sharing handlers are absent from the active backend; no provider credentials or upload dependencies are configured.

## Runtime requirements

- PostgreSQL with the schema at the current Alembic migration head.
- An OIDC managed identity provider that issues signed `RS256` **access tokens** for the VisionPath API and publishes a JWKS endpoint.
- A reviewed privacy/consent policy version matching the version presented in the client.

Set these values in `.env` (copy `.env.example` first):

```dotenv
DATABASE_URL=postgresql+psycopg://visionpath:...@127.0.0.1:5432/visionpath
OIDC_ISSUER=https://identity.example/tenant/v2.0
OIDC_JWKS_URL=https://identity.example/tenant/discovery/v2.0/keys
OIDC_AUDIENCE=api://visionpath
CONSENT_POLICY_VERSION=reviewed-policy-version
```

The identity provider URLs and audience are placeholders: choose and configure the project's actual provider. The API checks the access token's signature against cached JWKS keys, issuer, audience, expiry and required claims. It accepts only `RS256`; it never uses email as an identity key. The verified `(issuer, subject)` pair is the account identity. Only a provider-verified email claim is stored, and roles cannot be set through the profile API.

## Initialize PostgreSQL and run

From this directory:

```powershell
Copy-Item .env.example .env
# Edit .env with the real PostgreSQL and OIDC values.
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```

The service refuses startup when a configured PostgreSQL database is unreachable or behind the migration head. With missing database, OIDC, or consent-policy settings, liveness remains available at `/health`, protected API calls fail closed, and `/ready` returns 503. Runtime startup never creates or alters the schema.

## Enabled routes

All routes below require `Authorization: Bearer <OIDC access token>`.

- `GET /api/v1/users/me` creates or returns the profile associated with the verified token subject.
- `PATCH /api/v1/users/me` updates only name, phone, English/Arabic preference, and bounded accessibility preferences. Email and role are not client-editable.
- `GET /api/v1/me/consents` returns the authenticated user's latest decision per purpose.
- `PUT /api/v1/me/consents/{purpose}` records an append-only grant or revocation for `cloud_questions`, `synchronization`, or `sharing`. Grants must name the server-configured policy version. Revocation is always accepted and remains available after a policy version changes.

Consent is current only if the latest event for that user and purpose is a grant for the currently configured policy version. A service must check that condition server-side for every operation; a client boolean or an old grant is not proof of consent. The cloud question, sync, and sharing services are deliberately not implemented in the active API yet.

## Data and migration notes

`users` is keyed by a random UUID and has a unique OIDC issuer/subject pair. `consent_events` stores only the user, purpose, grant/revoke decision, policy version, generated event sequence, and timestamp. There are no scene, image, audio, transcript, or routine question-history tables. Consent events are append-only: both the API and a PostgreSQL trigger reject updates and deletes, and the foreign key prevents deleting an account while its consent audit history remains. Account retention/deletion needs a reviewed policy before implementing a separate anonymization or archival workflow.

The old SQLite prototype database was removed from the working project and was not read or migrated. It had no verified mapping to managed identity subjects, so importing it would risk assigning profiles to the wrong people. PostgreSQL is the only supported backend store; do not recreate or use SQLite data files.

## Before production or optional services

The application code does not provision an identity tenant, decide legal consent language, issue credentials, create a cloud PostgreSQL instance, or configure secret storage. Complete those environment and policy choices first. Before adding cloud questions, implement server-side current-consent enforcement, quotas, timeout/rate limits, provider data-retention review, validated fresh evidence, and output filtering that rejects movement/safety guidance. Client-supplied consent flags must never authorize processing. Before synchronization or sharing, add explicit relationship ownership, per-action authorization, revocation propagation, and retention/deletion behavior. Add audio upload/transcription only with authenticated ownership, explicit purpose-specific consent, size/type/time limits, and short-lived processing/storage. Keep database backups encrypted and test restoration and account deletion/retention procedures.
