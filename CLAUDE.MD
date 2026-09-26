# CLAUDE.md — WardSentry

Read `ARCHITECTURE.md` for the build spec, `DEMO.md` for what we are building
toward, and `BUILD_PLAN.md` for the hour-by-hour plan and who owns what.

## Context

Hackathon PS-18 (civic grievance triage, deduplication and accountability).
Team of three. **One 12-hour session.** Prototype, not production.

The thing that makes this project different: we hold 60,359 cleaned MPLADS
public works records, so we can link a recurring civic issue to the public work
already funded to prevent it. No other team is doing that. Protect it.

## Stack

- Python 3.11 · FastAPI · uvicorn
- PostgreSQL 16 + PostGIS + pgvector, via docker-compose
- sentence-transformers `all-MiniLM-L6-v2` · scikit-learn · spaCy `en_core_web_sm`
- React + Vite + Leaflet
- pytest

No auth. No deployment. No CI. Local only.

## Hard rules — never violate

1. **Priority is a formula, never a model.** Weights are constants in
   `app/core/priority.py`, printable, and returned in the breakdown.
2. **Every signal names its source record ids.** No unexplained output.
3. **No photo severity model.** Photos are stored and shown as evidence only.
4. **Nothing hardcoded to make the demo pass.** Seeded data is fine and labelled.
   Anything presented as computed must be computed at runtime from the database.
5. **Synthetic complaints are labelled synthetic** in schema and UI.
6. **Never imply guilt.** Words: anomaly signal, verification priority, evidence,
   human review. Never: fraud, corrupt, guilty, responsible.
7. **Every failure degrades gracefully and says so.** Geocode fails → ward
   centroid at confidence 0.4. Match below threshold → no match. Classification
   below threshold → manual queue.

## Working style

- **One task per request.** Write the test first, then the code, then run it.
- **Always run what you write.** Never hand back unexecuted code. If you cannot
  run it, say so explicitly.
- **Show real output**, not a description of expected output.
- **Boring and readable beats clever.** We are debugging this at 3am.
- **Ask when ambiguous.** We have one day and no time to unpick a wrong guess.
- **Commit after every working piece**, with a descriptive message.
- When you learn something the hard way (a column is swapped, a library version
  is wrong, an API rate-limits), **add it to the Gotchas section below immediately.**

## Build order

Follow `BUILD_PLAN.md`. Do not jump ahead to the UI before the matcher works —
a beautiful page with nothing behind it loses this hackathon.

The single most important deliverable is: **one real MPLADS work record linked
to one clustered issue, both visible on screen, with the match reason shown.**
If we finish with only that, we still have what nobody else has.

## Definition of done

See `DEMO.md`. If a feature does not appear in that script, it does not get
built today.

---

## Gotchas

*(Append as we discover them. Keep this current — it is what survives a `/clear`.)*

- **No Docker on this machine.** `docker-compose up` isn't available. Substitute: a
  native Postgres 17 cluster dedicated to this project, isolated from the
  machine's existing Postgres 15 (which has an unrelated `blueprint_reader` DB —
  do not touch it). Dedicated cluster: data dir
  `/opt/homebrew/var/postgresql@17-civicfix`, port **5433**, db `civicfix`,
  postgis 3.6.4 + pgvector 0.8.6 already `CREATE EXTENSION`'d. Start/stop:
  `pg_ctl -D /opt/homebrew/var/postgresql@17-civicfix -o "-p 5433" -l /opt/homebrew/var/postgresql@17-civicfix/server.log start|stop`
  (use `/opt/homebrew/opt/postgresql@17/bin/pg_ctl` if `postgresql@15`'s pg_ctl is
  first on PATH). Not registered as a LaunchAgent (needs explicit user approval
  for login-persistence), so it must be started manually each session/reboot.
  Connect: `postgresql://swarajdeshmukh4249gmail.com@localhost:5433/civicfix`.
  Same story for `pg_dump`/`pg_restore`: the `postgresql@15` one on PATH is
  v15 and refuses to dump a v17 server ("aborting because of server version
  mismatch"). Use `/opt/homebrew/opt/postgresql@17/bin/pg_dump`.
- **Homebrew Python is broken on this Mac for anything touching `pip`/`plistlib`.**
  `/usr/lib/libexpat.1.dylib` (system lib, macOS 26.2 beta) is missing a symbol
  Homebrew's Python bottles need (`_XML_SetAllocTrackerActivationThreshold`),
  which breaks `pyexpat` → `plistlib` → `pip` (surfaces as
  `ValueError: invalid literal for int() with base 10: ''` deep in pip/packaging).
  Fix: `brew install expat` then
  `export DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib`. Already baked into the
  bottom of `.venv/bin/activate` in this repo — just `source .venv/bin/activate`.
  Affects every Homebrew Python (3.12 and 3.14 both confirmed broken); not a
  project bug.
- **Python 3.11 (per stack) vs what's actually usable here.** Homebrew doesn't
  have 3.11 readily paired with working ML wheels checked yet; venv is built on
  Homebrew **Python 3.12** instead (3.14 is installed but too new for some ML
  package wheels). Re-check if this causes a real incompatibility; nothing hit
  so far.
- **Tests and dev data used to share one database — this destroyed real data
  once.** Running `pytest` after a real MPLADS ingestion truncated `works` via
  the `clean_works` fixture and replaced it with 3 fixture rows; a later test
  run truncated it again down to 0. Fixed: tests now run against a separate
  `civicfix_test` database (`TEST_DATABASE_URL` in `.env`), which
  `tests/conftest.py` swaps in for `DATABASE_URL` before `app.db` is imported.
  Never point `TEST_DATABASE_URL` at `civicfix` or a `clean_*` fixture will
  wipe real ingested data again. Recovery, if it ever recurs: MPLADS
  re-ingestion is fast (~15s) as long as `data/cache/geocode_cache.json`
  (committed) still has the resolved queries cached — only slow the first
  time because Nominatim throttles bulk unauthenticated requests hard.
- **Two terminals running pytest at once block each other.** Both hit
  `civicfix_test`; one session's `TRUNCATE` waits on the other's open
  transaction, so a 6s file takes minutes and looks hung. Pytest's cache
  dir also contends — pass `-p no:cacheprovider`. Run tests from one
  terminal at a time.
- **`pmc.gov.in` is unreachable from this machine** (both http and https time
  out, curl exit 28). It hosts the only per-ward population figures for the
  2022 scheme, inside the final ward map PDFs linked from
  `data/wards/ward-attributes.csv`'s `orig` column. So `wards.population` is
  still NULL and `priority.py`'s density-scaled exposure radius stays on its
  300 m fallback. `data/labelling/ward_population.csv` is pre-filled with all
  58 wards, computed areas and the per-ward PDF URL - someone on a network
  that can reach PMC fills one column and runs
  `python -c "from app.ingest.wards import load_ward_population as l; print(l())"`.
- **`clean_wards` commits, so ward state leaks across test files.** Unlike
  `db_conn` (which rolls back), the `clean_wards` fixture commits, and
  `load_ward_population` commits too - so a population written in
  `test_wards.py` was still there when `test_priority.py` ran, breaking a test
  that assumed "no ward has density data". Tests must establish their own
  ward density precondition rather than trusting the ambient DB.
- **MPLADS "Ward No. N" is never a ward id.** The text mixes PMC old/new,
  PCMC and village numbering (see `data/eval/mplads_ward_review.csv`).
  Works are placed by geocoded landmark (`geom_confidence` 1.0), reviewed
  ward or gazetteer place (0.5), else left unplaced.
- **Schema changes go in `migrations/NNN_*.sql`, applied with `python -m app.migrate`.**
  `schema.sql` is `CREATE ... IF NOT EXISTS` only, so a column added there never
  reaches an existing database. Migrations must be additive and idempotent;
  `tests/conftest.py` applies them to `civicfix_test` automatically. Back up the
  real DB first (v17 `pg_dump`, see above).
- **PyJWT's `PyJWKClient` refuses `file://` JWKS URLs** ("only 'http' and 'https'
  are supported"). Local dev and tests serve the public JWKS over localhost HTTP
  instead (see `docs/backend_auth_foundation.md` §11) - don't add a file-loading
  path to `app/auth.py`.
- **iCloud evicts files from this repo.** It lives in `~/Documents`, which macOS
  syncs to iCloud with "Optimize Mac Storage": ~30k `.venv` files (and some
  `.pyc`/uploads) became dataless placeholders, so `import torch` failed with
  `OSError: could not get source code` and even `head` read 0 bytes. Check with
  `find .venv -flags +dataless | wc -l`; restore with
  `find .venv -flags +dataless -print0 | xargs -0 -n 200 brctl download` (async,
  ~500 files/min). Lasting fix: move the repo out of `~/Documents`, or rename the
  venv to `.venv.nosync` and symlink `.venv` to it.
- **Phone cameras need https.** `getUserMedia` only works in a secure context,
  so `http://<laptop-ip>:5173` gets no camera. `cd web && npm run cert` makes a
  self-signed cert for the LAN IP; the citizen dev server then serves https on
  the network (accept the warning once on the phone). The API is reached
  same-origin through Vite's `/api` proxy - never point the phone at :8000.
-

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
