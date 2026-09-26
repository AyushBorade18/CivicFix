# Frontend Product Audit

Audit date: 2026-09-26. Read-only: nothing was changed to produce this.
Sources: `app/api/main.py`, `app/api/schemas.py`, `schema.sql`, `app/core/*`,
`web/src/**`, and the live `civicfix` database (port 5433).

---

## 1. Current frontend architecture

| Aspect | Current state |
|---|---|
| Stack | React 19, Vite 8, TypeScript 6, react-router-dom 7, Tailwind 4, Leaflet + react-leaflet + markercluster, lucide-react |
| Entry | `web/src/main.tsx` → `App.tsx` (single `BrowserRouter`, all routes in one file) |
| API layer | `web/src/api/client.ts` (one `request()` wrapper, typed `api.*` object) + `web/src/api/types.ts` (mirrors `schemas.py` by hand) |
| Data fetching | `web/src/hooks/useApi.ts`: a small hook returning `{data, loading, error, reload}`. No cache, no dedup between pages |
| Layouts | `citizen/CitizenLayout.tsx`, `admin/AdminLayout.tsx`, shared `components/Header.tsx` and `Footer.tsx` |
| Shared components | `Badges`, `EvidenceChain`, `PriorityBreakdown`, `States` (loading/error/empty), `WardMap`, `ui/GlowingCard`, `ui/GlowingEffect` |
| Styling | `styles/tokens.css` (design tokens), `styles/global.css`, plus one CSS file per page |
| Other | `hooks/useSpeechRecognition.ts` (voice input on the report form) |
| Size | ~6,200 lines across 40 files |

**Architectural observations**
- The citizen/admin split is a **route boundary, not a security boundary**: both layouts call the same unauthenticated API.
- The API client is clean and single-sourced, so there's no duplicate API logic to remove.
- `types.ts` is hand-maintained. It can drift from `schemas.py`; FastAPI already serves `/openapi.json` that types could be generated from.
- `ui/GlowingEffect.tsx` uses multi-colour conic gradients (blue/violet/green/cyan). That clashes with the requested design direction ("no generic AI gradients").

---

## 2. Existing frontend routes

| Route | Page | API calls | Notes |
|---|---|---|---|
| `/` | `pages/Landing.tsx` | `stats` | Hardcoded copy: "60,000+ government public works records" (see §7) |
| `/citizen` | `citizen/pages/Home.tsx` | `stats` | Copy promises "computed priority scores" to citizens |
| `/citizen/report` | `citizen/pages/ReportIssue.tsx` | `map`, `uploadPhoto`, `createReport` | Text, ward, photo, voice input. Shows the category/severity outcome after submitting |
| `/citizen/issues` | `citizen/pages/PublicIssues.tsx` | `map`, `listIssues(sort=recent)` | Public list + map |
| `/citizen/issues/:id` | `citizen/pages/PublicIssueDetail.tsx` | `issueDetail`, `submitFeedback` | Uses the **full internal** issue endpoint; shows the verification signal count |
| `/admin` | `admin/pages/Overview.tsx` | `stats`, `map`, `listIssues(ward_id)` | Ward filter |
| `/admin/issues` | `admin/pages/IssueExplorer.tsx` | `map`, `listIssues`, `listMatches` | Filter by ward/category/status/min priority; sort by priority/recent |
| `/admin/issues/:id` | `admin/pages/IssueDetail.tsx` | `issueDetail`, `closeIssue`, `routeIssue` | Priority breakdown, evidence chain, matches, signals |
| `/admin/map` | `admin/pages/MapView.tsx` | `map` | Issue points, matched works, sensitive sites |
| `/admin/works` | `admin/pages/PublicWorks.tsx` | `map`, `listWorks` | Paged, filter by ward/category |
| `/admin/verification` | `admin/pages/Verification.tsx` | `metrics`, `listMatches(500)`, then `issueDetail` **per issue** | N+1 request pattern; fine at 27 matches, won't scale |
| `*` | redirect → `/citizen` | | |

Unused client methods: `api.health` (never called).

---

## 3. Existing backend API (relevant to frontend)

All in `app/api/main.py`. **None require authentication.**

| Method | Endpoint | Returns | Frontend use |
|---|---|---|---|
| GET | `/api/health` | DB status + counts of works/reports/issues | Unused |
| GET | `/api/stats` | Row counts: wards, works, reports, issues, matches, sensitive_sites, verification_signals | Landing, Home, Overview |
| GET | `/api/metrics` | Classifier F1/baseline, clustering, location resolution, matcher rates | Verification |
| GET | `/api/issues` | Paged list. Filters: `ward_id`, `category`, `status`, `min_priority`. Sort: `priority` / `recent`. `limit ≤ 200` | Explorer, Public issues, Overview |
| GET | `/api/issues/{id}` | Issue + reports (raw text, translation, photo, severity, confidence) + matches + signals + feedback + priority breakdown | Both issue detail pages |
| POST | `/api/issues/{id}/close` | Sets status `closed` | Admin issue detail |
| POST | `/api/issues/{id}/route` | Fixed category → PMC department lookup; writes a `ROUTED_TO_AGENCY` signal | Admin issue detail |
| POST | `/api/issues/{id}/feedback` | Citizen confirms or disputes a closed issue; a dispute reopens it and writes `CITIZEN_DISPUTED_RESOLUTION` | Public issue detail |
| GET | `/api/matches` | Issue→work matches with scores and `match_reason`, ordered by score | Explorer, Verification |
| GET | `/api/works` | Paged works, filter by `ward_id` / `category` | Public works |
| GET | `/api/map` | Issue points, **matched** work points, sensitive sites, ward `{id, name}` | Most pages |
| POST | `/api/uploads/photo` | Stores jpeg/png/webp ≤ 5 MB; returns URL | Report form |
| POST | `/api/reports` | Full intake: language detect → translate → classify → severity → location → cluster → priority → match → signals | Report form |
| static | `/uploads/*` | Evidence photos | Image display |

---

## 4. Data actually available (live DB, 2026-09-26)

| Table | Rows | Notes |
|---|---|---|
| `wards` | 58 | All have `MultiPolygon` geometry, but **the API returns only id + name**. `population` is NULL (see Gotchas) |
| `issues` | 322 | **All `open`**. Statuses in code: `open`, `closed`, `reopened` |
| `reports` | 402 | **All `is_synthetic = true`** |
| `works` | 318 | Pune-district MPLADS rows only (the 60,359 figure is the national cleaned set). 117 have geometry, 201 don't |
| `matches` | 27 | |
| `signals` | 41 | `plausible_completion_window` (27), `repeat_sanctions_same_category_ward` (14). The code can also emit `recurrence_with_matched_work`, `ROUTED_TO_AGENCY` and `CITIZEN_DISPUTED_RESOLUTION` |
| `sensitive_sites` | 3,456 | OSM + PMC bus stops |
| `feedback` | 0 | The insert hardcodes `is_synthetic = true` |

**No tables exist for:** users, roles, departments, sessions, assignments, status history / audit log, comments, tenders, data-source config. *(Since added: `users`, `user_wards`, `user_departments`, `reports.reporter_user_id`, via `migrations/001_auth_foundation.sql`.)*
`routed_agency` is a free-text column populated from the fixed `AGENCY_MAP` in `app/core/routing.py` (7 PMC departments + General Complaints Cell). That's the only "department" concept in the system.

---

## 5. Authentication and roles

> **Update (same day): superseded by the backend auth foundation.** Token
> authentication, the four roles, ward/department scope, report ownership,
> `/api/me*` and the public `/api/public/*` API now exist, and the internal
> endpoints below now require staff. See `docs/backend_auth_foundation.md`.
> The frontend still sends no token, so its internal calls now get 401 until
> the frontend phase switches public pages to `/api/public/*`. The text
> below describes the state at audit time.

- **Authentication: none.** No login endpoint, no tokens, no session, no password storage, no user table.
- **Authorization: none.** Every endpoint, including `close`, `route` and the full internal `issueDetail`, is callable by anyone.
- **Roles: none** in the backend. The only role-like split is the frontend `/citizen` vs `/admin` route prefix, and the in-code comment says so ("Prototype only - no auth exists on either side").
- CORS allows any localhost origin (local-dev policy, commented as such).

**Consequence for citizen privacy (current bug-level issue):** `PublicIssueDetail` calls `GET /api/issues/{id}`, so the browser receives every report's raw text, priority breakdown, match scores and signal explanations, even where the page doesn't render them. Hiding them in the UI doesn't protect them. A public projection endpoint (or a server-side role check) is needed before the citizen side can honestly claim to hide internal data.

---

## 6. Capability matrix

Legend: ✅ exists · ◐ partial · ❌ missing

### Citizen

| Capability | API | UI | Notes |
|---|---|---|---|
| Register / sign in | ❌ | ❌ | No auth backend |
| Submit complaint (text, ward, photo) | ✅ | ✅ | |
| Confirm location on a map | ◐ | ◐ | API accepts `ward_id` only; no lat/lon field in `ReportCreateRequest`. Location comes from text geocoding |
| Pick category manually | ❌ | ❌ | Category is always classified server-side; no override field |
| My complaints | ❌ | ❌ | `reports` has no submitter column |
| Track complaint status | ◐ | ◐ | Possible only by issue id (no ownership) |
| Public issue list / map | ✅ | ✅ | Served from internal endpoints (see §5) |
| Ward boundaries on map | ◐ | ❌ | Geometry is in the DB, not exposed by the API |
| Confirm / dispute resolution | ✅ | ✅ | Anyone can submit, not only the reporter |

### Ward officer

| Capability | API | UI | Notes |
|---|---|---|---|
| Ward-scoped dashboard | ◐ | ◐ | `ward_id` filter exists; no identity to scope by |
| Issue list, filter, sort | ◐ | ✅ | No text search, no recurrence filter, no date range, sort limited to priority/recent |
| Issue detail with evidence and priority reasoning | ✅ | ✅ | Strongest screen today |
| Recurrence count | ✅ | ✅ | |
| Exposure / sensitive-site context | ✅ | ◐ | Inside `priority_breakdown.exposure_detail`; sites on the map |
| Related public works + match reason | ✅ | ✅ | |
| Verification signals with source ids | ✅ | ✅ | |
| Assign to officer | ❌ | ❌ | Only department-level routing |
| Status workflow (in progress, etc.) | ❌ | ❌ | Only open → closed → reopened |
| Resolution notes / proof of fix | ❌ | ❌ | `close` takes no body |
| Record a human decision on a signal | ❌ | ❌ | Signals have no review status |
| Audit trail of who did what | ❌ | ❌ | No actor on any write |

### Department / admin officer

| Capability | API | UI | Notes |
|---|---|---|---|
| Cross-ward issue list / map | ✅ | ✅ | Default when no ward filter |
| Filter by department | ❌ | ❌ | `routed_agency` exists but isn't a filter parameter |
| Trends over time | ❌ | ❌ | No aggregation endpoint; `first_reported` / `last_reported` exist to build one |
| Priority / category distribution | ◐ | ❌ | Possible client-side from `listIssues` (322 rows, two pages of 200). An aggregate endpoint is the right fix |
| Workload by department | ❌ | ❌ | |
| Tenders | ❌ | ❌ | `MAHATENDERS.MD` confirms tenders are pitch reference material, not ingested |
| System metrics (model/matcher quality) | ✅ | ✅ | On the Verification page |

### System administrator

| Capability | API | UI |
|---|---|---|
| Users, roles, permissions | ❌ | ❌ |
| Departments | ❌ (hardcoded map) | ❌ |
| Wards | ◐ (read only, via map) | ❌ |
| Data sources | ❌ | ❌ |
| Audit / access logs | ❌ | ❌ |
| System health | ✅ (`/api/health`) | ❌ |

---

## 7. Problems to fix before calling it a product

1. **Hardcoded record count.** `Landing.tsx:175` and `Footer.tsx:102` say "60,000+ … MPLADS records". The DB serving the app holds 318 (Pune district). The 60,359 is the national cleaned dataset. Either state it precisely ("60,359 national records cleaned; 318 Pune works linked") or read it from `/api/stats`. This matters under hard rule 4.
2. **Citizen data leakage** via the internal issue-detail endpoint (§5).
3. **Citizen copy exposes internal concepts:** Home mentions "computed priority scores"; ReportIssue says "to increase resolution priority"; PublicIssueDetail shows the verification signal count and "administrator review queue".
4. **Unprotected writes:** anyone can close or route any issue.
5. **Verification page N+1:** one `issueDetail` request per matched issue.
6. **Synthetic labelling:** every report is synthetic. The UI must keep showing that (hard rule 5); confirm every list and detail view does.
7. **Hand-synced `types.ts`** can drift from `schemas.py`.

---

## 8. Functional vs placeholder

**Build fully functional now (API already exists):**
landing, report complaint, public issue list/map/detail (after a public projection), officer dashboard, issue explorer, issue detail, map intelligence, public works, verification view, close/route actions, citizen feedback, system-quality metrics.

**Functional with a small backend addition (additive endpoints only, no contract changes):**

| Feature | Backend addition |
|---|---|
| Ward boundaries on maps | `GET /api/wards` returning GeoJSON (geometry already stored) |
| Safe public issue view | `GET /api/public/issues/{id}` (category, ward, status, dates, count, location) |
| Analytics | `GET /api/analytics` (counts by category/status/ward, priority histogram, issues per week) |
| Text search / department filter | Optional `q` and `routed_agency` params on `/api/issues` |
| Verification queue | `GET /api/signals` (flat, paged) to replace the N+1 |

**Needs real backend work (design the UI boundary only, clearly marked "not yet connected"):**
authentication, users/roles/permissions, "my complaints", officer assignment, a richer status workflow, human review decisions on signals, audit log, department and data-source management, tenders.

**Recommendation on auth:** don't build a fake login screen that "signs in" without a backend. Build an `AuthProvider` + `RequireRole` route guard against a typed `Session` interface, and give it a single integration point (`auth/session.ts`). Until the backend exists, run in an explicit, visibly labelled **"Prototype: role preview"** mode (role switcher in the header, banner on every page). That shows the role-aware product honestly without pretending it's secure.

---

## 9. Recommended information architecture

```
PUBLIC (no sign-in)
/                         Landing: what it is, how it works, live stats, public map preview
/map                      Public issue map (+ ward boundaries once /api/wards exists)
/issues                   Public issue list
/issues/:id               Public issue detail (public projection only) + resolution feedback
/report                   Report an issue (text, ward, photo, voice) → confirmation
/signin, /register        Auth boundary (placeholder until backend)

CITIZEN (/me)             ← needs auth + reporter ownership
/me                       My complaints, status, recent activity

MUNICIPAL (/ops)          ← role: ward_officer | department_officer
/ops                      Dashboard (scoped to ward or department)
/ops/issues               Priority queue / explorer: filters, sort, search
/ops/issues/:id           Issue intelligence: observed · computed · matched · signal · human decision
/ops/map                  Map intelligence: wards, issues, works, sensitive sites
/ops/works                Public works + issue→work links
/ops/verification         Signal queue + evidence + (future) human review
/ops/analytics            Category, priority, recurrence, ward patterns, trends
/ops/system               Pipeline quality metrics (current /api/metrics)

ADMIN (/admin)            ← role: system_admin, all placeholder until backend
/admin/users, /admin/roles, /admin/departments, /admin/wards,
/admin/data-sources, /admin/audit
```

Existing `/citizen/*` and `/admin/*` routes should redirect to their new homes so nothing breaks.

**Issue detail provenance labels** (for the key screen): tag every block with one of
`Observed` (citizen text, photo, timestamps), `Computed` (category, severity, priority terms, recurrence, exposure),
`Matched from public records` (MPLADS work + match reason + score), `Verification signal` (rule name + source ids),
`Human decision` (close, route, feedback). All five already come from `IssueDetailResponse`, so this is a pure UI change.

---

## 10. Recommended implementation order

Adjusted from the requested order. Auth goes after the shell because the auth backend doesn't exist, and the one real risk (citizen data leakage) should be fixed early.

1. **Design system + app shell.** Tokens, typography, layout primitives, navigation for public/ops/admin. Remove the gradient `GlowingEffect`. Fix the hardcoded "60,000+" copy.
2. **Role-aware routing + auth boundary.** `AuthProvider`, `RequireRole`, labelled role-preview mode, new route map with redirects from old paths.
3. **Backend additions, additive only:** `/api/public/issues/{id}`, `/api/wards` (GeoJSON), `/api/analytics`, `/api/signals`. Each with a test.
4. **Public / citizen portal:** landing, report flow, public map, public issue detail on the public projection. Mobile-first.
5. **Issue detail (ops).** The most important screen: provenance labels, evidence, priority reasoning, works, signals, actions.
6. **Issue explorer / priority queue.**
7. **Ops dashboard** (ward/department scoped).
8. **Map intelligence** with ward polygons.
9. **Public works.**
10. **Verification queue** (on `/api/signals`, no N+1).
11. **Analytics** (on `/api/analytics`).
12. **Admin console:** structure and clearly labelled "requires backend" states only.

Not started, needs a decision: real authentication (which provider/approach) and a reporter-ownership column for "my complaints". Both are schema changes.
