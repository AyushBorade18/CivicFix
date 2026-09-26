# Backend Auth Foundation

Status as of 2026-09-26. Backend only; the frontend is not yet updated (see §12).

---

## 1. Authentication architecture

```
Browser ──(Bearer JWT from identity provider)──▶ FastAPI
   app/auth.py  verify_token: signature (JWKS), exp, iss, aud, sub
        ▼
   app/users.py get_user(sub) → CivicFix user row
        ▼
   role + ward_ids + departments (from OUR database only)
        ▼
   require_staff / ensure_issue_access / issue_scope_sql → allow or 403
```

- **Provider-neutral OIDC/JWT.** Any provider that publishes a JWKS works: Clerk, Auth0, Cognito, Keycloak, Supabase with asymmetric keys. CivicFix never stores or sees passwords.
- **The token is trusted for exactly one thing: the subject (`sub`).** Role, ward and department claims in a token are ignored (there's a test for this).
- **Asymmetric algorithms only** (`RS*`, `ES*`, `PS*`, `EdDSA`). `none` and `HS*` are refused.
- **Fails closed.** With no `AUTH_JWKS_URL`/`AUTH_ISSUER`, every authenticated endpoint returns 503. There's no bypass or "dev mode" flag in the server.
- **Library:** PyJWT 2.15 (`PyJWKClient` fetches and caches the JWKS). It accepts only `http(s)` JWKS URLs.

Why this approach: no provider was configured in the repo, and the brief ruled out custom password storage. A JWKS boundary is the least disruptive way to plug in any managed provider later: only env vars change, not code.

## 2. User model

`users` table (migration 001):

| Column | Notes |
|---|---|
| `id` | bigserial |
| `external_auth_id` | provider `sub`, `UNIQUE NOT NULL` |
| `email` | from the token at registration, dropped if the token says `email_verified: false` |
| `display_name` | from the token's `name` claim at registration |
| `role` | `CHECK` in the 4 roles, default `citizen` |
| `is_active` | deactivated users get 403 |
| `created_at`, `updated_at` | |

`user_wards(user_id, ward_id)` and `user_departments(user_id, department)` hold the scope. Both are many-to-many, cascade on user delete.

## 3. Roles

| Role | Access |
|---|---|
| `citizen` | Submit reports; read own reports (`/api/me/reports`); public API; feedback only on issues they reported into. Blocked (403) from every internal endpoint |
| `ward_officer` | Internal issue intelligence **only for assigned wards**: list, detail (priority breakdown, signals, matches, reports), map, matches; close/route in scope. Issues with no ward are not visible to ward officers |
| `department_officer` | Same internal views, scoped to **categories owned by their department(s)** across all wards |
| `system_admin` | Everything, all wards |

Works (`/api/works`) and metrics (`/api/metrics`) are staff-only but not ward-scoped. Works are published MPLADS records, and officers need neighbouring wards to judge a match.

## 4. Ward / department scope

- **Ward:** `issues.ward_id ∈ user_wards`.
- **Department:** there's no departments table. The only department concept is the fixed `AGENCY_MAP` in `app/core/routing.py`. A department officer's scope is the categories that map to their department(s), e.g. `PMC Road Department` → `pothole_road`, `footpath`. `app/users.py` rejects unknown department names.
- Enforcement is in one place with two forms that mirror each other:
  - `CurrentUser.can_access_issue()` for single-issue endpoints, via `ensure_issue_access`: 404 if the issue doesn't exist, 403 if it's out of scope.
  - `issue_scope_sql()` for lists. It's a SQL predicate, so a client-supplied `ward_id` outside scope returns nothing rather than leaking.

## 5. Public vs internal API boundary

Public responses use a **separate model** (`PublicIssue`) built field by field from `issues`. It is never derived from the internal response, so a new internal field can't leak by accident.

`PublicIssue` fields: `issue_id, category, ward_id, ward_name, status, report_count, first_reported, last_reported, closed_at, location, location_precision, is_synthetic`.

**Not exposed:** priority score or breakdown, signals, matches, report text, reporter identity, routing agency, model confidences, photo metrics.

**Location privacy:** coordinates are rounded to 3 decimals (~110 m) and labelled `approximate`; ward-centroid points are labelled `ward_level`. There's no free-text public description: the only text is citizens' raw complaints, which can contain names and phone numbers, so none is published.

Public lists sort newest-first only, never by priority, because the ranking is internal.

## 6. Report ownership

- `reports.reporter_user_id` (FK → `users`, indexed). It's set only from the authenticated user; the request body has no ownership field, and extra fields are ignored (tested).
- **Decision: authenticated-only reporting.** `POST /api/reports` and `POST /api/uploads/photo` now require a token. Anonymous reporting is removed. "My Complaints", feedback rights and abuse control all need an owner. If anonymous reporting is wanted later, it should be a separate endpoint with rate limiting, and its reports would have no owner.
- **The 402 existing synthetic reports keep `reporter_user_id = NULL`.** They predate accounts and are still labelled synthetic.
- Reports submitted by a signed-in account are stored as `is_synthetic = false`, and so is feedback. Previously every live submission was hardcoded `true`.
- **Citizens get a redacted submission response.** Same `ReportCreateResponse` shape, with `priority_score`, `priority_breakdown`, `matched_work`, `signals`, `category_confidence`, `severity`, `geom_confidence` and the photo metrics nulled out server-side. Staff get the full response.

## 7. New endpoints

| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/api/me` | token + account | `{id, role, display_name, email, ward_ids, departments}` |
| POST | `/api/me/register` | verified token, no account needed | Creates a **citizen** account (idempotent). Takes no body, so a role can't be requested |
| GET | `/api/me/reports` | token + account | Caller's own reports + each issue's public status |
| GET | `/api/me/reports/{id}` | token + account | Own report, or 404 (never reveals that another citizen's report exists) |
| GET | `/api/public/issues` | none | Paged `PublicIssue` list. Filters: `ward_id`, `category`, `status` |
| GET | `/api/public/issues/{id}` | none | One `PublicIssue` |
| GET | `/api/public/map` | none | `PublicIssue` points + ward list |

## 8. Existing endpoints: protection changes

| Endpoint | Before | Now |
|---|---|---|
| `GET /api/health`, `GET /api/stats` | open | **open** (aggregate counts only) |
| `GET /api/issues` | open | staff, scoped |
| `GET /api/issues/{id}` | open | staff, in scope |
| `POST /api/issues/{id}/close` | open | staff, in scope |
| `POST /api/issues/{id}/route` | open | staff, in scope |
| `POST /api/issues/{id}/feedback` | open | account that owns a report in that issue |
| `GET /api/matches` | open | staff, scoped |
| `GET /api/works` | open | staff |
| `GET /api/map` | open | staff, issues and matched works scoped |
| `GET /api/metrics` | open | staff |
| `POST /api/uploads/photo` | open | any account |
| `POST /api/reports` | open | any account; owner = caller |

Response shapes are unchanged except `ReportCreateResponse.category_confidence` and `.severity`, which are now `Optional` (a compatible widening, used for citizen redaction). No routes were renamed or removed.

**Frontend dependency: the current UI will get 401s.** Every page except the landing page and citizen home calls an endpoint that now needs a token, and `web/src/api/client.ts` doesn't send one. Public pages must move to `/api/public/*`. That's the first job of the frontend phase.

## 9. Database migration

- **No migration framework existed.** `schema.sql` is `CREATE ... IF NOT EXISTS` only, and earlier column additions were applied to existing databases by hand.
- Added a minimal, dependency-free runner: `python -m app.migrate` applies `migrations/*.sql` in order, once each, recording them in `schema_migrations`. Each file runs in the same transaction as its record.
- `migrations/001_auth_foundation.sql` is additive and idempotent: 3 new tables, 1 nullable column, 1 index.
- `tests/conftest.py` runs `migrate()` against `civicfix_test` at session start.
- Fresh setup: `psql -p 5433 -d civicfix -f schema.sql`, then `python -m app.migrate`.
- **Applied to the real `civicfix` database on 2026-09-26.** A backup was taken first: `backups/civicfix_before_auth_foundation.dump`, restore with `pg_restore -p 5433 -d civicfix --clean <dump>`. Counts before and after were identical: wards 58, issues 322, reports 402, works 318, matches 27, signals 41, sensitive_sites 3456, feedback 0. The comparison is saved in `backups/counts_before_auth.txt`.

## 10. Environment variables

| Variable | Required | Meaning |
|---|---|---|
| `AUTH_JWKS_URL` | yes | Provider's JWKS URL (`https://…/.well-known/jwks.json`) |
| `AUTH_ISSUER` | yes | Exact expected `iss` |
| `AUTH_AUDIENCE` | strongly recommended | Expected `aud`. If unset, audience isn't checked, which is acceptable only when the issuer is dedicated to CivicFix (e.g. a Clerk instance) |
| `AUTH_ALGORITHMS` | no | Default `RS256` |

Placeholders are in `.env.example`. No real values are committed.

Provider examples (values come from your provider dashboard):
- **Clerk:** `AUTH_ISSUER=https://<instance>.clerk.accounts.dev`, `AUTH_JWKS_URL=<issuer>/.well-known/jwks.json`.
- **Auth0:** `AUTH_ISSUER=https://<tenant>.auth0.com/` (trailing slash matters), `AUTH_JWKS_URL=<issuer>.well-known/jwks.json`, `AUTH_AUDIENCE=<API identifier>`.

## 11. Local development authentication

`scripts/dev_auth.py` is a local-only issuer. It generates an RSA keypair into `.dev_auth/`, which is gitignored and was never committed, and mints tokens. The server verifies them through the **same** JWKS path as a real provider.

```bash
python -m scripts.dev_auth init        # prints the three AUTH_* lines for .env
python -m http.server 8765 --bind 127.0.0.1 --directory .dev_auth/public   # serves only the public JWKS
TOKEN=$(python -m scripts.dev_auth token "dev|alice" --name "Alice")
curl -X POST -H "Authorization: Bearer $TOKEN" localhost:8000/api/me/register     # → citizen
python -m app.users set-role "dev|alice" ward_officer                             # promote (operator)
python -m app.users assign-ward "dev|alice" 16
```

Anyone holding `.dev_auth/private_key.pem` can mint tokens. Never point a shared or deployed server at the dev JWKS.

**First system admin:** an operator with database access runs `python -m app.users create "<provider sub>" --role system_admin` (or `set-role` after the person registers). There's no HTTP route that can grant a role.

## 12. Before production deployment

1. Create the identity-provider application and set the `AUTH_*` variables. Until then the server answers 503 on authenticated routes; it is **not** production-authenticated today.
2. Bootstrap the first `system_admin` via the CLI.
3. **Frontend:** attach the provider's token to API calls, move public pages to `/api/public/*`, call `/api/me/register` on first sign-in, and route on `/api/me`.
4. **CORS:** `app/api/main.py` allows any `localhost` origin (dev policy). Set the real frontend origin before deploying.
5. **Evidence photos:** `/uploads/*` is still served statically without auth, protected only by unguessable UUID filenames. Before production, serve photos through an authorized endpoint or signed URLs. Also, a report can reference any existing `photo_url`; uploads aren't yet bound to their uploader.
6. **Admin HTTP API** (users, roles, assignments) isn't built. The service functions exist in `app/users.py`; the future endpoints should sit behind a `system_admin` check.
7. Rate limiting on registration, report submission and uploads.
8. Audit log of officer actions (close/route): these writes don't yet record which user performed them.

## 13. Security assumptions

- The identity provider verifies email and controls sign-up. CivicFix trusts `sub` and nothing else.
- Every role and scope decision reads the database on every request. Changes (deactivation, reassignment) take effect on the next request, and tokens carry no authorization state.
- **Reviewed:**
  - **IDOR:** `/api/me/reports/{id}` is scoped by owner; issue endpoints by scope; feedback by ownership.
  - **Client-supplied role/ward/department:** ignored.
  - **SQL injection:** every f-string in SQL interpolates code constants only; all request values are bound parameters.
  - **Error details:** never include the token.
  - **Token leakage:** the uvicorn access log contained 0 tokens after the smoke test.
  - **Secrets:** none committed.
- **Found and fixed:** an unauthenticated invalid `category` on `/api/public/issues` returned a 500 (Postgres enum cast). It now returns an empty list. The staff `/api/issues` has the same pre-existing behaviour, left unchanged and now reachable only by staff.
- **Remaining known gaps:** see §12, items 4, 5, 7 and 8.

## 14. Test coverage

`tests/test_auth.py`: **37 tests** against `civicfix_test`, with real RS256 tokens verified through a JWKS served on localhost (no mocked verifier).
- **Authentication:** missing, garbage, wrong key, expired, wrong issuer, wrong audience and unsigned (`alg: none`) tokens all rejected; unknown identity → 403; inactive → 403; valid identity → role and scope from the DB; role claim in the token ignored; unconfigured server fails closed (503); registration creates a citizen and ignores a requested role.
- **Citizen:** own report readable; another citizen's → 404; `?user_id=` ignored; 8 internal endpoints → 403; no token → 401; feedback only from a reporter of the issue.
- **Ward officer:** own ward allowed; other ward → 403 on read, close and route; list scoped even when another `ward_id` is requested; can route in scope. System admin: unrestricted.
- **Department officer:** own categories across wards allowed; other categories → 403; list scoped.
- **Public:** no token needed; no internal fields; no report text; coordinates rounded; unknown category → empty list.
- **Ownership:** submission owned by the token holder even when the body names another user; response redacted for citizens; appears only in the owner's `/api/me/reports`.

`tests/test_api.py` (30 tests) still exercises the real pipeline against the real database, now as a throwaway `system_admin` account that is deleted afterwards. Full suite: **332 passed**.
